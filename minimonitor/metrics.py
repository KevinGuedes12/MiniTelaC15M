"""Amostragem local de métricas do Linux."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
from time import monotonic

import psutil


@dataclass(frozen=True)
class Metrics:
    clock: str
    cpu: float | None
    ram: float | None
    battery: float | None
    battery_status: str
    temperature: float | None
    wifi: bool | None
    wifi_bytes_per_second: float | None


def read_text(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def cpu_temperature():
    try:
        sensors = psutil.sensors_temperatures()
    except OSError:
        return None

    # Prioriza o pacote Intel e os sensores de CPU identificados pelo kernel.
    for driver, preferred_label in (
        ("coretemp", "Package id"), ("k10temp", "Tdie"),
        ("zenpower", "Tdie"), ("cpu_thermal", ""),
        ("x86_pkg_temp", ""),
    ):
        entries = [
            entry for entry in sensors.get(driver, ())
            if entry.current is not None and isfinite(entry.current)
        ]
        if entries:
            preferred = [entry.current for entry in entries
                         if entry.label.startswith(preferred_label)]
            return max(preferred or [entry.current for entry in entries])
    return None


def battery_metrics():
    try:
        battery = psutil.sensors_battery()
    except OSError:
        battery = None
    if battery is None:
        return None, "N/D"
    states = []
    for supply in Path("/sys/class/power_supply").glob("*"):
        if read_text(supply / "type") == "Battery":
            states.append(read_text(supply / "status"))
    for state, label in (
        ("Charging", "Carregando"), ("Discharging", "Em uso"),
        ("Full", "Completa"), ("Not charging", "Sem carga ativa"),
    ):
        if state in states:
            return battery.percent, label
    return battery.percent, "Na tomada" if battery.power_plugged else "N/D"


class Collector:
    def __init__(self):
        psutil.cpu_percent(interval=None)
        self._cpu_since = monotonic()
        self._wifi_sample = None

    def _wifi(self, now):
        interfaces = sorted(
            path for path in Path("/sys/class/net").glob("*")
            if (path / "phy80211").exists() or (path / "wireless").is_dir()
        )
        states = [(path, read_text(path / "operstate")) for path in interfaces]
        # Para Wi-Fi, carrier confirma associação quando operstate é unknown.
        active = next(
            (path for path, state in states if state == "up" or
             read_text(path / "carrier") == "1"),
            None,
        )
        previous, self._wifi_sample = self._wifi_sample, None
        if active is None:
            disconnected = {"down", "lowerlayerdown", "dormant", "notpresent"}
            status = False if states and all(s in disconnected for _, s in states) else None
            return status, None

        counters = [read_text(active / "statistics" / name)
                    for name in ("rx_bytes", "tx_bytes")]
        if any(value is None or not value.isdecimal() for value in counters):
            return True, None
        rx, tx = map(int, counters)
        self._wifi_sample = (active, now, rx, tx)
        if previous is None:
            return True, None
        old_path, old_time, old_rx, old_tx = previous
        if old_path != active or now <= old_time or rx < old_rx or tx < old_tx:
            return True, None
        return True, (rx - old_rx + tx - old_tx) / (now - old_time)

    def sample(self):
        now = monotonic()
        cpu = None
        if now - self._cpu_since >= 0.1:
            cpu = psutil.cpu_percent(interval=None)
            self._cpu_since = now
        battery, state = battery_metrics()
        wifi, speed = self._wifi(now)
        return Metrics(
            datetime.now().strftime("%H:%M"), cpu, psutil.virtual_memory().percent,
            battery, state, cpu_temperature(), wifi, speed,
        )
