"""Renderização de um quadro RGB de 240×240 em uma superfície Cairo."""

import cairo

from . import config as c
from .presentation_values import percent, speed_label


def color(ctx, value):
    ctx.set_source_rgb(*(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def box(ctx, x, y, width, height, fill):
    color(ctx, fill)
    ctx.rectangle(x, y, width, height)
    ctx.fill()


def text(ctx, value, x, baseline, size, fill=c.TEXT, *, bold=False, right=False):
    color(ctx, fill)
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    if right:
        extents = ctx.text_extents(value)
        x -= extents.x_bearing + extents.width
    ctx.move_to(x, baseline)
    ctx.show_text(value)


def metric(ctx, name, value, y, accent):
    text(ctx, name, 35 if name == "CPU" else 14, y, 14, c.MUTED, bold=True)
    text(ctx, percent(value), 226, y, 21, bold=True, right=True)
    box(ctx, 14, y + 8, 212, 5, c.TRACK)
    if value is not None:
        box(ctx, 14, y + 8, 212 * min(100, max(0, value)) / 100, 5, accent)


def cpu_icon(ctx):
    color(ctx, c.BLUE)
    ctx.set_line_width(1)
    ctx.rectangle(17.5, 48.5, 10, 10)
    ctx.rectangle(20.5, 51.5, 4, 4)
    for x in (19.5, 22.5, 25.5):
        ctx.move_to(x, 46)
        ctx.line_to(x, 48)
        ctx.move_to(x, 59)
        ctx.line_to(x, 61)
    ctx.stroke()


def render(metrics=None):
    """Sem métricas, gera o fundo fixo para os widgets da minitela."""
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, c.WIDTH, c.HEIGHT)
    ctx = cairo.Context(surface)
    color(ctx, c.BACKGROUND)
    ctx.paint()

    text(ctx, "ARCH", 14, 27, 19, c.BLUE, bold=True)
    if metrics is not None:
        text(ctx, metrics.clock, 226, 27, 18, bold=True, right=True)
    box(ctx, 14, 37, 212, 1, c.TRACK)

    cpu_icon(ctx)
    if metrics is None:
        text(ctx, "CPU", 35, 60, 14, c.MUTED, bold=True)
        text(ctx, "RAM", 14, 103, 14, c.MUTED, bold=True)
        box(ctx, 14, 68, 212, 5, c.TRACK)
        box(ctx, 14, 111, 212, 5, c.TRACK)
    else:
        metric(ctx, "CPU", metrics.cpu, 60, c.BLUE)
        metric(ctx, "RAM", metrics.ram, 103, c.PURPLE)

    for x in (14, 124):
        box(ctx, x, 130, 102, 70, c.PANEL)
    text(ctx, "BATERIA", 23, 147, 11, c.MUTED, bold=True)
    text(ctx, "TEMP. CPU", 133, 147, 11, c.MUTED, bold=True)
    box(ctx, 14, 210, 212, 1, c.TRACK)
    if metrics is None:
        text(ctx, "Wi-Fi", 14, 228, 12, c.MUTED)
        return surface

    text(ctx, percent(metrics.battery), 23, 173, 23, c.GREEN, bold=True)
    text(ctx, metrics.battery_status, 23, 190, 11, c.MUTED)
    temperature = "N/D" if metrics.temperature is None else f"{metrics.temperature:.0f} °C"
    text(ctx, temperature, 133, 175, 22, c.ORANGE, bold=True)

    state = {True: "Conectado", False: "Desconectado", None: "N/D"}[metrics.wifi]
    text(ctx, f"Wi-Fi · {state}", 14, 228, 12, c.MUTED)
    text(ctx, speed_label(metrics.wifi_bytes_per_second), 226, 228, 12, c.MUTED, right=True)
    return surface
