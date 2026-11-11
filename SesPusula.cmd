@echo off
setlocal
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
start "" "%~dp0.runtime\pythonw.exe" "%~dp0Baslat.pyw"
