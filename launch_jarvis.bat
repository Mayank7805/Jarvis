@echo off
title Jarvis AI Assistant
echo.
echo  ========================================
echo   Starting Jarvis AI Assistant...
echo  ========================================
echo.

REM Navigate to the project directory (handles if batch file is run from the Desktop)
cd /d "%~dp0"
if exist "Mayank\Project\Jarvis" (
    cd "Mayank\Project\Jarvis"
)

REM Ensure Python prints output in real-time (no buffering)
set PYTHONUNBUFFERED=1

REM Verify the venv exists
if not exist "venv\Scripts\python.exe" (
    echo  [ERROR] Virtual environment not found at venv\Scripts\python.exe
    echo  Please run: python -m venv venv
    pause
    exit /b 1
)

REM Verify main.py exists
if not exist "main.py" (
    echo  [ERROR] main.py not found in %cd%
    pause
    exit /b 1
)

REM Store the project root as an absolute path for the child window
set "PROJECT_ROOT=%cd%"

REM Start the Python backend in a new window using the venv python directly
REM (avoids relying on PATH / activate inheritance across 'start' boundaries)
echo  [1/2] Launching Python backend...
start "Jarvis Backend" cmd /k "cd /d "%PROJECT_ROOT%" && set PYTHONUNBUFFERED=1 && "%PROJECT_ROOT%\venv\Scripts\python.exe" main.py || (echo. & echo [ERROR] Backend crashed. See above for details. & pause)"

REM Give the backend time to initialise (STT model, server, etc.)
echo  [...]  Waiting for backend to initialise...
timeout /t 8 /nobreak >nul

REM Start the UI (Electron / React)
echo  [2/2] Launching UI...
if not exist "ui\node_modules" (
    echo  [WARN] ui\node_modules not found — running npm install first...
    cd ui
    call npm install
) else (
    cd ui
)
start "Jarvis UI" /D "%PROJECT_ROOT%\ui" cmd /k "npm start || (echo. & echo [ERROR] UI failed to start. See above. & pause)"

echo.
echo  Jarvis is starting...
echo  (You can close this window)
echo.
