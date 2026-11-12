#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -x .venv/bin/python3 ]; then
  .venv/bin/python3 "Programi Sil.py" --include-state
else
  python3 "Programi Sil.py" --include-state
fi
