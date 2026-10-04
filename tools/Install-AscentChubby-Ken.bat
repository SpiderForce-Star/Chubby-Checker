@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Ascent Chubby Install - Ken Williams
rem Drop-in installer for Ken Williams.
rem Windows profile / computer label: Ken.Williams
rem Run from the unzipped clean package (no .venv, no git clone, do not copy Chris .venv).
rem Creates .venv, installs requirements, and a Desktop shortcut "Ascent Chubby".
rem Daily access code: Twist1960

set "EXPECTED_USER=Ken.Williams"
set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "ROOT=%CD%"

echo.
echo ============================================
echo  Ascent Chubby / Chubby Checker installer
echo  Prepared for: Ken Williams
echo  Expected Windows user: %EXPECTED_USER%
echo ============================================
echo  Install folder : %ROOT%
echo  This PC user   : %USERNAME%
echo  This PC name   : %COMPUTERNAME%
echo.
echo  Note: Windows NetBIOS computer names cannot contain a period.
echo  Ken.Williams is checked as the Windows user (C:\Users\Ken.Williams).
echo.

if /I not "%USERNAME%"=="%EXPECTED_USER%" (
  echo WARNING: Windows user is "%USERNAME%", expected %EXPECTED_USER%.
  echo Continue only if this is Ken's machine.
  set /p GO=Continue? Y/N: 
  if /I not "!GO!"=="Y" (
    echo Cancelled.
    pause
    exit /b 1
  )
)

if not exist "%ROOT%\tools\gui_launcher.py" (
  echo ERROR: tools\gui_launcher.py not found.
  echo Unzip the full Chubby-Checker folder first, then run this file from tools\.
  pause
  exit /b 1
)
if not exist "%ROOT%\requirements.txt" (
  echo ERROR: requirements.txt not found in %ROOT%
  pause
  exit /b 1
)

set "PY="
where py >nul 2>&1 && (
  py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1 && set "PY=py -3.12"
  if not defined PY py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1 && python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo ERROR: Python 3.11+ was not found.
  echo Install from https://www.python.org/downloads/ and check "Add python.exe to PATH".
  echo Or in an admin prompt: winget install -e --id Python.Python.3.12
  pause
  exit /b 1
)
echo Using: %PY%

if exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Existing .venv found. Reusing it.
  echo Delete the .venv folder and rerun this installer to rebuild from scratch.
) else (
  echo Creating .venv ...
  %PY% -m venv "%ROOT%\.venv"
  if errorlevel 1 (
    echo ERROR: Could not create .venv.
    pause
    exit /b 1
  )
)

call "%ROOT%\.venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Could not activate .venv.
  pause
  exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 (
  echo ERROR: pip upgrade failed. Ken's PC needs internet for this step.
  pause
  exit /b 1
)
python -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 (
  echo ERROR: requirements install failed. Ken's PC needs internet for this step.
  pause
  exit /b 1
)

echo Creating Desktop shortcut "Ascent Chubby" ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\Install-DesktopShortcut.ps1"
if errorlevel 1 (
  echo ERROR: Desktop shortcut was not created.
  pause
  exit /b 1
)

echo.
echo DONE for Ken Williams.
echo Shortcut : Desktop \ Ascent Chubby
echo Access code : Twist1960
echo Leave this folder in place. Do not move it after install.
echo Suggested location: C:\Users\Ken.Williams\Ascent-Chubby
echo.
pause
endlocal
