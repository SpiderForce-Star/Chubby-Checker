#!/bin/bash
# Ascent Shipper Checker — double-click launcher (macOS)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then
  exec "$ROOT/.venv/bin/python" "$ROOT/tools/gui_launcher.py"
fi
exec python3 "$ROOT/tools/gui_launcher.py"
