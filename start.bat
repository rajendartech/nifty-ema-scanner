@echo off
title NIFTY EMA Scanner
echo ============================================
echo        NIFTY EMA Scanner  v2.0
echo ============================================
echo.

cd /d "%~dp0"

if not exist venv (
    echo [1/3] Creating virtual environment...
    python -m venv venv
) else (
    echo [1/3] Virtual environment already exists.
)

echo.
echo [2/3] Installing / updating requirements...
venv\Scripts\python -m pip install --upgrade pip -q
venv\Scripts\python -m pip install -r requirements.txt -q

echo.
echo [3/3] Launching NIFTY EMA Scanner...
echo.
echo  Browser will open at http://localhost:8501
echo  Press Ctrl+C in this window to stop.
echo.

start "" http://localhost:8501
venv\Scripts\streamlit run app.py --server.headless false

pause
