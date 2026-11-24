#!/usr/bin/env bash
# Extrai apenas os arquivos necessários e gera um ZIP de tema, sem usar a USB.
set -euo pipefail
if [[ $# != 2 ]]; then
  printf 'Uso: bash %s PACOTE.deb DIRETORIO_NOVO\n' "$0" >&2
  exit 2
fi
package="$(realpath -- "$1")"
project="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -- "$2"
work="$(realpath -- "$2")"
ar p "$package" data.tar.xz | bsdtar -xf - -C "$work" \
  './usr/share/minitela/resources/ACF/file.zip' \
  './usr/share/minitela/resources/MiniPanel-0.1.6.AppImage' \
  './usr/share/minitela/resources/gifs_imagens/img1.jpg' \
  './usr/share/minitela/resources/gifs_imagens/img2.jpg' \
  './usr/share/minitela/resources/gifs_imagens/img3.jpg'
resources="$work/usr/share/minitela/resources"
for slot in 1 2 3; do
  ffmpeg -v error -i "$resources/gifs_imagens/img$slot.jpg" \
    -vf 'scale=240:240,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=none' \
    -frames:v 1 "$work/slot$slot.gif"
done
python - "$resources/ACF/file.zip" "$work" <<'PY'
from pathlib import Path
from sys import argv
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(argv[2])
slots = ("1i1h1e37393671471.gif", "1h1k1e37393671464.gif", "1h1m1e37393671466.gif")
images = {name: (root / f"slot{index}.gif").read_bytes() for index, name in enumerate(slots, 1)}
with ZipFile(argv[1]) as source, ZipFile(root / "base.zip", "x", ZIP_DEFLATED) as output:
    if not images.keys() <= set(source.namelist()):
        raise ValueError("os slots do pacote não correspondem ao projeto C15M")
    for name in source.namelist():
        output.writestr(name, images[name] if name in images else source.read(name))
PY
cd "$project"
python -m minimonitor.live_theme "$work/base.zip" "$work/musica.zip" --music
printf 'Projeto de tema gerado: %s\n' "$work/musica.zip"
