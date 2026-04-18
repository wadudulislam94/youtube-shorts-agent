@echo off
title YouTube Shorts Agent — Setup (Free Edition)
color 0E
echo.
echo  ================================================================
echo   YouTube Shorts Agent - FREE Edition Setup
echo  ================================================================
echo.

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Download from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

REM Check ffmpeg (required by moviepy)
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] ffmpeg not found. Installing via winget...
    winget install ffmpeg
    echo [OK] ffmpeg installed. Restart terminal if issues persist.
) else (
    echo [OK] ffmpeg found
)

REM Create virtual environment
echo.
echo [1/3] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated

REM Upgrade pip silently
echo [2/3] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install all dependencies
echo [3/3] Installing packages (this may take 2-3 minutes)...
pip install -r requirements.txt

echo.
echo  ================================================================
echo   Setup Complete!
echo.
echo   Next steps:
echo   1. Edit .env — paste your GEMINI_API_KEY and PIXABAY_API_KEY
echo      Gemini (free): https://aistudio.google.com/app/apikey
echo      Pixabay (free): https://pixabay.com/api/docs/
echo.
echo   2. YouTube OAuth — see README.md Step 4
echo      (Download client_secrets.json from Google Cloud Console)
echo.
echo   3. Run RUN_ONCE.bat to test the full pipeline
echo   4. Run START.bat to start the scheduled agent
echo  ================================================================
echo.
pause
