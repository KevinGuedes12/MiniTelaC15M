"""Cache de capas, com leitura limitada e download fora do loop GTK."""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib

LIMIT = 4 * 1024 * 1024
CACHE_SIZE = 16
ART_SIZE = 112


def load_art(url):
    uri = urlsplit(url)
    if uri.scheme == "file" and uri.netloc in ("", "localhost"):
        stream = Path(unquote(uri.path)).open("rb")
    elif uri.scheme in ("http", "https"):
        stream = urlopen(url, timeout=3)
    else:
        return None
    with stream:
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        return None
    decoder = GdkPixbuf.PixbufLoader.new()

    def resize(loader, width, height):
        scale = min(ART_SIZE / width, ART_SIZE / height, 1)
        loader.set_size(max(1, round(width * scale)), max(1, round(height * scale)))

    decoder.connect("size-prepared", resize)
    try:
        decoder.write(data)
        decoder.close()
        return decoder.get_pixbuf()
    except GLib.Error:
        # Alguns ambientes restringem o decodificador externo do GdkPixbuf.
        # O FFmpeg recebe apenas os bytes já lidos, com entrada e saída por pipe.
        try:
            result = subprocess.run(
                ["ffmpeg", "-v", "error", "-protocol_whitelist", "pipe", "-i", "pipe:0",
                 "-vf", f"scale={ART_SIZE}:{ART_SIZE}:force_original_aspect_ratio=decrease,"
                 f"pad={ART_SIZE}:{ART_SIZE}:(ow-iw)/2:(oh-ih)/2:color=0x111D2C",
                 "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                input=data, capture_output=True, timeout=3, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        pixels = result.stdout
        if result.returncode or len(pixels) != ART_SIZE * ART_SIZE * 3:
            return None
        return GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(pixels), GdkPixbuf.Colorspace.RGB, False, 8,
            ART_SIZE, ART_SIZE, ART_SIZE * 3,
        )


class Artwork:
    def __init__(self, changed):
        self.changed = changed
        self.cache = OrderedDict()
        self.pending = None
        self.wanted = None
        self.closed = False
        self.worker = ThreadPoolExecutor(max_workers=1)

    def get(self, url):
        if not url:
            self.wanted = None
            return None
        if url in self.cache:
            self.wanted = None
            self.cache.move_to_end(url)
            return self.cache[url]
        self.wanted = url
        if self.pending is None and not self.closed:
            self.pending = self.worker.submit(load_art, url)
            self.pending.add_done_callback(lambda task: GLib.idle_add(self._complete, url, task))
        return None

    def _complete(self, url, task):
        self.pending = None
        if self.closed:
            return GLib.SOURCE_REMOVE
        try:
            pixbuf = task.result()
        except (OSError, ValueError, GLib.Error):
            pixbuf = None
        self.cache[url] = pixbuf
        while len(self.cache) > CACHE_SIZE:
            self.cache.popitem(last=False)
        if self.wanted is not None:
            self.changed()
        return GLib.SOURCE_REMOVE

    def close(self):
        self.closed = True
        self.worker.shutdown(wait=False, cancel_futures=True)
