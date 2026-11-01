#!/usr/bin/env bash
# Build Bun Afaka from the SVG drawings in source/ into dist/{otf,ttf,woff2}.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=".venv"
if [ ! -d "$VENV" ]; then
  echo "==> creating $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q fonttools svgpathtools brotli uharfbuzz picosvg
fi

echo "==> building"
"$VENV/bin/python" scripts/build_font.py

echo "==> checking shaping"
"$VENV/bin/python" scripts/check_shaping.py
