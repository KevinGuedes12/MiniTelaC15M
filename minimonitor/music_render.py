"""Composição Cairo de 240×240 para a interface de música."""

import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from . import config as c
from .render import box, color, text
from .presentation_values import stamp
from . import visualizer


def fit(ctx, value, size, width, bold=False):
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    value = " ".join(value.split())[:240]
    if ctx.text_extents(value).x_advance <= width:
        return value
    while value and ctx.text_extents(value + "…").x_advance > width:
        value = value[:-1]
    return value + "…"


def render_music(track=None, now=0, artwork=None, *, background_only=False):
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, c.WIDTH, c.HEIGHT)
    ctx = cairo.Context(surface)
    color(ctx, c.BACKGROUND)
    ctx.paint()
    text(ctx, "MÚSICA", 14, 24, 14, c.BLUE, bold=True)
    box(ctx, 14, 32, 212, 1, c.TRACK)
    box(ctx, 64, 41, 112, 112, c.PANEL)
    if artwork is not None:
        x = 120 - artwork.get_width() / 2
        y = 97 - artwork.get_height() / 2
        Gdk.cairo_set_source_pixbuf(ctx, artwork, x, y)
        ctx.paint()
    else:
        visualizer.draw(ctx, visualizer.phase(track, now), *visualizer.BOUNDS[:2])
    if background_only:
        box(ctx, 14, 204, 212, 5, c.TRACK)
        return surface
    title = track.title if track else "Sem reprodução"
    artist = track.artist if track else ""
    text(ctx, fit(ctx, title, 18, 212, True), 14, 177, 18, bold=True)
    text(ctx, fit(ctx, artist, 13, 212), 14, 195, 13, c.MUTED)
    box(ctx, 14, 204, 212, 5, c.TRACK)
    elapsed = track.elapsed(now) if track else 0
    duration = track.duration if track else 0
    if duration:
        box(ctx, 14, 204, 212 * elapsed / duration, 5, c.BLUE)
    text(ctx, stamp(elapsed), 14, 227, 12, c.MUTED)
    text(ctx, stamp(duration, unknown=not duration), 226, 227, 12, c.MUTED, right=True)
    label = track.label if track else "Parado"
    text(ctx, label, 148, 227, 12, c.MUTED, right=True)
    return surface
