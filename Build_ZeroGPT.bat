@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ZeroGPT Builder

if not exist ".venv\Scripts\python.exe" (
  echo ZeroGPT environment not found. Run Install_ZeroGPT.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

if exist build rmdir /s /q build
if exist dist\ZeroGPT rmdir /s /q dist\ZeroGPT

pyinstaller --noconfirm --clean --windowed --onedir ^
  --name ZeroGPT ^
  --collect-all markdown ^
  --collect-all PySide6 ^
  app.py
if errorlevel 1 goto :fail

echo.
echo Build complete:
echo   %CD%\dist\ZeroGPT\ZeroGPT.exe
echo.
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1
