@echo off
setlocal

set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set "EDGE_PROFILE=D:\BossAutoGreeterProfile"

if not exist "%EDGE_EXE%" (
  echo Edge executable not found:
  echo %EDGE_EXE%
  pause
  exit /b 1
)

start "" "%EDGE_EXE%" --remote-debugging-port=9222 --user-data-dir="%EDGE_PROFILE%"
echo Edge started with remote debugging port 9222.
echo Profile directory: %EDGE_PROFILE%
pause
