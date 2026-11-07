@echo off
REM ============================================================
REM  Build a standalone Windows exe (no Python needed on target PCs)
REM  Run this file on a Windows PC that has Python 3.10+ installed.
REM ============================================================
cd /d "%~dp0"

echo [1/3] Installing libraries...
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo [2/3] Building exe (takes a few minutes)...
python -m PyInstaller --noconfirm --clean --windowed --name EquipmentGuide --add-data "fonts;fonts" main.py
if errorlevel 1 goto :error

echo [3/3] Done.
echo.
echo Output folder: %~dp0dist\EquipmentGuide
echo Run:           dist\EquipmentGuide\EquipmentGuide.exe
echo Copy the whole "dist\EquipmentGuide" folder to other PCs (USB etc.).
echo The "data" folder is created next to the exe on first run.
pause
exit /b 0

:error
echo.
echo BUILD FAILED. Check that Python is installed and "python" works in this window.
pause
exit /b 1
