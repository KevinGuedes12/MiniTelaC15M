"""Definições AHMI compartilhadas pelo tema e pelos atualizadores."""

from dataclasses import dataclass

from . import config as c, visualizer


@dataclass(frozen=True)
class Field:
    name: str
    register: int
    bounds: tuple[int, int, int, int]
    color: str
    initial: str
    align: str = "left"
    compact: bool = False


FIELDS = (
    Field("Clock", 2200, (158, 7, 68, 25), c.TEXT, "N/D", "right"),
    Field("Cpu", 2201, (154, 41, 72, 24), c.TEXT, "N/D", "right"),
    Field("Ram", 2202, (154, 84, 72, 24), c.TEXT, "N/D", "right"),
    Field("Battery", 2203, (23, 151, 85, 25), c.GREEN, "N/D"),
    Field("Charge", 2204, (23, 178, 89, 18), c.MUTED, "N/D", compact=True),
    Field("Temperature", 2205, (133, 151, 86, 25), c.ORANGE, "N/D"),
    Field("Wifi", 2206, (50, 213, 102, 21), c.MUTED, "N/D", compact=True),
    Field("Rate", 2207, (154, 213, 72, 21), c.MUTED, "", "right", True),
)
BARS = (
    Field("CpuBar", 2208, (14, 68, 212, 5), c.BLUE, ""),
    Field("RamBar", 2209, (14, 111, 212, 5), c.PURPLE, ""),
)
BAR_LEVELS = 10
MUSIC_FIELDS = (
    Field("TrackTitle", 2220, (14, 155, 212, 25), c.TEXT, " ", compact=True),
    Field("TrackArtist", 2221, (14, 181, 212, 19), c.MUTED, " ", compact=True),
    Field("TrackTime", 2222, (14, 213, 108, 21), c.MUTED, "--:--", compact=True),
    Field("TrackStatus", 2223, (124, 213, 102, 21), c.TEXT, "Pausado", "right", True),
)
MUSIC_BARS = (Field("TrackProgress", 2224, (14, 204, 212, 5), c.BLUE, ""),)
VISUALIZER = Field("MusicVisualizer", 2225, visualizer.BOUNDS, c.BLUE, "")
