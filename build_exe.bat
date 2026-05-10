@echo off
setlocal
cd /d "%~dp0"

REM Build in an isolated virtual environment to avoid polluted global/conda packages.
set "VENV_DIR=.venv_pack"
set "USERPROFILE=C:\tmp"
set "HOME=C:\tmp"
set "APPDATA=C:\tmp"
set "LOCALAPPDATA=C:\tmp"
set "PYTHONNOUSERSITE=1"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  python -m venv "%VENV_DIR%"
)

"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt

REM Build a single-file Windows exe without a console window
"%VENV_DIR%\Scripts\python.exe" -m PyInstaller ^
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
