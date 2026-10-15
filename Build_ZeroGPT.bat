@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ZeroGPT Portable Builder

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
if exist release\ZeroGPT-Portable rmdir /s /q release\ZeroGPT-Portable
if exist release\ZeroGPT-Portable.zip del /q release\ZeroGPT-Portable.zip

pyinstaller --noconfirm --clean --windowed --onedir ^
  --name ZeroGPT ^
  --collect-all markdown ^
  --collect-all PySide6 ^
  app.py
if errorlevel 1 goto :fail

mkdir release >nul 2>nul
xcopy /E /I /Y "dist\ZeroGPT" "release\ZeroGPT-Portable" >nul

(
  echo ZeroGPT Portable 1.0.1
  echo ======================
  echo.
  echo 1. Run ZeroGPT.exe.
  echo 2. Open Settings and click Install / Repair Local AI once if the AI runtimes are not installed yet.
  echo 3. ZeroGPT chats, images, settings, attachments, and its ComfyUI runtime are stored in the ZeroGPT_Data folder beside the EXE.
  echo.
  echo You can move the entire ZeroGPT-Portable folder anywhere. Keep the folder contents together.
) > "release\ZeroGPT-Portable\README-PORTABLE.txt"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\ZeroGPT-Portable' -DestinationPath 'release\ZeroGPT-Portable.zip' -CompressionLevel Optimal -Force"
if errorlevel 1 goto :fail

echo.
echo Portable build complete:
echo.
echo   Unpacked folder:
echo   %CD%\release\ZeroGPT-Portable\
echo.
echo   ZIP:
echo   %CD%\release\ZeroGPT-Portable.zip
echo.
echo No installer is required for the ZeroGPT app itself.
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1
