"""Formatação compartilhada pela prévia e pelo serviço da minitela."""


def percent(value):
    return "N/D" if value is None else f"{value:.0f}%"


def speed_label(speed):
    if speed is None:
        return ""
    for unit in ("B/s", "kB/s", "MB/s", "GB/s"):
        if speed < 1000 or unit == "GB/s":
            return f"{speed:.0f} {unit}"
        speed /= 1000


def stamp(microseconds, *, unknown=False):
    if unknown:
        return "--:--"
    minutes, seconds = divmod(microseconds // 1_000_000, 60)
    return f"{minutes}:{seconds:02d}"
