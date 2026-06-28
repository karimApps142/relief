@echo off
title ComfyUI - Relief Studio engine
REM Launch ComfyUI in its OWN window with console output (NOT piped into the app). On
REM Windows, tqdm flushing a piped stream crashes some nodes (UltimateSDUpscale) with
REM "[Errno 22] Invalid argument" — a real console avoids it. The Relief app auto-detects
REM this running ComfyUI (127.0.0.1:8188) and uses it. Leave this window open.
cd /d "%~dp0..\ComfyUI"

if not exist "main.py" (
  echo [!] ComfyUI not found at "%CD%".
  echo     Install it first via the app's "Set up the image engine" wizard.
  echo.
  pause
  exit /b 1
)

REM free :8188 if a previous (piped) ComfyUI is holding it
for /f "tokens=5" %%a in ('netstat -ano ^| findstr LISTENING ^| findstr ":8188"') do taskkill /F /PID %%a >nul 2>nul

echo ============================================================
echo   ComfyUI engine  ·  http://127.0.0.1:8188
echo   Leave this window open. Ctrl+C to stop.
echo ============================================================
echo.
"%~dp0.venv\Scripts\python.exe" main.py --listen 127.0.0.1 --port 8188

echo.
echo ComfyUI stopped.
pause
