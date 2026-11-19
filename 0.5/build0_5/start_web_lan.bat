@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title 44 WHITE CURTAIN - ПУЛЬТ
color 0A

rem ═══════════════════════════════════════════════════════════════════
rem  44 WHITE CURTAIN - ПУЛЬТ УПРАВЛЕНИЯ СЕРВЕРОМ
rem  Без аргументов  : меню-пульт (сервер в отдельном окне WC44_SERVER)
rem  run / _run      : сервер в этом окне (старый режим), лог всегда в файл
rem  Мягкий стоп     : пульт шлёт Ctrl+C в окно сервера, ждёт 10с, потом /F
rem ═══════════════════════════════════════════════════════════════════

call :load_cfg
set "AUTORESTART=0"
set "STARTED=0"
set "SRV_TITLE=WC44_SERVER"

if /i "%~1"=="_run" goto :run_server
if /i "%~1"=="run"  goto :run_server

call :preflight
call :get_pid
if defined SRV_PID set "STARTED=1"
goto :menu

rem ═══════════ НАСТРОЙКИ СЕРВЕРА (правь здесь или пункт [9]) ═══════════
:load_cfg
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
exit /b 0

rem ═══════════ ПРОВЕРКИ ═══════════
:preflight
if not exist "logs" mkdir "logs"
echo ========================================
echo    44 WHITE CURTAIN - WEB TERMINAL D6
echo ========================================
if "%WC_PIN%"=="1234" echo [!] PIN по умолчанию 1234 - смени перед игрой с людьми.
if "%WC_ADMIN%"==""   echo [!] WC_ADMIN не задан - администратора не будет.
if "%WC_DEBUG%"=="1"  echo [!] DEBUG включён - экономика сервера не защищена.
where python >nul 2>&1
if errorlevel 1 (
  echo [X] Python не найден в PATH. Установи Python 3.11+ с галкой "Add to PATH".
  pause
  exit
)
python -c "import aiohttp, aiosqlite" >nul 2>&1
if errorlevel 1 (
  echo [!] Ставлю зависимости: aiohttp, aiosqlite...
  python -m pip install --disable-pip-version-check aiohttp aiosqlite
  if errorlevel 1 (
    echo [X] Установка не удалась. Выполни: python -m pip install aiohttp aiosqlite
    pause
    exit
  )
)
net session >nul 2>&1
if errorlevel 1 (
  echo [!] Нет прав администратора - правило брандмауэра не создано. Пункт [8] или запуск от админа.
  exit /b 0
)
netsh advfirewall firewall show rule name="Metro44 Web" >nul 2>&1
if errorlevel 1 (
  netsh advfirewall firewall add rule name="Metro44 Web" dir=in action=allow protocol=TCP localport=%WC_PORT% profile=any >nul
  echo [OK] Правило брандмауэра для порта %WC_PORT% создано.
)
exit /b 0

rem ═══════════ PID ПО ПОРТУ ═══════════
:get_pid
set "SRV_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /c:":%WC_PORT% " ^| findstr /c:"LISTENING"') do (
  if not defined SRV_PID set "SRV_PID=%%P"
)
exit /b 0

rem ═══════════ МЕНЮ ═══════════
:menu
cls
set "AR_TXT=ВЫКЛ"
if "%AUTORESTART%"=="1" set "AR_TXT=ВКЛ"
echo  ============================================
echo    44 WHITE CURTAIN - ПУЛЬТ УПРАВЛЕНИЯ
echo  ============================================
call :get_pid
if defined SRV_PID (
  echo   Состояние: РАБОТАЕТ   PID !SRV_PID!   Порт %WC_PORT%
) else (
  echo   Состояние: ОСТАНОВЛЕН   Порт %WC_PORT%
)
echo   Автоперезапуск: %AR_TXT%   PIN: %WC_PIN%   Админ: %WC_ADMIN%
echo  --------------------------------------------
echo   [1] Старт         [2] Стоп        [3] Рестарт
echo   [4] Статус/адреса [5] Лог         [6] Браузер
echo   [7] Автоперезапуск вкл/выкл       [8] Брандмауэр
echo   [9] Настройки - блокнот           [R] Обновить
echo   [0] Выход
echo  --------------------------------------------
choice /c 123456789R0 /n /t 5 /d R /m "  Выбор: "
set "CH=%errorlevel%"
if "%CH%"=="1"  goto :m_start
if "%CH%"=="2"  goto :m_stop
if "%CH%"=="3"  goto :m_restart
if "%CH%"=="4"  goto :m_status
if "%CH%"=="5"  goto :m_log
if "%CH%"=="6"  goto :m_browser
if "%CH%"=="7"  goto :m_auto
if "%CH%"=="8"  goto :m_fw
if "%CH%"=="9"  goto :m_settings
if "%CH%"=="10" goto :refresh
if "%CH%"=="11" goto :m_exit
goto :menu

:m_start
call :do_start
pause
goto :menu

:m_stop
call :do_stop
pause
goto :menu

:m_restart
call :do_stop
call :do_start
pause
goto :menu

:m_status
call :get_pid
if defined SRV_PID (echo  Состояние: РАБОТАЕТ, PID !SRV_PID!) else (echo  Состояние: ОСТАНОВЛЕН)
echo  Порт: %WC_PORT%
powershell -NoProfile -Command "try{ $r=Invoke-RestMethod -Uri 'http://127.0.0.1:%WC_PORT%/api/lan' -TimeoutSec 2; Write-Host ('  Игроков онлайн: '+$r.online); Write-Host '  Адреса для игроков:'; $r.addresses | ForEach-Object { Write-Host ('    http://'+$_+':%WC_PORT%') } } catch { Write-Host '  API не отвечает (сервер не запущен или ещё стартует).' }"
pause
goto :menu

:m_log
if exist "logs\web_server.log" (
  powershell -NoProfile -Command "Get-Content -Path 'logs\web_server.log' -Tail 30"
) else (
  echo [i] Лога пока нет. Он пишется с момента запуска сервера.
)
pause
goto :menu

:m_browser
start "" "http://127.0.0.1:%WC_PORT%"
goto :menu

:m_auto
if "%AUTORESTART%"=="1" (set "AUTORESTART=0") else (set "AUTORESTART=1")
echo [i] Автоперезапуск переключён.
timeout /t 1 /nobreak >nul
goto :menu

:m_fw
net session >nul 2>&1
if errorlevel 1 (
  echo [!] Запусти пульт от администратора, либо выполни вручную:
  echo     netsh advfirewall firewall add rule name="Metro44 Web" dir=in action=allow protocol=TCP localport=%WC_PORT% profile=any
  pause
  goto :menu
)
netsh advfirewall firewall show rule name="Metro44 Web" >nul 2>&1
if errorlevel 1 (
  netsh advfirewall firewall add rule name="Metro44 Web" dir=in action=allow protocol=TCP localport=%WC_PORT% profile=any >nul
  echo [OK] Правило создано.
) else (
  echo [OK] Правило уже есть.
)
pause
goto :menu

:m_settings
notepad "%~f0"
echo [i] Перезапускаю пульт, чтобы подхватить настройки...
start "" "%~f0"
exit

:m_exit
choice /c YN /n /m "  Остановить сервер перед выходом? [Y/N]: "
if "%errorlevel%"=="1" call :do_stop
echo  Пока, сталкер.
timeout /t 1 /nobreak >nul
exit

rem ═══════════ WATCHDOG (каждые 5с, пока меню ждёт ввод) ═══════════
:refresh
call :get_pid
if defined SRV_PID goto :menu
if not "%AUTORESTART%"=="1" goto :menu
if not "%STARTED%"=="1" goto :menu
echo [watchdog] Сервер упал - перезапускаю...
call :do_start
timeout /t 2 /nobreak >nul
goto :menu

rem ═══════════ СТАРТ ═══════════
:do_start
call :get_pid
if defined SRV_PID (
  echo [!] Сервер уже запущен, PID !SRV_PID!. Используй [3] Рестарт.
  exit /b 1
)
taskkill /fi "WINDOWTITLE eq %SRV_TITLE%" /f >nul 2>&1
if not exist "logs" mkdir "logs"
start "%SRV_TITLE%" /d "%~dp0" cmd /c ""%~f0" _run"
set "STARTED=1"
echo [i] Запускаю сервер, жду порт %WC_PORT%...
set /a W=0
:wait_up
call :get_pid
if defined SRV_PID goto :up_ok
set /a W+=1
if !W! GEQ 20 goto :up_fail
timeout /t 1 /nobreak >nul
goto :wait_up
:up_ok
echo [OK] Сервер работает, PID !SRV_PID!. Адрес: http://127.0.0.1:%WC_PORT%
exit /b 0
:up_fail
echo [X] Порт не поднялся за 20 секунд. Смотри окно %SRV_TITLE% и logs\web_server.log.
exit /b 1

rem ═══════════ СТОП: мягко, потом жёстко ═══════════
:do_stop
call :get_pid
if not defined SRV_PID (
  echo [i] Сервер не запущен.
  set "STARTED=0"
  exit /b 0
)
echo [i] Мягкая остановка: посылаю Ctrl+C в окно %SRV_TITLE%...
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; if($w.AppActivate('%SRV_TITLE%')){ Start-Sleep -Milliseconds 400; $w.SendKeys('^c') }" >nul 2>&1
set /a W=0
:wait_down
call :get_pid
if not defined SRV_PID goto :down_ok
set /a W+=1
if !W! GEQ 10 goto :down_force
timeout /t 1 /nobreak >nul
goto :wait_down
:down_force
echo [!] Мягко не вышло - добиваю жёстко (данные защитит автосейв).
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /c:":%WC_PORT% " ^| findstr /c:"LISTENING"') do taskkill /pid %%P /t /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq %SRV_TITLE%" /f >nul 2>&1
call :get_pid
if defined SRV_PID (
  echo [X] Не удалось освободить порт %WC_PORT%. Проверь Диспетчер задач.
  exit /b 1
)
:down_ok
echo [OK] Сервер остановлен.
set "STARTED=0"
exit /b 0

rem ═══════════ ОКНО СЕРВЕРА (run / _run) ═══════════
:run_server
title %SRV_TITLE%
call :preflight
echo.
echo  Окно сервера. Мягкая остановка: Ctrl+C, дождись "Сервер остановлен, БД закрыта".
echo  После Ctrl+C на вопрос cmd "Завершить пакетный файл?" отвечай N.
echo  Лог: logs\web_server.log
echo.
rem Потоки сливаем ВНУТРИ cmd (2>&1), а не в PowerShell:
rem иначе PS 5.1 считает каждую строку stderr (logging пишет туда) "ошибкой"
rem и рисует красные NativeCommandError поверх нормальных INFO-логов.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$OutputEncoding=[Console]::OutputEncoding=(New-Object System.Text.UTF8Encoding $false); $env:PYTHONUNBUFFERED='1'; cmd /c 'python -u server\web\app.py 2>&1' | Tee-Object -FilePath 'logs\web_server.log'; exit $LASTEXITCODE"
set "EXITCODE=%errorlevel%"
echo.
if not "%EXITCODE%"=="0" (
  color 0C
  echo [X] Сервер завершился с кодом %EXITCODE%.
  if exist "logs\metro_bot.log" (
    echo --- последние 25 строк logs\metro_bot.log ---
    powershell -NoProfile -Command "Get-Content -Path 'logs\metro_bot.log' -Tail 25"
  )
) else (
  echo [i] Сервер остановлен штатно.
)
echo.
pause
exit