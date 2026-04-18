@echo off
title YouTube Shorts Agent - Scheduler
color 0A
echo.
echo  ============================================================
echo   YouTube Shorts Agent - Scheduled Mode (4 Shorts/day)
echo  ============================================================
echo.
echo  Niche: facts (edit .env to change)
echo  Schedule: every 6 hours
echo  Press Ctrl+C to stop
echo.

cd /d "%~dp0"

python -X utf8 main.py

pause
