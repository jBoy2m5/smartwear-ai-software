@echo off
setlocal
set "video=%~dp0..\ai\generated_data\reference_samples\01_two_hands_reach_grab\camera.avi"
if not "%~1"=="" set "video=%~1"
if not exist "%video%" (
  echo No local hand video found. Drag a video file onto this script to test it.
  pause
  exit /b 1
)
echo SmartWear Judge: verify real-hand video in an isolated Docker container
echo Video: %video%
if "%~1"=="" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-judge.ps1" -HandVideo "%video%" -RequireBothHands
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-judge.ps1" -HandVideo "%video%"
)
set "verify_result=%errorlevel%"
if not "%verify_result%"=="0" echo Verification failed. Please send the first error above.
if "%verify_result%"=="0" echo Verification passed. Real hand and restart were checked.
pause
exit /b %verify_result%
