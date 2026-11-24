"""Seleção de interface, permitindo que uma única saída receba os quadros."""

from dataclasses import replace
from time import monotonic

from gi.repository import GLib

from .config import INTERVAL_MS


class Screens:
    def __init__(self, dashboard, music, display, *, clock=monotonic):
        self.dashboard = dashboard
        self.music = music
        self.display = display
        self.clock = clock
        self.active = "dashboard"
        self.track = None
        self.idle_since = None
        self.timer = 0

    def changed(self, track, paused=None):
        now = self.clock()
        if track is not None:
            if self.idle_since is not None or self.track is None:
                self.active = "music"
            self.track = track
            self.idle_since = None
        elif self.track is not None:
            # Congela a posição durante a carência se o player encerrar.
            if self.idle_since is None:
                self.track = paused or replace(self.track, status="Stopped",
                                               position=self.track.elapsed(now))
                self.idle_since = now
        self.refresh()

    def toggle(self):
        if self.track is not None:
            self.active = "music" if self.active == "dashboard" else "dashboard"
            self.refresh()

    def refresh(self):
        self.stop()
        now = self.clock()
        if self.idle_since is not None and now - self.idle_since >= 30:
            self.track = None
            self.idle_since = None
            self.active = "dashboard"
        if self.active == "music":
            self.display("music", self.music(self.track, now))
            if self.track.playing:
                self.timer = GLib.timeout_add(1000, self._tick)
            elif self.idle_since is not None:
                remaining = max(1, round((30 - (now - self.idle_since)) * 1000))
                self.timer = GLib.timeout_add(remaining, self._tick)
        else:
            self.display("dashboard", self.dashboard())
            self.timer = GLib.timeout_add(INTERVAL_MS, self._tick)

    def _tick(self):
        self.timer = 0
        self.refresh()
        return GLib.SOURCE_REMOVE

    def stop(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
