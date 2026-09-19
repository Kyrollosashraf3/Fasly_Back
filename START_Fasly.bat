@echo off
chcp 65001 >nul
title Fasly Launcher - Double Click to Run
cd /d "%~dp0"

echo ============================================
echo   Fasly - Sunday School App Launcher
echo   Backend : http://127.0.0.1:9001
echo   Frontend: http://localhost:8000
echo ============================================
echo.

REM ---------- 1) Find Python ----------
set PYCMD=
python --version >nul 2>&1
if %errorlevel%==0 (
  set PYCMD=python
) else (
  py --version >nul 2>&1
  if %errorlevel%==0 (
    set PYCMD=py
  ) else (
    goto :INSTALL_PYTHON
  )
)
echo [1/5] Python found: %PYCMD%
%PYCMD% --version
echo.
goto :SETUP_VENV

:INSTALL_PYTHON
echo [!] Python is NOT installed on this computer.
echo [*] Trying to install it automatically with winget...
where winget >nul 2>&1
if %errorlevel%==0 (
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo.
  echo [*] Python install finished. Please CLOSE this window and DOUBLE-CLICK the file again.
  pause
  exit /b 0
) else (
  echo [!] winget not found. Opening python.org so you can install Python manually...
  echo     IMPORTANT: while installing, check the box "Add python.exe to PATH"
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)

REM ---------- 2) venv + requirements ----------
:SETUP_VENV
echo [2/5] Checking virtual environment...
if not exist "back_fasly\.venv\Scripts\python.exe" (
  echo [*] Creating venv in back_fasly\.venv ...
  %PYCMD% -m venv "back_fasly\.venv"
  if %errorlevel% neq 0 (
    echo [ERROR] Could not create venv. Make sure Python is installed correctly.
    pause
    exit /b 1
  )
)
set VENV_PY=%~dp0back_fasly\.venv\Scripts\python.exe
echo [3/5] Installing requirements (first time takes a few minutes)...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r "back_fasly\requirements.txt"
if %errorlevel% neq 0 (
  echo [ERROR] pip install failed. Check your internet connection and try again.
  pause
  exit /b 1
)
echo     Requirements OK.
echo.

REM ---------- 3) .env check ----------
if not exist "back_fasly\.env" (
  if exist "back_fasly\.env.example" (
    echo [*] No .env found - copying from .env.example, edit it later if needed.
    copy /y "back_fasly\.env.example" "back_fasly\.env" >nul
  ) else (
    echo [WARNING] back_fasly\.env not found! Backend may fail without Firebase credentials.
  )
)

REM ---------- 4) Close old copies (avoid port busy) ----------
echo [4/5] Closing old Fasly windows if any...
taskkill /FI "WINDOWTITLE eq Fasly Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Fasly Frontend*" /F >nul 2>&1
timeout /t 2 /nobreak >nul

REM ---------- 5) Start backend on port 9001 ----------
echo [5/5] Starting backend on port 9001...
start "Fasly Backend" cmd /k cd /d "%~dp0back_fasly" ^& "%~dp0back_fasly\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 9001

echo [*] Starting frontend on port 8000...
start "Fasly Frontend" cmd /k cd /d "%~dp0front_fasly" ^& "%~dp0back_fasly\.venv\Scripts\python.exe" -m http.server 8000

echo.
echo [*] Waiting for backend to be ready (max 30 sec)...
powershell -NoProfile -Command "$ok=$false; for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:9001/docs; if ($r.StatusCode -eq 200) { $ok=$true; break } } catch { Start-Sleep -Seconds 1 } }; if ($ok) { Write-Host 'Backend is UP!' } else { Write-Host 'WARNING: backend did not respond yet - check the Fasly Backend window for errors.' }"

echo.
echo [*] Opening the app in your browser...
timeout /t 2 /nobreak >nul
start "" "http://localhost:8000"

REM Try Chrome explicitly too (won't hurt if Chrome isn't there)
where chrome >nul 2>&1
if %errorlevel%==0 (
  start chrome "http://localhost:8000" >nul 2>&1
)

echo.
echo ============================================
echo   DONE! The app should now be open.
echo   Frontend: http://localhost:8000
echo   Backend docs: http://127.0.0.1:9001/docs
echo   Do NOT close the two black windows
echo   (Fasly Backend + Fasly Frontend) while using the app.
echo ============================================
echo.
echo Press any key to keep this window open (app keeps running)...
pause >nul
