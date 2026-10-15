@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ZeroGPT Installer
color 0A

echo.
echo  ==================================================
echo           ZeroGPT - One Click Windows Setup
echo  ==================================================
echo.

where winget >nul 2>nul
if errorlevel 1 (
  echo ERROR: Windows App Installer ^(winget^) was not found.
  echo Install "App Installer" from Microsoft Store and run this again.
  pause
  exit /b 1
)

where py >nul 2>nul
if errorlevel 1 (
  echo [1/3] Installing Python 3.12...
  winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :fail
) else (
  echo [1/3] Python launcher detected.
)

echo [2/3] Preparing ZeroGPT...
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto :fail
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [3/3] Launching ZeroGPT...
start "ZeroGPT" "%CD%\.venv\Scripts\pythonw.exe" "%CD%\app.py"
echo.
echo ZeroGPT is launching.
echo Click "Install / Repair Local AI" once inside the app to download
 echo Ollama, the default chat model, ComfyUI, and the image model.
echo.
exit /b 0

:fail
echo.
echo ZeroGPT setup failed. Review the error above, then run this file again.
pause
exit /b 1
