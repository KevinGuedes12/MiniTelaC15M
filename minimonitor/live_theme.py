"""Monta offline um projeto editável AHMI para os widgets do dashboard."""

from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import cairo

from . import config as c
from .render import box, render


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


def png(surface):
    image = BytesIO()
    surface.write_to_png(image)
    return image.getvalue()


def rgba(hex_color):
    values = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "rgba({},{},{},1)".format(*values)


def place(widget, field, index):
    x, y, width, height = field.bounds
    widget.update(id=f"4.0.0.{index}", wId=index, name=field.name,
                  tag=field.name, zIndex=index + 1)
    widget.pop("$$hashKey", None)
    widget.pop("refID", None)
    widget["info"].update(left=x, top=y, absoluteLeft=x, absoluteTop=y,
                          width=width, height=height)
    return widget


def build(source, destination):
    with ZipFile(source) as original:
        project = json.loads(original.read("data.json"))
        assert project["size"] == {"width": 240, "height": 240}
        pages = {page["id"]: page for page in project["pageList"]}
        canvas = pages["4"]["canvasList"][0]
        layer = canvas["subCanvasList"][0]
        templates = {
            widget.get("tag"): widget
            for parent in pages["2"]["canvasList"]
            for child in parent["subCanvasList"]
            for widget in child["widgetList"]
        }
        prefix = f'/project/{project["projectId"]}/resources/'
        assets = {"r-4-0.png": png(render())}
        pages["4"]["backgroundImage"] = prefix + "r-4-0.png"
        layer["widgetList"] = []
        tags = {t["name"]: t for t in project["tagList"]}
        used = {t["indexOfRegister"] for t in tags.values()}
        for index, field in enumerate(FIELDS + BARS):
            numeric = field in BARS
            if field.register in used or field.name in tags:
                raise ValueError(f"registro duplicado: {field.register}")
            base_tag = tags["Battery_Type" if numeric else "Wifi_SSID"]
            tag = deepcopy(base_tag)
            tag.pop("_indexOfRegister", None)
            tag.update(name=field.name, showName={"en": field.name, "zh": field.name},
                       indexOfRegister=field.register)
            if numeric:
                tag.update(initValue=0)
            project["tagList"].append(tag)

            if numeric:
                widget = deepcopy(templates["Battery_Type"])
                slices = widget["texList"][0]["slices"]
                template = deepcopy(slices[0])
                slices.clear()
                for level in range(BAR_LEVELS + 1):
                    name = f"r-4-0-0-{index}-{level}.png"
                    width, height = field.bounds[2:]
                    strip = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
                    ctx = cairo.Context(strip)
                    box(ctx, 0, 0, width, height, c.TRACK)
                    box(ctx, 0, 0, round(width * level / BAR_LEVELS), height, field.color)
                    assets[name] = png(strip)
                    frame = deepcopy(template)
                    frame.update(imgName=name, id=name, imgSrc=prefix + name, originSrc=prefix + name)
                    slices.append(frame)
            else:
                widget = deepcopy(templates["Wifi_SSID" if field.compact else "dateHour"])
                widget["info"].update(text=field.initial, fontColor=rgba(field.color),
                                      align=field.align)
            layer["widgetList"].append(place(widget, field, index))
        with ZipFile(destination, "x", ZIP_DEFLATED) as output:
            for name in original.namelist():
                if name != "data.json" and name not in assets:
                    output.writestr(name, original.read(name))
            output.writestr("data.json", json.dumps(project, ensure_ascii=False))
            for name, image in assets.items():
                output.writestr(name, image)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    build(args.source, args.destination)
