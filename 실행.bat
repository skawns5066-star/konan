@echo off
cd /d "%~dp0"
py -3 light_gv_tool.py || python light_gv_tool.py
if errorlevel 1 pause
