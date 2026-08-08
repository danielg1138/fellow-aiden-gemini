@echo off
title Fellow Aiden - Brew Studio
cd /d "%~dp0"
echo.
echo =======================================================
echo        Starting Fellow Aiden - Brew Studio...
echo =======================================================
echo.
call .\venv\Scripts\activate.bat
start "" http://localhost:8501
streamlit run brew_studio\brew_studio.py
if errorlevel 1 (
    echo.
    echo Something went wrong while running Brew Studio.
    pause
)
