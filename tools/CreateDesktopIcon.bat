@echo off
title Create Ascent Chubby Desktop Icon
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-DesktopShortcut.ps1"
echo.
pause
