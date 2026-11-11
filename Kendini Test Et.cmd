@echo off
setlocal
cd /d "%~dp0"
"%~dp0.runtime\python.exe" "%~dp0portable_selftest.py" --require-contained-runtime
pause
