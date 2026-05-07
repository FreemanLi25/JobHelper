@echo off
setlocal
cd /d "%~dp0"

REM Install dependencies
python -m pip install -r requirements.txt

REM Build a single-file Windows exe without a console window
python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --noconsole ^
  --name BossAutoGreeter ^
  --clean ^
  --collect-data customtkinter ^
  --collect-all DrissionPage ^
  main.py

echo.
echo Build finished: %CD%\dist\BossAutoGreeter.exe
pause
