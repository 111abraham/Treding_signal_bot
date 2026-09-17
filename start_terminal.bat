@echo off
title AI Quant Trading Forecast Terminal
echo ========================================================
echo    Starting AI Quant Trading Forecast Terminal
echo ========================================================
cd /d "%~dp0"
".venv\Scripts\python.exe" run.py
pause
