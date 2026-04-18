@echo off
title YouTube Shorts Agent - ONCE
color 0B
cd /d "%~dp0"

REM Use system Python (packages installed globally, not in venv)
echo Running pipeline ONCE...
echo.
python -X utf8 main.py --once
echo.
if %errorlevel% neq 0 (
    echo [ERROR] Pipeline failed. See output above.
) else (
    echo [DONE] Short produced and uploaded successfully!
)
pause
