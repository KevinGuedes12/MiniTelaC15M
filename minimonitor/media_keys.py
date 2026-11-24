"""Atalhos opt-in via eventos Linux, sem tomar posse exclusiva do teclado."""

import os
import struct

from gi.repository import GLib, GLibUnix

EVENT = struct.Struct("@llHHi")
EV_KEY = 1
ARROWS = {105: "left", 106: "right"}
SPACE = 57


class Chords:
    def __init__(self, key, toggle, skip, pause):
        self.key, self.toggle, self.skip, self.pause = key, toggle, skip, pause
        self.held = self.used = False

    def event(self, key, value):
        if key == self.key:
            if value == 1:
                self.held, self.used = True, False
            elif value == 0 and self.held:
                self.held = False
                if not self.used:
                    self.toggle()
        elif self.held and value == 1 and key == SPACE:
            self.used = True
            self.pause()
        elif self.held and value == 1 and key in ARROWS:
            self.used = True
            self.skip(ARROWS[key])


class InputKeys:
    def __init__(self, paths, chords):
        self.sources = {}
        self.chords = chords
        try:
            for path in dict.fromkeys(paths):
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                try:
                    self.sources[fd] = GLibUnix.fd_add_full(
                        GLib.PRIORITY_DEFAULT, fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                        self._ready,
                    )
                except Exception:
                    os.close(fd)
                    raise
        except (OSError, TypeError):
            self.close()
            raise

    def _ready(self, fd, condition, _data=None):
        if condition & GLib.IO_IN:
            try:
                data = os.read(fd, EVENT.size * 32)
            except BlockingIOError:
                return GLib.SOURCE_CONTINUE
            except OSError:
                data = b""
            if data and len(data) % EVENT.size == 0:
                for _, _, kind, code, value in EVENT.iter_unpack(data):
                    if kind == EV_KEY:
                        self.chords.event(code, value)
                return GLib.SOURCE_CONTINUE
        self.sources.pop(fd)
        os.close(fd)
        self.chords.held = False
        return GLib.SOURCE_REMOVE

    def close(self):
        for fd, source in self.sources.items():
            GLib.source_remove(source)
            os.close(fd)
        self.sources.clear()


def diagnose(paths):
    """Mostra o primeiro pressionamento observado e encerra."""
    loop = GLib.MainLoop()

    class FirstPress:
        held = False
        found = False

        def event(self, key, value):
            if value == 1 and not self.found:
                self.found = True
                print(f"Código EV_KEY: {key}", flush=True)
                loop.quit()

    probe = FirstPress()
    try:
        keys = InputKeys(paths, probe)
    except OSError as exc:
        print(exc)
        return 1
    def timeout():
        loop.quit()
        return GLib.SOURCE_CONTINUE

    timer = GLib.timeout_add_seconds(8, timeout)
    try:
        print("Pressione apenas a tecla MINITELA uma vez.", flush=True)
        loop.run()
    finally:
        GLib.source_remove(timer)
        keys.close()
    if not probe.found:
        print("Nenhum evento EV_KEY foi observado nesses dispositivos.")
    return 0 if probe.found else 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Identifica o código Linux da tecla MINITELA.")
    parser.add_argument("devices", metavar="/dev/input/eventN", nargs="+")
    raise SystemExit(diagnose(parser.parse_args().devices))
