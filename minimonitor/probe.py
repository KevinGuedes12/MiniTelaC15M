"""Consulta AHMI, baseada nos comandos de estado documentados para o R15M."""

from contextlib import contextmanager
import fcntl
import os
import select
import struct
import sys
import termios
import tty
from time import monotonic

from .hardware import candidates, matches


def response(fd, command, expected, content=b"", *, timeout=2, buffer=None):
    if buffer is None:
        buffer = bytearray()
    until = monotonic() + timeout
    if command is not None:
        packet = struct.pack(">2sHH", b"AH", len(content) + 2, command) + content + b"\0\0MI"
        pending = memoryview(packet)
        while pending:
            remaining = until - monotonic()
            if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
                raise TimeoutError("tempo esgotado no envio serial")
            try:
                written = os.write(fd, pending)
            except BlockingIOError:
                continue
            if written == 0:
                raise OSError("envio serial interrompido")
            pending = pending[written:]
    while True:
        while len(buffer) >= 4:
            start = buffer.find(b"AH")
            if start < 0:
                del buffer[:-1]
                break
            del buffer[:start]
            if len(buffer) < 4:
                break
            length = int.from_bytes(buffer[2:4], "big") & 0x7FFF
            if length < 2:
                del buffer[:2]
                continue
            end = length + 8
            if len(buffer) < end:
                break
            if buffer[end - 2:end] != b"MI":
                del buffer[:2]
                continue
            reply = int.from_bytes(buffer[4:6], "big")
            payload = bytes(buffer[6:4 + length])
            del buffer[:end]
            if reply == expected:
                return payload
        remaining = until - monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            break
        try:
            chunk = os.read(fd, 4096)
        except BlockingIOError:
            continue
        if not chunk:
            break
        buffer.extend(chunk)
    raise TimeoutError(f"sem resposta AHMI 0x{expected:04x}")


def query(fd, *, buffer=None):
    handshake = response(fd, 0x0080, 0x00C0, buffer=buffer)
    if len(handshake) < 4:
        raise ValueError("resposta de handshake incompleta")
    status = response(fd, 0x0085, 0x00C5, buffer=buffer)
    if len(status) < 21:
        raise ValueError("resposta de estado incompleta")
    return (
        int.from_bytes(handshake[:4], "big"),
        status[0], status[1:17].hex(), int.from_bytes(status[17:21], "big"),
    )


def whatsapp_test(fd):
    message = b"MiniMonitor teste"
    content = struct.pack(">BHH", 0xD0, 1141, len(message)) + message
    return response(fd, 0x0090, 0x00D0, content)


def select_dashboard_page(fd):
    # Página AHMI 4 abriu Clima (índice 3 no projeto); tenta Imagens em 5.
    content = struct.pack(">BHI", 0x80, 2, 5)
    return response(fd, 0x0090, 0x00D0, content)


@contextmanager
def serial_device():
    ports = list(candidates())
    if len(ports) != 1:
        raise OSError("é necessária uma única porta USB CDC 0324:0324")
    _, node, device_number = ports[0]
    if not matches(node.stat(), device_number):
        raise OSError("o caminho diverge do dispositivo registrado no sysfs")
    fd = os.open(node, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if not matches(os.fstat(fd), device_number):
            raise OSError("o dispositivo mudou durante a abertura")
        fcntl.ioctl(fd, termios.TIOCEXCL)
        original = termios.tcgetattr(fd)
        try:
            attrs = termios.tcgetattr(fd)
            tty.cfmakeraw(attrs)
            attrs[2] &= ~(termios.CSTOPB | termios.CRTSCTS)
            attrs[2] |= termios.CLOCAL | termios.CREAD
            attrs[4] = attrs[5] = termios.B115200
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            yield fd, node
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSANOW, original)
            except termios.error:
                # A porta pode ter desaparecido após a reinicialização do painel.
                pass
    finally:
        os.close(fd)


def report(*, test_message=False, dashboard_page=False):
    try:
        with serial_device() as (fd, node):
            if dashboard_page:
                result = select_dashboard_page(fd)
            elif test_message:
                result = whatsapp_test(fd)
            else:
                result = query(fd)
    except (OSError, ValueError, termios.error) as exc:
        print(exc, file=sys.stderr)
        return 1
    if dashboard_page:
        print(f"{node} — resposta AHMI à seleção da página 5: {result.hex() or '(sem conteúdo)'}")
        return 0
    if test_message:
        print(f"{node} — resposta AHMI ao teste: {result.hex() or '(sem conteúdo)'}")
        return 0
    packet_size, state, theme, offset = result
    print(f"{node} — AHMI respondeu")
    print(f"Pacote máximo: {packet_size}")
    print(f"Estado: 0x{state:02x}")
    print(f"Identificador do tema: {theme}")
    print(f"Offset: {offset}")
    return 0
