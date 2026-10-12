@echo off
setlocal
echo SmartWear Judge: build, verify and export Docker image
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-judge.ps1"
set "build_result=%errorlevel%"
echo.
if not "%build_result%"=="0" echo Build failed. Please send the last error shown above.
if "%build_result%"=="0" echo Build passed. The package is under release\SmartWear-Judge-1.0.0.
pause
exit /b %build_result%
