@echo off
title Ascent Shipper Checker - GUI
setlocal

:: Resolve repo root (this .bat lives in tools\)
set "ROOT=%~dp0.."
cd /d "%ROOT%"

:: Prefer project venv if present
if exist "%ROOT%\.venv\Scripts\pythonw.exe" (
  start "" "%ROOT%\.venv\Scripts\pythonw.exe" "%ROOT%\tools\gui_launcher.py"
  exit /b 0
)
if exist "%ROOT%\.venv\Scripts\python.exe" (
  start "" "%ROOT%\.venv\Scripts\python.exe" "%ROOT%\tools\gui_launcher.py"
  exit /b 0
)

:: Fallback to system Python
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" pythonw "%ROOT%\tools\gui_launcher.py"
  exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" python "%ROOT%\tools\gui_launcher.py"
  exit /b 0
)

echo Python not found. Install Python 3.11+ and create .venv in the project folder.
pause
