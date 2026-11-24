"""Saída USB opcional. Um gerenciador é dono da porta durante toda a sessão."""

import os
from pathlib import Path
import struct
import sys
import termios

from gi.repository import Gio, GLib

from .live_display import bar_level, update
from .registers import MUSIC_BARS, MUSIC_FIELDS, VISUALIZER
from .visualizer import phase
from .media import Mpris
from .metrics import Collector
from .presentation_values import stamp
from .probe import response, serial_device
from .screens import Screens

PAGES = {"dashboard": 5, "music": 6}


class Device:
    def __init__(self, fd, *, visualizer=False):
        self.fd = fd
        self.visualizer = visualizer
        self.page = None
        self.cache = {}
        self.dashboard_cache = {}
        self.unconfirmed = set()
        self.buffer = bytearray()

    def write_registers(self, payload):
        try:
            response(self.fd, 0x0090, 0x00D0, payload, timeout=0.35, buffer=self.buffer)
        except TimeoutError:
            # O C15M já apresentou atualizações visíveis sem ACK.
            pass

    def display(self, view, frame):
        if view != self.page:
            self.write_registers(struct.pack(">BHI", 0x80, 2, PAGES[view]))
            self.page = view
        if view == "dashboard":
            update(self.fd, frame, self.dashboard_cache, self.unconfirmed)
            return
        text_values, numeric_values = frame
        for field, value in zip(MUSIC_FIELDS, text_values):
            self.set_text(field.register, value)
        fields = MUSIC_BARS + (VISUALIZER,) if self.visualizer else MUSIC_BARS
        changed = [(field.register, value) for field, value in zip(fields, numeric_values)
                   if self.cache.get(field.register) != value]
        if changed:
            payload = bytes([0x80 | (len(changed) - 1)])
            payload += b"".join(struct.pack(">HI", register, value) for register, value in changed)
            self.write_registers(payload)
            self.cache.update(changed)

    def set_text(self, register, value):
        if self.cache.get(register) == value:
            return
        # O atlas desta página usa Latin-1 e o campo comporta até 27 glifos.
        encoded = " ".join(value.split()).encode("latin-1", errors="replace")
        if len(encoded) > 27:
            encoded = encoded[:24] + b"..."
        encoded = (encoded or b" ").decode("latin-1").encode("utf-8")
        payload = struct.pack(">BHH", 0xD0, register, len(encoded)) + encoded
        self.write_registers(payload)
        self.cache[register] = value


def values(track, now):
    elapsed = track.elapsed(now)
    duration = stamp(track.duration, unknown=not track.duration)
    progress = bar_level(100 * elapsed / track.duration if track.duration else None)
    return ((track.title, track.artist, f"{stamp(elapsed)}/{duration}", track.label),
            (progress, phase(track, now)))


def login_bus():
    """Acessa o barramento do mesmo usuário quando executado pelo serviço de boot."""
    endpoint = Path(f"/run/user/{os.getuid()}/bus")
    if not endpoint.is_socket():
        return None
    bus = Gio.DBusConnection.new_for_address_sync(
        f"unix:path={endpoint}",
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None,
    )
    bus.set_exit_on_close(False)
    return bus


def run(input_devices=(), minitela_key=None, *, visualizer=False, wait_for_login=False):
    main = GLib.MainLoop()
    error = None
    try:
        with serial_device() as (fd, node):
            device = Device(fd, visualizer=visualizer)
            collector = Collector()

            def present(view, frame):
                nonlocal error
                try:
                    device.display(view, frame)
                except (OSError, ValueError, termios.error) as exc:
                    error = exc
                    main.quit()

            screens = Screens(collector.sample, values, present)

            mpris = None
            keys = None
            retry = 0
            keyboard_error = None

            def schedule_reconnect():
                nonlocal retry
                if wait_for_login and not retry:
                    retry = GLib.timeout_add_seconds(4, reconnect)

            def changed():
                nonlocal mpris, keys
                if mpris is None or mpris.bus.is_closed():
                    if mpris is not None:
                        mpris.close()
                        mpris = None
                        print("Sessão MPRIS encerrada.", flush=True)
                    if keys is not None and wait_for_login:
                        keys.close()
                        keys = None
                    screens.changed(None)
                    schedule_reconnect()
                    return
                player = screens.track.player if screens.track else None
                screens.changed(mpris.active(player), mpris.tracks.get(player))

            def attach_keys():
                nonlocal keys, keyboard_error
                from .media_keys import Chords, InputKeys

                def skip(direction):
                    if mpris is not None:
                        track = mpris.active(screens.track.player if screens.track else None)
                        if track is not None:
                            mpris.skip(track, direction)

                def pause():
                    if mpris is not None:
                        mpris.toggle_playback(screens.track.player if screens.track else None)

                try:
                    keys = InputKeys(input_devices, Chords(minitela_key, screens.toggle, skip, pause))
                    keyboard_error = None
                except OSError as exc:
                    if not wait_for_login:
                        raise
                    if str(exc) != keyboard_error:
                        print(f"Atalhos aguardando teclado: {exc}", file=sys.stderr, flush=True)
                        keyboard_error = str(exc)
                    schedule_reconnect()

            def reconnect():
                nonlocal mpris, retry
                retry = 0
                if mpris is None:
                    try:
                        bus = login_bus() if wait_for_login else None
                        if bus is None and wait_for_login:
                            schedule_reconnect()
                            return GLib.SOURCE_REMOVE
                        mpris = Mpris(changed, bus=bus)
                    except (OSError, GLib.Error) as exc:
                        if not wait_for_login:
                            print(f"MPRIS indisponível: {exc}", file=sys.stderr, flush=True)
                        schedule_reconnect()
                        return GLib.SOURCE_REMOVE
                    if wait_for_login:
                        print("Sessão MPRIS conectada.", flush=True)
                    changed()
                if input_devices and keys is None:
                    attach_keys()
                return GLib.SOURCE_REMOVE

            try:
                print(f"MiniMonitor em {node}.", flush=True)
                screens.refresh()
                if wait_for_login:
                    schedule_reconnect()
                elif error is None:
                    reconnect()
                if error is None:
                    main.run()
            finally:
                if retry:
                    GLib.source_remove(retry)
                if keys is not None:
                    keys.close()
                screens.stop()
                if mpris is not None:
                    mpris.close()
            if error is not None:
                raise error
    except KeyboardInterrupt:
        return 0
    except (GLib.Error, OSError, ValueError, termios.error) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
