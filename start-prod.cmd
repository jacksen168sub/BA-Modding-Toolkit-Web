@echo off
chcp 65001 >nul 2>&1
title BA-Modding-Toolkit-Web Production

echo Starting BA-Modding-Toolkit-Web...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0start-prod.ps1" %*

pause