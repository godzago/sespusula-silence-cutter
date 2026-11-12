#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
MODE="${1:---build}"
case "$MODE" in --build|--run|--verify|--test) ;; *) echo "Gecersiz islem"; exit 1 ;; esac
mkdir -p .build
LOG="$PWD/.build/son-islem.log"
exec > >(tee "$LOG") 2>&1
finish() {
  result=$?
  if [ "$result" -ne 0 ]; then
    echo "Islem tamamlanamadi. Hata kaydi: $LOG"
    read -r -p "Kapatmak icin Enter..." _unused || true
  fi
  exit "$result"
}
trap finish EXIT
PY=""
for candidate in /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 /opt/homebrew/bin/python3.11 python3.11; do
  resolved="$(command -v "$candidate" 2>/dev/null || true)"
  if [ -n "$resolved" ] && /usr/bin/arch -arm64 "$resolved" -c 'import sys,platform,tkinter; assert sys.version_info[:2]==(3,11); assert platform.machine()=="arm64"' >/dev/null 2>&1; then
    PY="$resolved"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Bir kez: python.org adresinden Tk iceren Python 3.11 macOS universal2 yukleyicisini kurun."
  echo "Bu yalnizca uygulamayi olusturmak icindir. Olusan .app ayri Python istemez."
  exit 1
fi
if [ "$MODE" = --test ]; then
  /usr/bin/arch -arm64 "$PY" setup_mac.py --verify
  .venv/bin/python3 -m unittest discover -s tests -v
else
  /usr/bin/arch -arm64 "$PY" setup_mac.py "$MODE"
fi
