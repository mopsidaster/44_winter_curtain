@echo off
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8
set WC_HOST=0.0.0.0
set WC_PORT=8080
set WC_EVENTS=1
set WC_AUTOSAVE=1
rem set WC_PIN=1234
cd /d "%~dp0"

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

echo.
echo  Подключение по Radmin VPN: адрес 26.x.x.x этого ПК, порт %WC_PORT%
echo  Игроки открывают в браузере: http://26.x.x.x:%WC_PORT%
echo.
python server\web\app.py
pause