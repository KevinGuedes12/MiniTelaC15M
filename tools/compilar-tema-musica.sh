#!/usr/bin/env bash
# Compila a cópia local do tema. O script não escreve na minitela.
set -euo pipefail
if [[ $# != 1 ]]; then
  printf 'Uso: bash %s DIRETORIO_PREPARADO\n' "$0" >&2
  exit 2
fi
work="$(realpath -- "$1")"
test -s "$work/musica.zip"
mkdir -p -- "$work/compiler"
app="$work/compiler/MiniPanel.AppImage"
install -m 0700 "$work/usr/share/minitela/resources/MiniPanel-0.1.6.AppImage" "$app"
cd "$work/compiler"
if [[ ! -f squashfs-root/resources/IDE_utils/Gen/AHMISimGenDemo_og.exe ]]; then
  "$app" --appimage-extract 'resources/IDE_utils/*' > extraction.log
fi
cd squashfs-root/resources/IDE_utils/Gen
export WINEPREFIX="$work/wine-prefix" WINEDEBUG=-all WINEDLLOVERRIDES='mscoree,mshtml='
output="$(mktemp -d "$work/tema.XXXXXX")"
printf 13 | wine ./AHMISimGenDemo_og.exe -f "$work/musica.zip" -m 2 -c 0 -e 0 -d 1 -o "$output"
test -s "$output/Texture.acf"
printf '\nTema de música gerado: %s\n' "$output/Texture.acf"
