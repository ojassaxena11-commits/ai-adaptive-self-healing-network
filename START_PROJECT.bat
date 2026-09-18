@echo off
setlocal

title AI-Driven Adaptive Self-Healing Network - NOC Launcher

echo ==============================================================================
echo   AI-DRIVEN ADAPTIVE SELF-HEALING NETWORK
echo ==============================================================================
echo Starting NOC Dashboard...
echo Environment: SIMULATION
echo.

:: Navigate to script directory
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

:: Check for app.py
if not exist "%~dp0app.py" goto ErrNoApp

:: Check for virtual environment
if not exist "%~dp0.venv\Scripts\python.exe" goto ErrNoVenv

:: Ensure .env exists
if not exist "%~dp0.env" if exist "%~dp0.env.example" copy /y "%~dp0.env.example" "%~dp0.env" >nul

echo Opening Streamlit dashboard...
echo.

"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0app.py"
goto End

:ErrNoApp
echo [x] Error: app.py not found at "%~dp0app.py"
echo     Please verify project root structure.
echo.
pause
exit /b 1

:ErrNoVenv
echo [x] Error: Virtual environment .venv was not found at "%~dp0.venv".
echo     Please run SETUP_PROJECT.bat first to set up the environment.
echo.
pause
exit /b 1

:End
if %errorlevel% neq 0 pause
