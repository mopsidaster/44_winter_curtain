@echo off
chcp 65001 >nul
title Metro 2033 Bot Launcher
color 0A
echo ========================================
echo        𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍 - МЕНЮ ЗАПУСКА
echo ========================================
echo.
echo Запуск PowerShell меню...
echo.
powershell -ExecutionPolicy Bypass -File "menu.ps1"
pause