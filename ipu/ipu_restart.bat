@echo off
cd /d "%~dp0"
REM Usage: ipu_restart.bat            (all)
REM        ipu_restart.bat ipu1 ipu3  (selected)
REM        ipu_restart.bat --check    (check only)
python ipu_restart.py %*
pause
