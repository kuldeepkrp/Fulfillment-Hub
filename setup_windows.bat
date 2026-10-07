@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Fulfillment Hub - Windows Setup
echo ==========================================

set "PYTHON_CMD=python"
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo.
        echo Python was not found.
        echo Install Python 3.10+ and make sure it is available as 'python' or 'py'.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py"
)

if not exist .venv (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Setup complete.
echo Run run_app.bat to start Fulfillment Hub.
pause
