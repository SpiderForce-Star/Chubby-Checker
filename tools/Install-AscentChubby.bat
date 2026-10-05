@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Ascent Chubby - one-time setup
rem Shared installer. Any Windows user can run this on their own PC.
rem No username lock. Do not clone GitHub. Do not copy someone else's .venv.
rem Creates .venv, installs requirements, and a Desktop shortcut "Ascent Chubby".
rem Daily access code: Twist1960

set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "ROOT=%CD%"

echo.
echo ============================================
echo  Ascent Chubby / Chubby Checker
echo  One-time setup for this PC
echo ============================================
echo  Install folder : %ROOT%
echo  Windows user   : %USERNAME%
echo  PC name        : %COMPUTERNAME%
echo  Shortcut goes on this user's Desktop.
echo.

if not exist "%ROOT%\tools\gui_launcher.py" (
  echo ERROR: tools\gui_launcher.py not found.
  echo Unzip the full Ascent-Chubby folder first, then run this file from tools\.
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
  echo Python 3.11 or newer was not found on this PC.
  echo.
  echo  1. Install Python 3.11 or 3.12
  echo  2. On the first screen, CHECK: Add python.exe to PATH
  echo  3. Close this window and run this file again
  echo.
  echo Or, in an admin Command Prompt:
  echo   winget install -e --id Python.Python.3.12
  echo.
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)
echo Using: %PY%
%PY% --version
echo.

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

echo Installing packages. First run can take 1-3 minutes. Internet is required.
python -m pip install --upgrade pip
if errorlevel 1 (
  echo ERROR: pip upgrade failed. This PC needs internet for this step.
  pause
  exit /b 1
)
python -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 (
  echo ERROR: requirements install failed. This PC needs internet for this step.
  pause
  exit /b 1
)
if exist "%ROOT%\pyproject.toml" (
  python -m pip install -e "%ROOT%"
  if errorlevel 1 (
    echo ERROR: package install failed.
    pause
    exit /b 1
  )
)

echo Creating Desktop shortcut "Ascent Chubby" for %USERNAME% ...
if exist "%ROOT%\tools\Install-DesktopShortcut.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\Install-DesktopShortcut.ps1"
  if errorlevel 1 (
    echo ERROR: Desktop shortcut was not created.
    pause
    exit /b 1
  )
) else if exist "%ROOT%\tools\CreateDesktopIcon.bat" (
  call "%ROOT%\tools\CreateDesktopIcon.bat"
) else (
  echo NOTE: Desktop shortcut script not found.
  echo You can still launch with tools\ChubbyChecker.bat
)

echo.
echo ============================================
echo  Setup complete for %USERNAME%.
 echo.
echo  Daily use:
echo    1. Double-click Ascent Chubby on the Desktop
echo    2. Access code: Twist1960
echo    3. Drop the Complete Shipper and Final Drawings
echo    4. Click Run Check, then Open Report
echo.
echo  Leave this folder where it is. Do not move it after install.
echo  A good place is: %USERPROFILE%\Ascent-Chubby
echo.
echo  Questions: Chris Woodmore  chris.woodmore@ascentbuildings.com
echo             865-307-6336
echo ============================================
echo.
pause
endlocal
