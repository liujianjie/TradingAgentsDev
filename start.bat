@echo off
REM TradingAgents launcher
REM This file MUST stay pure ASCII; Chinese UI is in launcher.ps1
REM Use chcp 65001 so the cmd window renders the UTF-8 output from PS
chcp 65001 >nul

set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\launcher.ps1"

if errorlevel 1 (
    echo.
    echo Launcher exited with error. Press any key to close.
    pause >nul
)
