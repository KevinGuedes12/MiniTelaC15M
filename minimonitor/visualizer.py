"""Quadros decorativos que não precisam capturar áudio."""

from . import config as c

BOUNDS = (64, 55, 112, 84)
HEIGHTS = (
    (10, 10, 10, 10, 10, 10, 10),
    (20, 42, 30, 64, 48, 32, 22),
    (37, 25, 56, 40, 63, 24, 35),
    (22, 46, 62, 33, 45, 55, 26),
    (36, 60, 35, 52, 26, 44, 20),
    (26, 33, 49, 61, 35, 25, 39),
)
COLORS = (c.BLUE, c.BLUE, "#75ADFF", "#8F9CFF", "#AA8CFF", "#A88CFF", "#AC91FF")


def phase(track, now):
    if track is None or not track.playing:
        return 0
    seconds = track.elapsed(now) // 1_000_000
    return 1 + seconds % (len(HEIGHTS) - 1)


def draw(ctx, index, x, y):
    from .render import box

    _, _, width, height = BOUNDS
    box(ctx, x, y, width, height, c.PANEL)
    for n, (bar, shade) in enumerate(zip(HEIGHTS[index], COLORS)):
        box(ctx, x + 11 + n * 13, y + (height - bar) // 2, 10, bar, shade)


def surface(index):
    import cairo

    _, _, width, height = BOUNDS
    frame = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    draw(cairo.Context(frame), index, 0, 0)
    return frame
