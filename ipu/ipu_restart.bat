@echo off
chcp 949 >nul
cd /d "%~dp0"
REM 사용: ipu_restart.bat            (전체)
REM       ipu_restart.bat ipu1 ipu3  (선택)
REM       ipu_restart.bat --check    (점검)
python ipu_restart.py %*
pause
