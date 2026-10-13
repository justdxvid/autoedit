#!/bin/bash
# Build AutoEdit-for-FilmCraft.zip (on the Desktop) to give to someone else.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$HOME/Desktop}"
TMP=$(mktemp -d); PKG="$TMP/AutoEdit"
mkdir -p "$PKG"
rsync -a --exclude hyperframes/node_modules --exclude hyperframes/package-lock.json --exclude __pycache__ \
      --exclude .keep-in-place --exclude make-package.sh --exclude AutoEdit.app "$SRC/" "$PKG/"
# bundle FilmCraft's command-line tool (MIT/Apache-2.0, licences included) so the installer finds it
CLI=$(ls -d "$HOME"/.local/bin/filmcraft-cli 2>/dev/null && readlink "$HOME/.local/bin/filmcraft-cli" || true)
CLI_DIR=$(dirname "$(readlink "$HOME/.local/bin/filmcraft-cli" 2>/dev/null || echo /nonexistent/x)")
if [ -d "$CLI_DIR" ]; then
  mkdir -p "$PKG/$(basename "$CLI_DIR")"
  cp "$CLI_DIR/filmcraft-cli" "$CLI_DIR"/LICENSE* "$PKG/$(basename "$CLI_DIR")/" 2>/dev/null || true
fi
(cd "$TMP" && rm -f "$OUT/AutoEdit-for-FilmCraft.zip" && zip -qry "$OUT/AutoEdit-for-FilmCraft.zip" AutoEdit)
rm -rf "$TMP"
ls -lh "$OUT/AutoEdit-for-FilmCraft.zip"
