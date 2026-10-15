@echo off
setlocal
cd /d "%~dp0"
title ZeroGPT Installer
color 0A

echo.
echo  =========================================
echo          ZeroGPT One-Click Setup
echo  =========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [1/4] Installing Python...
  winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
) else (
  echo [1/4] Python detected.
)

where git >nul 2>nul
if errorlevel 1 (
  echo [2/4] Installing Git...
  winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
) else (
  echo [2/4] Git detected.
)

echo [3/4] Creating ZeroGPT environment...
py -3.12 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [4/4] Launching ZeroGPT...
start "ZeroGPT" .venv\Scripts\pythonw.exe app.py

echo.
echo ZeroGPT is starting. Inside the app, click "Install Local AI" once to download Ollama, the chat model, ComfyUI, and the default image model.
pause
