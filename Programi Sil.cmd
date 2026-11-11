@echo off
setlocal
cd /d "%~dp0"
if exist ".runtime\pythonw.exe" (
  ".runtime\pythonw.exe" "Programi Sil.py"
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "Programi Sil.py"
) else (
  py -3 "Programi Sil.py"
)
