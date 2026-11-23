"""Codificação offline de texturas AHMI em blocos de modo 0.

Formato descrito em https://github.com/caio-imperial/minitela-r15/blob/main/RE-acf.md
"""

import sys

import cairo

from .config import HEIGHT, WIDTH

BLOCK_BYTES = 16


def encode_block(pixels):
    """Compacta 16 pixels RGB opacos com dois extremos e pesos de 4 bits."""
    channels = list(zip(*pixels))
    axis = max(range(3), key=lambda i: max(channels[i]) - min(channels[i]))
    low = min(pixels, key=lambda pixel: pixel[axis])
    high = max(pixels, key=lambda pixel: pixel[axis])
    difference = tuple(b - a for a, b in zip(low, high))
    square = sum(delta * delta for delta in difference)
    weights = [0] * 16
    if square:
        for index, pixel in enumerate(pixels):
            projection = sum((v - a) * delta
                             for v, a, delta in zip(pixel, low, difference))
            weights[index] = min(15, max(0, round(15 * projection / square)))
    # O último peso usa três bits, pois o quarto cairia no bloco seguinte.
    if weights[-1] > 7:
        low, high = high, low
        weights = [15 - weight for weight in weights]
    endpoints = bytes(value for pair in zip((*low, 255), (*high, 255)) for value in pair)
    block = int.from_bytes(endpoints, "little")
    for index, weight in enumerate(weights):
        block |= weight << (64 + 4 * index)
    return (block << 1).to_bytes(BLOCK_BYTES, "little")


def decode_block(data):
    """Decodifica o formato acima para conferir o quadro antes de empacotá-lo."""
    block = int.from_bytes(data, "little")
    if block & 1:
        raise ValueError("bloco AHMI de modo 1")
    block >>= 1
    endpoints = block.to_bytes(BLOCK_BYTES, "little")[:6]
    return [
        tuple((a * (15 - weight) + b * weight + 7) // 15
              for a, b in zip(endpoints[::2], endpoints[1::2]))
        for weight in ((block >> (64 + 4 * i)) & 15 for i in range(16))
    ]


def positions():
    for y in range(0, HEIGHT, 4):
        for x in range(0, WIDTH, 4):
            yield [(x + dx, y + dy) for dy in range(4) for dx in range(4)]


def encode_surface(surface):
    if (surface.get_width(), surface.get_height(), surface.get_format()) != (
        WIDTH, HEIGHT, cairo.FORMAT_RGB24
    ):
        raise ValueError("esperada superfície Cairo RGB24 de 240×240")
    surface.flush()
    data = surface.get_data()
    stride = surface.get_stride()
    result = bytearray()
    for block in positions():
        pixels = []
        for x, y in block:
            offset = y * stride + x * 4
            value = int.from_bytes(data[offset:offset + 4], sys.byteorder)
            pixels.append(((value >> 16) & 255, (value >> 8) & 255, value & 255))
        result.extend(encode_block(pixels))
    return bytes(result)


def preview(texture):
    if len(texture) != WIDTH * HEIGHT:
        raise ValueError("tamanho de textura AHMI 240×240 inválido")
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, WIDTH, HEIGHT)
    data, stride = surface.get_data(), surface.get_stride()
    for index, block in enumerate(positions()):
        start = index * BLOCK_BYTES
        for (x, y), (red, green, blue) in zip(
            block, decode_block(texture[start:start + BLOCK_BYTES])
        ):
            offset = y * stride + x * 4
            value = (red << 16) | (green << 8) | blue
            data[offset:offset + 4] = value.to_bytes(4, sys.byteorder)
    surface.mark_dirty()
    return surface
