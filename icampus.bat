@echo off
chcp 65001 >nul
title icampus 최신화
cd /d "%~dp0"
".venv\Scripts\python.exe" run.py
echo.
echo 이 창은 30초 뒤 닫힙니다. (바로 닫으려면 아무 키나 누르세요)
timeout /t 30 >nul
