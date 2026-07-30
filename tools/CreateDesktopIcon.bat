@echo off
title Create Chubby Checker Desktop Icon
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-DesktopShortcut.ps1"
echo.
pause
