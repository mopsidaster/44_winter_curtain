@echo off
chcp 65001 >nul
setlocal EnableExtensions
title 44 WHITE CURTAIN - Web Server [LIVE]
color 0A
cd /d "%~dp0"

rem ═══════════ НАСТРОЙКИ СЕРВЕРА ═══════════
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
set WC_HOST=0.0.0.0
set WC_PORT=8080
set WC_EVENTS=1
set WC_AUTOSAVE=1

set WC_PIN=1234
set WC_ADMIN=mops
set WC_DEBUG=0

set WC_RATE=20
set WC_RATE_BURST=40
set WC_MAP_ITER=160
rem ════════════════════════════════════════

rem Режим вывода: по умолчанию ВСЁ в консоль в реальном времени.
rem Ключ /log (или --tee) дополнительно пишет копию в logs\web_server.log.
set TEE=0
for %%A in (%*) do (
  if /i "%%~A"=="/log"  set TEE=1
  if /i "%%~A"=="--tee" set TEE=1
  if /i "%%~A"=="/tee"  set TEE=1
)

if not exist "logs" mkdir "logs"

echo ========================================
echo    44 WHITE CURTAIN - WEB TERMINAL D6
echo ========================================
echo.

if "%WC_PIN%"=="1234" echo [!] PIN по умолчанию 1234 - смени перед игрой с людьми.
if "%WC_ADMIN%"==""   echo [!] WC_ADMIN не задан - администратора не будет.
if "%WC_DEBUG%"=="1"  echo [!] DEBUG включён - экономика сервера не защищена.

where python >nul 2>&1
if errorlevel 1 (
  echo [X] Python не найден в PATH. Установи Python 3.11+ с галкой "Add to PATH".
  pause
  exit /b 1
)

python -c "import aiohttp, aiosqlite" >nul 2>&1
if errorlevel 1 (
  echo [!] Ставлю зависимости: aiohttp, aiosqlite...
  python -m pip install --disable-pip-version-check aiohttp aiosqlite
  if errorlevel 1 (
    echo [X] Установка не удалась. Выполни: python -m pip install aiohttp aiosqlite
    pause
    exit /b 1
  )
)

net session >nul 2>&1
if not errorlevel 1 (
  netsh advfirewall firewall show rule name="Metro44 Web" >nul 2>&1
  if errorlevel 1 (
    netsh advfirewall firewall add rule name="Metro44 Web" dir=in action=allow protocol=TCP localport=%WC_PORT% profile=any >nul
    echo [OK] Правило брандмауэра для порта %WC_PORT% создано.
  )
) else (
  echo [!] Нет прав администратора - порт в брандмауэре не открыт. Если игроки не подключаются, выполни от админа:
  echo     netsh advfirewall firewall add rule name="Metro44 Web" dir=in action=allow protocol=TCP localport=%WC_PORT%
)

echo.
echo  Radmin VPN: адрес 26.x.x.x этого ПК, порт %WC_PORT%
echo  Игроки открывают: http://26.x.x.x:%WC_PORT%
echo  PIN: %WC_PIN%   Админ: %WC_ADMIN%
if "%TEE%"=="1" (
  echo  Вывод: КОНСОЛЬ + logs\web_server.log
) else (
  echo  Вывод: КОНСОЛЬ в реальном времени ^(ключ /log - писать ещё и в файл^)
)
echo  Игровой лог независимо пишется в logs\metro_bot.log
echo.
echo  Остановка: Ctrl+C - дождись строки "Сервер остановлен, БД закрыта".
echo ========================================
echo.

if "%TEE%"=="1" goto :run_tee

:run_live
python -u "server\web\app.py"
set EXITCODE=%errorlevel%
goto :done

:run_tee
powershell -NoProfile -ExecutionPolicy Bypass -Command "$OutputEncoding=[Console]::OutputEncoding=(New-Object System.Text.UTF8Encoding $false); $env:PYTHONUNBUFFERED='1'; & python -u 'server\web\app.py' 2>&1 | Tee-Object -FilePath 'logs\web_server.log'"
set EXITCODE=%errorlevel%
goto :done

:done
echo.
if not "%EXITCODE%"=="0" (
  color 0C
  echo [X] Сервер завершился с кодом %EXITCODE%.
  if exist "logs\metro_bot.log" (
    echo --- последние 25 строк logs\metro_bot.log ---
    powershell -NoProfile -Command "Get-Content -Path 'logs\metro_bot.log' -Tail 25"
  )
) else (
  echo  Сервер остановлен штатно.
)
echo.
pause
endlocal