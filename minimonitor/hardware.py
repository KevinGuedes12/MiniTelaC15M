"""Identificação passiva do candidato USB CDC na árvore sysfs."""

import os
import stat
from pathlib import Path


def candidates():
    for entry in sorted(Path("/sys/class/tty").glob("ttyACM*")):
        try:
            ancestors = entry.resolve(strict=True).parents
            usb = next(parent for parent in ancestors if (parent / "idVendor").is_file())
            vendor = (usb / "idVendor").read_text().strip()
            product = (usb / "idProduct").read_text().strip()
            device_number = (entry / "dev").read_text().strip()
        except (OSError, StopIteration):
            continue
        if (vendor, product) != ("0324", "0324"):
            continue
        yield usb.name, Path("/dev") / entry.name, device_number


def matches(metadata, device_number):
    major, minor = os.major(metadata.st_rdev), os.minor(metadata.st_rdev)
    return stat.S_ISCHR(metadata.st_mode) and f"{major}:{minor}" == device_number


def report():
    ready = False
    ports = list(candidates())
    for usb, node, device_number in ports:
        print(f"USB {usb} 0324:0324 → {node} ({device_number})")
        try:
            metadata = node.stat()
        except OSError as exc:
            print(f"  Caminho indisponível: {exc.strerror}.")
            continue
        if not matches(metadata, device_number):
            print("  O caminho não corresponde ao dispositivo registrado no sysfs.")
            continue
        accessible = os.access(node, os.R_OK | os.W_OK)
        ready |= accessible
        print("  Permissões aparentes de leitura e escrita: "
              + ("disponíveis." if accessible else "indisponíveis."))
    if not ports:
        print("Nenhuma porta USB CDC 0324:0324 encontrada no sysfs.")
    return 0 if ready else 1
