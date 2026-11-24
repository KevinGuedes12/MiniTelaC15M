"""Monta offline um projeto editável AHMI para os widgets do dashboard."""

from copy import deepcopy
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import cairo

from . import config as c, visualizer
from .render import box, render
from .registers import BARS, BAR_LEVELS, FIELDS, MUSIC_BARS, MUSIC_FIELDS, VISUALIZER


def png(surface):
    image = BytesIO()
    surface.write_to_png(image)
    return image.getvalue()


def rgba(hex_color):
    values = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "rgba({},{},{},1)".format(*values)


def place(widget, field, index, page):
    x, y, width, height = field.bounds
    widget.update(id=f"{page}.0.0.{index}", wId=index, name=field.name,
                  tag=field.name, zIndex=index + 1)
    widget.pop("$$hashKey", None)
    widget.pop("refID", None)
    widget["info"].update(left=x, top=y, absoluteLeft=x, absoluteTop=y,
                          width=width, height=height)
    return widget


def widgets(project, page, templates, prefix, assets, fields, bars, animations=()):
    page_id = page["id"]
    layer = page["canvasList"][0]["subCanvasList"][0]
    layer["widgetList"] = []
    tags = {t["name"]: t for t in project["tagList"]}
    used = {t["indexOfRegister"] for t in tags.values()}
    for index, field in enumerate(fields + bars + animations):
        numeric = field in bars or field in animations
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
            levels = len(visualizer.HEIGHTS) if field == VISUALIZER else BAR_LEVELS + 1
            for level in range(levels):
                name = f"r-{page_id}-0-0-{index}-{level}.png"
                if field == VISUALIZER:
                    assets[name] = png(visualizer.surface(level))
                else:
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
        layer["widgetList"].append(place(widget, field, index, page_id))


def build(source, destination, *, music=False):
    with ZipFile(source) as original:
        project = json.loads(original.read("data.json"))
        if project["size"] != {"width": 240, "height": 240}:
            raise ValueError("o projeto AHMI precisa ter resolução 240×240")
        pages = {page["id"]: page for page in project["pageList"]}
        templates = {
            widget.get("tag"): widget
            for parent in pages["2"]["canvasList"]
            for child in parent["subCanvasList"]
            for widget in child["widgetList"]
        }
        prefix = f'/project/{project["projectId"]}/resources/'
        assets = {"r-4-0.png": png(render())}
        pages["4"]["backgroundImage"] = prefix + "r-4-0.png"
        widgets(project, pages["4"], templates, prefix, assets, FIELDS, BARS)
        if music:
            from .music_render import render_music

            assets["r-5-0.png"] = png(render_music(background_only=True))
            pages["5"].update(name="Music", backgroundImage=prefix + "r-5-0.png")
            widgets(project, pages["5"], templates, prefix, assets, MUSIC_FIELDS, MUSIC_BARS, (VISUALIZER,))
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
    parser.add_argument("--music", action="store_true", help="inclui a página de música")
    args = parser.parse_args()
    build(args.source, args.destination, music=args.music)
