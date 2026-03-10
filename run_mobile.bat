@echo off
echo ==============================================
echo       NIFTY EMA Scanner (Mobile UI)         
echo ==============================================

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate

echo.
echo Starting Mobile NIFTY EMA Scanner...
venv\Scripts\python mobile_app.py
