@echo off
setlocal

set "EDGE_EXE="
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
  set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)
if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" (
  set "EDGE_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
)
set "EDGE_PROFILE=C:\tmp\BossAutoGreeterProfile"
if not exist "C:\tmp" mkdir "C:\tmp"

if not "%EDGE_EXE%"=="" goto edge_found

echo Edge executable not found:
echo C:\Program Files ^(x86^)\Microsoft\Edge\Application\msedge.exe
echo C:\Program Files\Microsoft\Edge\Application\msedge.exe
pause
exit /b 1

:edge_found

if not exist "%EDGE_PROFILE%" (
  mkdir "%EDGE_PROFILE%"
)

call :start_edge
call :check_port
if "%PORT_OK%"=="1" goto success

echo.
echo Edge did not expose port 9222.
echo This is usually caused by existing Edge background processes.
echo.
choice /C YN /M "Close all existing Edge processes and restart debug Edge"
if errorlevel 2 goto fail

taskkill /IM msedge.exe /F >nul 2>nul
timeout /t 2 /nobreak >nul
call :start_edge
call :check_port
if "%PORT_OK%"=="1" goto success

goto fail

:start_edge
echo.
echo Starting Edge with remote debugging:
echo "%EDGE_EXE%" --remote-debugging-port=9222 --user-data-dir="%EDGE_PROFILE%" --no-first-run --no-default-browser-check --disable-gpu --no-sandbox --new-window https://www.zhipin.com/
start "" "%EDGE_EXE%" --remote-debugging-port=9222 --user-data-dir="%EDGE_PROFILE%" --no-first-run --no-default-browser-check --disable-gpu --no-sandbox --new-window https://www.zhipin.com/
timeout /t 3 /nobreak >nul
exit /b 0

:check_port
set "PORT_OK=0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:9222/json/version' -TimeoutSec 2; if ($r.Browser) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 set "PORT_OK=1"
exit /b 0

:success
echo.
echo Success: Edge remote debugging port 9222 is ready.
echo Profile directory: %EDGE_PROFILE%
echo Now open BossAutoGreeter.exe and click test connection.
pause
exit /b 0

:fail
echo.
echo Failed: port 9222 is still not ready.
echo Try disabling Edge Startup boost, then run this file again:
echo Edge Settings - System and performance - Startup boost - Off
echo.
pause
exit /b 1
