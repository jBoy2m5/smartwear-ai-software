@echo off
setlocal
cd /d "%~dp0"

if not defined SMARTWEAR_PORT set "SMARTWEAR_PORT=8000"
where docker >nul 2>&1
if errorlevel 1 (
  echo Docker CLI was not found. Install and open Docker Desktop, then try again.
  pause
  exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Engine is not running. Open Docker Desktop and wait for Engine running.
  pause
  exit /b 1
)

echo Building SmartWear from this repository. The first build needs Internet.
docker build --platform linux/amd64 -f Dockerfile.judge -t smartwear-judge:1.0.0 .
if errorlevel 1 goto failed

echo Starting SmartWear on port %SMARTWEAR_PORT%...
docker compose -f compose.judge.yaml up -d --pull never --no-build
if errorlevel 1 goto failed

echo Waiting for SmartWear to become ready...
for /l %%i in (1,1,60) do (
  powershell.exe -NoProfile -Command "try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:%SMARTWEAR_PORT%/ready' -TimeoutSec 3; if ($r.status -eq 'ready') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 goto ready
  timeout /t 2 /nobreak >nul
)
echo SmartWear did not become ready. Check the Docker logs below.
docker compose -f compose.judge.yaml logs --tail 60 smartwear
pause
exit /b 1

:ready
echo SmartWear is ready: http://localhost:%SMARTWEAR_PORT%
start "" "http://localhost:%SMARTWEAR_PORT%"
pause
exit /b 0

:failed
echo Docker build or startup failed. Read the first error above.
pause
exit /b 1
