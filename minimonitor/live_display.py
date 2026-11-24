"""Atualiza os registros em memória do tema MiniMonitor dinâmico."""

import struct
import sys
import termios
from time import monotonic, sleep

from .config import INTERVAL_MS
from .registers import BARS, BAR_LEVELS, FIELDS
from .metrics import Collector
from .probe import response, serial_device
from .presentation_values import percent, speed_label


def bar_level(value):
    return 0 if value is None else min(BAR_LEVELS, max(0, round(value * BAR_LEVELS / 100)))


def update(fd, metrics, previous, unconfirmed=None):
    values = (
        metrics.clock,
        percent(metrics.cpu),
        percent(metrics.ram),
        percent(metrics.battery),
        {"Sem carga ativa": "Sem carga"}.get(metrics.battery_status, metrics.battery_status),
        "N/D" if metrics.temperature is None else f"{metrics.temperature:.0f} °C",
        {True: "Conectado", False: "Sem enlace", None: "N/D"}[metrics.wifi],
        speed_label(metrics.wifi_bytes_per_second) or " ",
    )
    buffer = bytearray()
    if unconfirmed is None:
        unconfirmed = set()

    def send(payload, fields):
        label = ", ".join(f"{field.name} ({field.register})" for field in fields)
        try:
            response(fd, 0x0090, 0x00D0, payload, buffer=buffer, timeout=0.35)
        except TimeoutError:
            if label not in unconfirmed:
                print(f"Sem confirmação AHMI para {label}.", file=sys.stderr, flush=True)
                unconfirmed.add(label)
        else:
            if label in unconfirmed:
                print(f"Confirmação recuperada para {label}.", flush=True)
                unconfirmed.remove(label)

    for field, value in zip(FIELDS, values):
        if previous.get(field.register) == value:
            continue
        encoded = value.encode("utf-8")
        payload = struct.pack(">BHH", 0xD0, field.register, len(encoded)) + encoded
        send(payload, (field,))
        previous[field.register] = value

    levels = (bar_level(metrics.cpu), bar_level(metrics.ram))
    changed = [(field.register, level) for field, level in zip(BARS, levels)
               if previous.get(field.register) != level]
    if changed:
        payload = bytes([0x80 | (len(changed) - 1)])
        payload += b"".join(struct.pack(">HI", reg, level) for reg, level in changed)
        send(payload, tuple(field for field in BARS if field.register in dict(changed)))
        previous.update(changed)


def run():
    collector = Collector()
    previous = {}
    unconfirmed = set()
    try:
        with serial_device() as (fd, node):
            print(f"Atualizando o tema dinâmico em {node}. Ctrl+C para sair.", flush=True)
            while True:
                cycle = monotonic()
                update(fd, collector.sample(), previous, unconfirmed)
                sleep(max(0, INTERVAL_MS / 1000 - (monotonic() - cycle)))
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, termios.error) as exc:
        print(exc, file=sys.stderr)
        return 1
