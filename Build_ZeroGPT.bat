@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pyinstaller --noconfirm --clean --windowed --name ZeroGPT app.py
echo.
echo Build complete: dist\ZeroGPT\ZeroGPT.exe
pause
