@echo off
title Cjspanel V1 - Starting...
color 0A
cls

echo.
echo   ____  _                           _   
echo  / ___^|(_)___ _ __   __ _ _ __   ___^| ^|  
echo ^| ^|   ^| / __^| '_ \ / _` ^| '_ \ / _ \ ^|  
echo ^| ^|___^| \__ \ ^|_) ^| (_^| ^| ^| ^| ^|  __/ ^|  
echo  \____/ ^|___/ .__/ \__,_^|_^| ^|_^|\___^|_^|  
echo            ^|_^|                          
echo.
echo ============================================
echo   Advanced Device Control Panel v1.0
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed!
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Check if virtual environment exists
if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
    echo [+] Virtual environment created!
)

:: Activate virtual environment
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

:: Install/Update dependencies
echo [*] Installing dependencies...
pip install -r requirements.txt -q

:: Clear screen for clean start
cls
echo.
echo   ____  _                           _   
echo  / ___^|(_)___ _ __   __ _ _ __   ___^| ^|  
echo ^| ^|   ^| / __^| '_ \ / _` ^| '_ \ / _ \ ^|  
echo ^| ^|___^| \__ \ ^|_) ^| (_^| ^| ^| ^| ^|  __/ ^|  
echo  \____/ ^|___/ .__/ \__,_^|_^| ^|_^|\___^|_^|  
echo            ^|_^|                          
echo.
echo ============================================
echo   [+] All systems ready!
echo   [*] Starting server...
echo ============================================
echo.
echo   Access Panel at: http://localhost:5000
echo.
echo   Default Credentials:
echo   Username: Chetancj
echo   Password: Chetancj
echo.
echo   Press Ctrl+C to stop the server
echo ============================================
echo.

:: Start the server
python main.py
