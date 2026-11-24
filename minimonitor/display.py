"""Saída de prévia. Recebe quadros Cairo e os apresenta no desktop."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_foreign("cairo")
from gi.repository import GLib, Gtk

from .config import HEIGHT, INTERVAL_MS, WIDTH


class Preview(Gtk.Application):
    def __init__(self, next_frame):
        super().__init__(flags=0)
        self._next_frame = next_frame
        self._frame = None
        self._timer = 0

    def do_activate(self):
        if self.get_active_window() is not None:
            self.get_active_window().present()
            return
        window = Gtk.ApplicationWindow(application=self, title="MiniMonitor C15M")
        window.set_default_size(WIDTH, HEIGHT)
        window.set_resizable(False)
        canvas = Gtk.DrawingArea()
        canvas.set_content_width(WIDTH)
        canvas.set_content_height(HEIGHT)
        canvas.set_draw_func(self._draw)
        window.set_child(canvas)
        self.start(canvas)
        window.present()

    def start(self, canvas):
        self._refresh(canvas)
        self._timer = GLib.timeout_add(INTERVAL_MS, self._refresh, canvas)

    def _draw(self, _canvas, context, _width, _height):
        context.set_source_surface(self._frame, 0, 0)
        context.paint()

    def _refresh(self, canvas):
        self._frame = self._next_frame()
        canvas.queue_draw()
        return GLib.SOURCE_CONTINUE

    def do_shutdown(self):
        if self._timer:
            GLib.source_remove(self._timer)
        Gtk.Application.do_shutdown(self)
