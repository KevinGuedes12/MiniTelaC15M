"""Grava os temas MiniMonitor compilados e conferidos para o C15M."""

from functools import partial
from hashlib import md5, sha256
from pathlib import Path
import struct
import sys
import termios

from .probe import query, response, serial_device

THEME_ADDRESS = 0x08100000
APPROVED_DIGESTS = {
    "de13a91c514becd522a876c0dc262881215b9e97f172b15fccc439bc3bb75fca": "estático",
    "c9917fda8ffc83c546f5cf1e24e81a61f19fa7bd760da1813d6d458e59448bf0": "dinâmico",
    "65a6cc79f5e7d70024cbd50e4359746204359439727de23b967b847a0563057f": "com Música",
    "1a808c143d9f8559d4c83fca3c268689c053916a6943bd13fb1e2c1ef835a816": "com visualizador",
}
BUSY = 0xFFFFFFFF


def word(payload):
    if len(payload) < 4:
        raise ValueError("resposta AHMI incompleta")
    return int.from_bytes(payload[:4], "big")


def upload(fd, data):
    buffer = bytearray()
    exchange = partial(response, fd, buffer=buffer)
    file_id = md5(data, usedforsecurity=False).digest()
    _, state, current_id, offset = query(fd, buffer=buffer)
    print(f"Estado anterior: 0x{state:02x}.", flush=True)
    if state == 0x20 and current_id == file_id.hex():
        print("O dispositivo já informa este tema.")
        return
    if state == 0x20:
        if word(exchange(0x0071, 0x00B1, b"\x10", timeout=5)) != 0:
            raise OSError("a minitela recusou o modo de gravação do tema")
    elif state not in (0x10, 0x11):
        raise OSError(f"estado AHMI inesperado: 0x{state:02x}")

    if current_id != file_id.hex():
        offset = 0
    if offset > len(data):
        raise OSError("offset informado pela minitela fora do tema")

    print("Solicitando gravação da região de tema…", flush=True)
    request = struct.pack(">II", THEME_ADDRESS, len(data)) + file_id
    reply = exchange(0x0081, 0x00C1, request, timeout=60)
    code = word(reply[4:])
    if code == BUSY:
        reply = exchange(None, 0x00C1, timeout=60)
        code = word(reply[4:])
    page = word(reply)
    if code != 0 or not 1 <= page <= 0x7FFF - 6:
        raise OSError(f"gravação recusada ou tamanho inválido: código 0x{code:08x}, página {page}")

    last_progress = -1
    while offset < len(data):
        chunk = data[offset:offset + page]
        payload = struct.pack(">I", offset) + chunk
        code = word(exchange(0x0082, 0x00C2, payload, timeout=5))
        if code == BUSY:
            code = word(exchange(None, 0x00C2, timeout=60))
        if code != 0:
            raise OSError(f"gravação recusada no offset {offset}: código 0x{code:08x}")
        offset += len(chunk)
        progress = offset * 100 // len(data)
        if progress // 10 != last_progress:
            print(f"Tema enviado: {progress}%", flush=True)
            last_progress = progress // 10

    try:
        reply = exchange(0x008F, 0x00CF, timeout=5)
    except OSError as exc:
        raise OSError(f"todos os blocos foram aceitos, mas a finalização não foi confirmada: {exc}") from exc
    if reply and word(reply) != 0:
        raise OSError(f"finalização recusada: 0x{word(reply):08x}")
    print("Finalização confirmada pela minitela.")


def report(path):
    try:
        data = Path(path).read_bytes()
        variant = APPROVED_DIGESTS.get(sha256(data).hexdigest())
        if variant is None:
            raise ValueError("o arquivo não corresponde a um tema MiniMonitor aprovado")
        with serial_device() as (fd, node):
            print(f"Enviando o tema MiniMonitor {variant} a {node}.", flush=True)
            upload(fd, data)
    except (OSError, ValueError, termios.error) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
