@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

rem ═══════════════ НАСТРОЙКИ СЕРВЕРА ═══════════════
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set WC_HOST=0.0.0.0
set WC_PORT=8080
set WC_EVENTS=1
set WC_AUTOSAVE=1

rem PIN сервера: без него зарегистрируется любой, кто видит порт.
set WC_PIN=1234

rem Логин владельца сервера (регистр не важен). Только он получит права админа.
set WC_ADMIN=mops

rem Отладочные команды (/debug). Наружу НЕ включать: раздают деньги и лояльность.
set WC_DEBUG=1

rem Лимит действий игрока в секунду (защита от флуда).
set WC_RATE=20
set WC_RATE_BURST=40

rem Итерации раскладки схемы метро. Меньше — быстрее старт карты.
set WC_MAP_ITER=160
rem ════════════════════════════════════════════════

if "%WC_PIN%"=="1234" (
  echo [!] Стоит PIN по умолчанию 1234. Смени его в этом файле перед игрой с людьми.
)
if "%WC_ADMIN%"=="" (
  echo [!] WC_ADMIN не задан - администратора на сервере не будет.
)
if "%WC_DEBUG%"=="1" (
  echo [!] ВНИМАНИЕ: включены debug-команды. Экономика сервера не защищена.
)

where python >nul 2>&1
if errorlevel 1 (
  echo [X] Python не найден в PATH. Установи Python 3.11+ и отметь "Add to PATH".
  pause
  exit /b 1
)

python -c "import aiohttp, aiosqlite" >nul 2>&1
if errorlevel 1 (
  echo [!] Не хватает зависимостей. Ставлю aiohttp и aiosqlite...
  python -m pip install --disable-pip-version-check aiohttp aiosqlite
  if errorlevel 1 (
    echo [X] Установка не удалась. Выполни вручную: python -m pip install aiohttp aiosqlite
    pause
    exit /b 1
  )
)

net session >nul 2>&1
if %errorlevel%==0 (
  netsh advfirewall firewall show rule name="Metro44 Web" >nul 2>&1
  if errorlevel 1 (
    netsh advfirewall firewall add rule name="Metro44 Web" dir=in action=allow protocol=TCP localport=%WC_PORT% profile=any >nul
    echo [OK] Правило брандмауэра для порта %WC_PORT% создано.
  )
) else (
  echo [!] Запусти от администратора, чтобы открыть порт в брандмауэре, либо выполни:
  echo     netsh advfirewall firewall add rule name="Metro44 Web" dir=in action=allow protocol=TCP localport=%WC_PORT%
)

if not exist "logs" mkdir "logs"

echo.
echo  Подключение по Radmin VPN: адрес 26.x.x.x этого ПК, порт %WC_PORT%
echo  Игроки открывают в браузере: http://26.x.x.x:%WC_PORT%
echo  PIN для входа: %WC_PIN%
echo  Журнал сервера: logs\web_server.log
echo.
echo  Остановка: Ctrl+C (дождись строки "Сервер остановлен, БД закрыта").
echo.

python server\web\app.py 1>>"logs\web_server.log" 2>&1
set EXITCODE=%errorlevel%

echo.
if not "%EXITCODE%"=="0" (
  echo [X] Сервер завершился с кодом %EXITCODE%. Последние строки журнала:
  powershell -NoProfile -Command "Get-Content -Path 'logs\web_server.log' -Tail 25"
) else (
  echo  Сервер остановлен.
)
pause
endlocal