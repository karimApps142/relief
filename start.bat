@echo off
title Relief Studio
cd /d "%~dp0"

echo ============================================================
echo   Relief Studio
echo ============================================================
echo.
echo Updating to latest (git pull)...
git pull --ff-only

REM --- free port 8000 if a previous server is still holding it (clean restart) ---
echo Freeing port 8000 if a previous server is running...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr LISTENING ^| findstr ":8000"') do taskkill /F /PID %%a >nul 2>nul

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [!] .venv not found in "%CD%".
  echo     Create the virtual env and install requirements-gpu.txt first.
  echo.
  pause
  exit /b 1
)

echo.
echo Starting server. Leave this window open.
echo   Local:     http://localhost:8000
echo   From Mac:  http://100.86.189.84:8000   (Tailscale)
echo   Stop:      press Ctrl+C
echo.

.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000

echo.
echo Server stopped.
pause
