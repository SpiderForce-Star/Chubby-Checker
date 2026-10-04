@echo off
setlocal EnableExtensions
title Build Ascent Chubby
cd /d "%~dp0"

echo.
echo ============================================
echo  Build Ascent Chubby.exe
echo ============================================
echo.
echo This makes ONE file you can copy to a desktop and double-click.
echo It can take 10 to 20 minutes. Leave this window open.
echo Internet is required the first time.
echo.

set "PY="
where py >nul 2>&1 && (
  py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1 && set "PY=py -3.12"
  if not defined PY py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1 && set "PY=py -3.11"
  if not defined PY py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1 && python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python 3.11 or newer was not found.
  echo.
  echo 1. Open https://www.python.org/downloads/release/python-3120/
  echo 2. Install Python 3.12. Check "Add python.exe to PATH".
  echo 3. Double-click this file again.
  echo.
  pause
  exit /b 1
)

echo Using: %PY%
echo.

if not exist ".venv-build\Scripts\python.exe" (
  echo Creating a build folder. This does not change the copy you already run.
  %PY% -m venv .venv-build
  if errorlevel 1 goto :fail
)

call ".venv-build\Scripts\activate.bat"
if errorlevel 1 goto :fail

python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt pyinstaller pillow
if errorlevel 1 goto :fail
python -m pip install -e .
if errorlevel 1 goto :fail

echo.
echo Building Ascent Chubby.exe. Please wait...
echo.
set "PYTHONPATH=%CD%"
python -m PyInstaller --noconfirm --clean "tools\ascent_chubby.spec"
if errorlevel 1 goto :fail
if not exist "dist\Ascent Chubby.exe" goto :fail

powershell -NoProfile -Command "$d = [Environment]::GetFolderPath('Desktop'); Copy-Item -LiteralPath 'dist\Ascent Chubby.exe' -Destination (Join-Path $d 'Ascent Chubby.exe') -Force; Write-Host ('Copied to ' + (Join-Path $d 'Ascent Chubby.exe'))"
if errorlevel 1 goto :fail

echo.
echo DONE.
echo Ascent Chubby.exe is on your Desktop.
echo Copy that one file to each person's desktop.
echo They double-click it and enter Twist1960.
echo If Windows says it protected the PC: More info, then Run anyway.
echo.
pause
exit /b 0

:fail
echo.
echo BUILD FAILED.
echo Leave this window open and send a photo of the text above.
echo If you want a clean retry, delete the .venv-build folder and run this again.
echo.
pause
exit /b 1
