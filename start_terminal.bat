@echo off
title AI Quant Trading Forecast Terminal
echo ========================================================
echo    Starting AI Quant Trading Forecast Terminal
echo ========================================================
cd /d "%~dp0"

:: Check if virtual environment exists; if not, set it up automatically!
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] First time setup detected on this computer!
    echo [INFO] Creating Python virtual environment...
    
    where uv >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        uv venv --python 3.11 .venv
        uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    ) else (
        where python >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            python -m venv .venv
            .venv\Scripts\pip install -r requirements.txt
        ) else (
            echo [ERROR] Neither 'uv' nor 'python' was found on PATH.
            echo Please install Python 3.11 from https://www.python.org/
            pause
            exit /b 1
        )
    )
    echo [SUCCESS] Environment created successfully!
)

:: Launch the application
".venv\Scripts\python.exe" run.py
pause
