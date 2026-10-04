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
echo If Python 3.12 is missing, this installs it automatically.
echo The finished program already contains Python.
echo The other computers do not install Python.
echo.

set "PY="
call :find312
if not defined PY call :install312
if not defined PY (
  echo Could not install Python 3.12.
  echo Leave this window open and send a photo of the text above.
  pause
  exit /b 1
)

echo Using: %PY%
echo.

if not exist ".venv-build\Scripts\python.exe" (
  echo Creating a build folder. This does not change the copy you already run.
  "%PY%" -m venv .venv-build
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
echo Python is already inside the file. They do not install Python.
echo If Windows says it protected the PC: More info, then Run anyway.
echo.
pause
exit /b 0

:find312
set "PY="
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  "%LocalAppData%\Programs\Python\Python312\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
    exit /b 0
  )
)
if exist "%ProgramFiles%\Python312\python.exe" (
  "%ProgramFiles%\Python312\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PY=%ProgramFiles%\Python312\python.exe"
    exit /b 0
  )
)
where py >nul 2>&1 && (
  for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%I"
)
if defined PY exit /b 0
exit /b 1

:install312
echo Python 3.12 was not found. Installing Python 3.12.10 now...
echo Windows may ask to allow changes. Click Yes if it does.
echo.
set "PYSETUP=%TEMP%\python-3.12.10-amd64.exe"
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $env:TEMP\python-3.12.10-amd64.exe -UseBasicParsing; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
  echo Download of Python 3.12.10 failed. This PC needs internet for that step.
  exit /b 1
)
echo Running the Python installer. Please wait...
start /wait "" "%PYSETUP%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_tcltk=1 Include_test=0 Shortcuts=0
call :find312
if defined PY (
  echo Python 3.12 is installed.
  exit /b 0
)
echo The Python installer finished, but python.exe was not found.
exit /b 1

:fail
echo.
echo BUILD FAILED.
echo Leave this window open and send a photo of the text above.
echo If you want a clean retry, delete the .venv-build folder and run this again.
echo.
pause
exit /b 1
