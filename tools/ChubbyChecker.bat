@echo off
title Chubby Checker
setlocal

:: Repo root = parent of tools\
set "ROOT=%~dp0.."
cd /d "%ROOT%"

:: Prefer venv python if present
if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" "%ROOT%\tools\gui_launcher.py"
  goto :eof
)

:: System Python
where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python "%ROOT%\tools\gui_launcher.py"
  goto :eof
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py "%ROOT%\tools\gui_launcher.py"
  goto :eof
)

echo Python not found. Install Python 3.11+ from https://www.python.org/downloads/
pause
