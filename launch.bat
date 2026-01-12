@echo off
title EMG Signal Collection - Flask Server
color 0B

echo ========================================
echo   EMG Signal Collection Interface
echo ========================================
echo.
echo Checking dependencies...
echo.

REM Check if Python is installed
py --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

REM Check and install required packages
echo Verifying required libraries...
echo.

py -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available
    pause
    exit /b 1
)

echo [1/7] Checking Flask...
py -c "import flask" 2>nul || (
    echo    Installing Flask...
    py -m pip install flask --quiet
)

echo [2/7] Checking pyserial...
py -c "import serial" 2>nul || (
    echo    Installing pyserial...
    py -m pip install pyserial --quiet
)

echo [3/7] Checking numpy...
py -c "import numpy" 2>nul || (
    echo    Installing numpy...
    py -m pip install numpy --quiet
)

echo [4/7] Checking pyedflib...
py -c "import pyedflib" 2>nul || (
    echo    Installing pyedflib...
    py -m pip install pyedflib --quiet
)

echo [5/7] Checking mne...
py -c "import mne" 2>nul || (
    echo    Installing mne...
    py -m pip install mne --quiet
)

echo [6/7] Checking PyQt5...
py -c "import PyQt5" 2>nul || (
    echo    Installing PyQt5...
    py -m pip install PyQt5 --quiet
)

echo [7/8] Checking pyqtgraph...
py -c "import pyqtgraph" 2>nul || (
    echo    Installing pyqtgraph...
    py -m pip install pyqtgraph --quiet
)

echo [8/8] Checking matplotlib...
py -c "import matplotlib" 2>nul || (
    echo    Installing matplotlib...
    py -m pip install matplotlib --quiet
)

echo.
echo [OK] All dependencies verified!
echo.
echo ========================================
echo Starting Flask server...
echo.
echo Once started, open your browser to:
echo http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

py app_emg.py

pause
