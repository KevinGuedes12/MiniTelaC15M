"""Descoberta e acompanhamento dos players MPRIS na sessão Linux."""

from dataclasses import dataclass
from time import monotonic

from gi.repository import Gio, GLib

PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
PROPERTIES = "org.freedesktop.DBus.Properties"


@dataclass(frozen=True)
class Track:
    player: str
    title: str = "Faixa desconhecida"
    artist: str = "Artista desconhecido"
    art: str = ""
    status: str = "Stopped"
    duration: int = 0
    position: int = 0
    sampled_at: float = 0

    @property
    def playing(self):
        return self.status == "Playing"

    @property
    def label(self):
        return {"Playing": "Tocando", "Paused": "Pausado"}.get(self.status, "Parado")

    def elapsed(self, now):
        position = max(0, self.position)
        if self.playing:
            position += int(max(0, now - self.sampled_at) * 1_000_000)
        return min(position, self.duration) if self.duration else position


def number(value):
    return max(0, value) if isinstance(value, int) else 0


def make_track(name, values, position, now):
    tags = values.get("Metadata") or {}
    artists = tags.get("xesam:artist")
    if isinstance(artists, str):
        artists = [artists]
    elif not isinstance(artists, (list, tuple)):
        artists = []
    return Track(
        name, tags.get("xesam:title") or "Faixa desconhecida",
        ", ".join(str(artist) for artist in artists if artist) if artists else "Artista desconhecido",
        tags.get("mpris:artUrl") or "", values.get("PlaybackStatus", "Stopped"),
        number(tags.get("mpris:length")), number(position), now,
    )


class Mpris:
    def __init__(self, changed, bus=None):
        self.changed = changed
        self.bus = bus if bus is not None else Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.tracks = {}
        self.owners = {}
        self.recent = {}
        self.subscriptions = [
            self.bus.signal_subscribe(
                "org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
                "/org/freedesktop/DBus", PREFIX[:-1], Gio.DBusSignalFlags.MATCH_ARG0_NAMESPACE,
                self._owner_changed),
            self.bus.signal_subscribe(
                None, PROPERTIES, "PropertiesChanged", PATH, PLAYER,
                Gio.DBusSignalFlags.NONE, self._player_changed),
            self.bus.signal_subscribe(
                None, PLAYER, "Seeked", PATH, None, Gio.DBusSignalFlags.NONE,
                self._player_changed),
        ]
        self.closed_handler = self.bus.connect("closed", self._closed)
        try:
            names, = self._dbus("ListNames", None)
            for name in sorted(names):
                if name.startswith(PREFIX):
                    try:
                        owner, = self._dbus("GetNameOwner", GLib.Variant("(s)", (name,)))
                    except GLib.Error:
                        continue
                    self.owners[name] = owner
                    self._refresh(name)
        except GLib.Error:
            self.close()
            raise

    def _dbus(self, method, args):
        return self._call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                          "org.freedesktop.DBus", method, args)

    def _call(self, name, path, interface, method, args=None):
        return self.bus.call_sync(name, path, interface, method, args, None,
                                  Gio.DBusCallFlags.NONE, 500, None).unpack()

    def _refresh(self, name):
        try:
            values, = self._call(name, PATH, PROPERTIES, "GetAll", GLib.Variant("(s)", (PLAYER,)))
        except GLib.Error:
            self.tracks.pop(name, None)
            return
        position = values.get("Position")
        if position is None:
            try:
                position, = self._call(name, PATH, PROPERTIES, "Get",
                                       GLib.Variant("(ss)", (PLAYER, "Position")))
            except GLib.Error:
                position = 0
        now = monotonic()
        previous = self.tracks.get(name)
        track = make_track(name, values, position, now)
        if track.playing and (previous is None or not previous.playing):
            self.recent[name] = now
        self.tracks[name] = track

    def _owner_changed(self, _bus, _sender, _path, _iface, _signal, args):
        name, _old, owner = args.unpack()
        if owner:
            self.owners[name] = owner
            self._refresh(name)
        else:
            self.owners.pop(name, None)
            self.tracks.pop(name, None)
            self.recent.pop(name, None)
        self.changed()

    def _player_changed(self, _bus, sender, _path, _iface, _signal, args):
        if len(args.unpack()) == 3:
            _, changes, invalidated = args.unpack()
            if not {"Metadata", "PlaybackStatus", "Position"}.intersection((*changes, *invalidated)):
                return
        for name, owner in self.owners.items():
            if owner == sender:
                self._refresh(name)
        self.changed()

    def active(self, current=None):
        if current in self.tracks and self.tracks[current].playing:
            return self.tracks[current]
        return max((track for track in self.tracks.values() if track.playing),
                   key=lambda track: self.recent.get(track.player, 0), default=None)

    def skip(self, track, direction):
        prop, method = {"left": ("CanGoPrevious", "Previous"),
                        "right": ("CanGoNext", "Next")}[direction]
        return self._control(track, prop, method)

    def toggle_playback(self, current=None):
        track = self.active(current)
        if track is not None:
            return self._control(track, "CanPause", "Pause")
        track = self.tracks.get(current)
        if track is None or track.status != "Paused":
            track = max((candidate for candidate in self.tracks.values() if candidate.status == "Paused"),
                        key=lambda candidate: self.recent.get(candidate.player, 0), default=None)
        if track is not None:
            return self._control(track, "CanPlay", "Play")
        return False

    def _control(self, track, prop, method):
        try:
            allowed, = self._call(track.player, PATH, PROPERTIES, "Get",
                                  GLib.Variant("(ss)", (PLAYER, prop)))
            if allowed:
                self._call(track.player, PATH, PLAYER, method)
        except GLib.Error:
            return False
        return bool(allowed)

    def _closed(self, _bus, _remote, _error):
        self.tracks.clear()
        self.owners.clear()
        self.recent.clear()
        self.changed()

    def close(self):
        if self.closed_handler:
            self.bus.disconnect(self.closed_handler)
            self.closed_handler = 0
        for subscription in self.subscriptions:
            self.bus.signal_unsubscribe(subscription)
        self.subscriptions.clear()
