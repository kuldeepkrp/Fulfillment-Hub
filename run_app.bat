@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Virtual environment not found.
    echo Please run setup_windows.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
streamlit run app.py
