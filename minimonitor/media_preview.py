"""Prévia GTK opcional do gerenciador de telas e do player MPRIS."""

from gi.repository import GLib

from .album_art import Artwork
from .display import Preview
from .media import Mpris
from .metrics import Collector
from .music_render import render_music
from .render import render
from .screens import Screens


class MediaPreview(Preview):
    def __init__(self):
        super().__init__(None)
        self.mpris = None
        self.screens = None
        self.art = None

    def start(self, canvas):
        collector = Collector()

        def present(_view, frame):
            self._frame = frame
            canvas.queue_draw()

        def music(track, now):
            return render_music(track, now, self.art.get(track.art))

        self.art = Artwork(lambda: self.screens.refresh() if self.screens.active == "music" else None)
        self.screens = Screens(lambda: render(collector.sample()), music, present)
        try:
            self.mpris = Mpris(self._changed)
        except GLib.Error as exc:
            print(f"MPRIS indisponível: {exc}", flush=True)
        self._changed()

    def _changed(self):
        if self.mpris is None:
            self.screens.changed(None)
        else:
            player = self.screens.track.player if self.screens.track else None
            self.screens.changed(self.mpris.active(player), self.mpris.tracks.get(player))

    def do_shutdown(self):
        if self.screens is not None:
            self.screens.stop()
        if self.mpris is not None:
            self.mpris.close()
        if self.art is not None:
            self.art.close()
        super().do_shutdown()
