@echo off
setlocal enabledelayedexpansion

title Setup - AI-Driven Adaptive Self-Healing Network

echo ==============================================================================
echo   AI-DRIVEN ADAPTIVE SELF-HEALING NETWORK - ENVIRONMENT SETUP
echo ==============================================================================
echo.

cd /d "%~dp0"

:: 1. Verify Python availability
echo [*] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [x] Error: Python was not found on your PATH.
    echo     Please install Python 3.10+ and check 'Add Python to PATH' during installation.
    pause
    exit /b 1
)

python --version
echo.

:: 2. Create virtual environment if missing
if not exist ".venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [x] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [*] Virtual environment created successfully.
) else (
    echo [*] Virtual environment (.venv) already exists.
)

:: 3. Activate environment
call ".venv\Scripts\activate.bat"

:: 4. Upgrade pip and install requirements
echo.
echo [*] Upgrading pip and installing required dependencies...
python -m pip install --upgrade pip
if exist "requirements.txt" (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [!] Warning: Some dependencies failed to install. Please check network/pip output.
    ) else (
        echo [*] All requirements installed successfully.
    )
) else (
    echo [!] Warning: requirements.txt not found.
)

:: 5. Create .env if missing (do not overwrite existing .env)
echo.
if not exist ".env" (
    if exist ".env.example" (
        echo [*] Creating .env from .env.example with default ENV_MODE=SIMULATION...
        copy /y ".env.example" ".env" >nul
        echo [*] .env configuration initialized.
    ) else (
        echo [*] Generating default .env file...
        (
            echo ENV_MODE=SIMULATION
            echo CML_HOST=192.168.1.100
            echo CML_PORT=80
            echo CML_USER=admin
            echo CML_PASS=cisco123
            echo SSH_USER=cisco
            echo SSH_PASS=cisco123
            echo LOG_LEVEL=INFO
        ) > ".env"
        echo [*] Default .env created.
    )
) else (
    echo [*] Existing .env detected - preserving user settings.
)

:: 6. Run Unit Tests Verification
echo.
echo [*] Running automated test verification (19 unit tests)...
set "PYTHONPATH=%~dp0"
python -m unittest discover tests -v

echo.
echo ==============================================================================
echo   SETUP COMPLETE!
echo   You can now launch the system anytime by double-clicking START_PROJECT.bat
echo ==============================================================================
echo.
pause
