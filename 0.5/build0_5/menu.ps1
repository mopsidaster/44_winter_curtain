# -*- coding: utf-8 -*-
# menu.ps1 - PowerShell меню для управления ботом (Билд 0.4.8.3)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$Green = "Green"
$Red = "Red"
$Yellow = "Yellow"
$Cyan = "Cyan"
$Magenta = "Magenta"
$White = "White"
$DarkGray = "DarkGray"

function Write-Header {
    Clear-Host
    Write-Host "===============================================" -ForegroundColor $Cyan
    Write-Host "   🚇 44: WHITE CURTAIN БОТ - УПРАВЛЕНИЕ" -ForegroundColor $Yellow
    Write-Host "   Билд 0.4.8.3 «Фракции и Контрабанда»" -ForegroundColor $Magenta
    Write-Host "===============================================" -ForegroundColor $Cyan
    Write-Host ""
}

function Write-Menu {
    Write-Header
    Write-Host "📋 ОСНОВНОЕ МЕНЮ:" -ForegroundColor $White
    Write-Host ""
    Write-Host "  [1] 🚀 Запустить бота" -ForegroundColor $Green
    Write-Host "  [2] 🛑 Остановить бота" -ForegroundColor $Red
    Write-Host "  [3] 🔄 Перезапустить бота" -ForegroundColor $Yellow
    Write-Host "  [4] 📊 Статус бота" -ForegroundColor $Cyan
    Write-Host ""
    Write-Host "🔑 КЛЮЧИ ДОСТУПА:" -ForegroundColor $White
    Write-Host ""
    Write-Host "  [5] 📋 Список всех ключей" -ForegroundColor $Cyan
    Write-Host "  [6] ✅ Список активированных" -ForegroundColor $Cyan
    Write-Host "  [7] 🕓 Список неактивированных" -ForegroundColor $Cyan
    Write-Host "  [8] 🔓 Отозвать ключ (сброс активации)" -ForegroundColor $Yellow
    Write-Host "  [9] 🗑️ Удалить ключ из БД" -ForegroundColor $Red
    Write-Host ""
    Write-Host "🗄️ БАЗА ДАННЫХ И ЛОГИ:" -ForegroundColor $White
    Write-Host ""
    Write-Host "  [10] 💾 Сделать бэкап metro.db" -ForegroundColor $Green
    Write-Host "  [11] 👥 Список игроков" -ForegroundColor $Cyan
    Write-Host "  [12] 🗑️ Удалить игрока" -ForegroundColor $Red
    Write-Host "  [13] 📝 Показать логи" -ForegroundColor $Cyan
    Write-Host "  [14] 🧹 Очистить логи" -ForegroundColor $DarkGray
    Write-Host "  [15] 💥 ВАЙП ИГРОВЫХ ДАННЫХ (без ключей)" -ForegroundColor $Red
    Write-Host ""
    Write-Host "🔧 СЛУЖЕБНОЕ:" -ForegroundColor $White
    Write-Host ""
    Write-Host "  [16] ✅ Проверить конфиги" -ForegroundColor $Green
    Write-Host "  [17] 🧪 Диагностика" -ForegroundColor $Magenta
    Write-Host "  [18] 📂 Открыть папку проекта" -ForegroundColor $Cyan
    Write-Host "  [0]  ❌ Выход" -ForegroundColor $Red
    Write-Host ""
    Write-Host "===============================================" -ForegroundColor $Cyan
    Write-Host ""
}

function Start-Bot {
    Write-Header
    Write-Host "🚀 ЗАПУСК БОТА..." -ForegroundColor $Green
    Write-Host ""

    if ($script:botProcess -and !$script:botProcess.HasExited) {
        Write-Host "⚠️ Бот уже запущен (PID: $($script:botProcess.Id))" -ForegroundColor $Yellow
        Pause
        return
    }

    Write-Host "Запуск Python скрипта..." -ForegroundColor $Cyan
    Write-Host "===============================================" -ForegroundColor $DarkGray
    Write-Host ""

    $script:botProcess = Start-Process -FilePath "python" -ArgumentList "main.py" -PassThru -WindowStyle Normal

    Write-Host "✅ Бот запущен (PID: $($script:botProcess.Id))" -ForegroundColor $Green
    Write-Host ""
    Write-Host "Нажмите любую клавишу для возврата в меню..." -ForegroundColor $DarkGray
    Pause
}

function Stop-Bot {
    Write-Header
    Write-Host "🛑 ОСТАНОВКА БОТА..." -ForegroundColor $Red
    Write-Host ""

    if ($script:botProcess -and !$script:botProcess.HasExited) {
        Write-Host "Останавливаем процесс (PID: $($script:botProcess.Id))..." -ForegroundColor $Yellow
        Stop-Process -Id $script:botProcess.Id -Force
        Write-Host "✅ Бот остановлен" -ForegroundColor $Green
    } else {
        Write-Host "⚠️ Бот не запущен или уже остановлен" -ForegroundColor $Yellow
    }

    Write-Host ""
    Pause
}

function Restart-Bot {
    Write-Header
    Write-Host "🔄 ПЕРЕЗАПУСК БОТА..." -ForegroundColor $Yellow
    Write-Host ""

    if ($script:botProcess -and !$script:botProcess.HasExited) {
        Write-Host "Останавливаем процесс (PID: $($script:botProcess.Id))..." -ForegroundColor $Yellow
        Stop-Process -Id $script:botProcess.Id -Force
        Start-Sleep -Seconds 2
    }

    Write-Host "Запускаем бота..." -ForegroundColor $Green
    $script:botProcess = Start-Process -FilePath "python" -ArgumentList "main.py" -PassThru -WindowStyle Normal

    Write-Host "✅ Бот перезапущен (PID: $($script:botProcess.Id))" -ForegroundColor $Green
    Write-Host ""
    Pause
}

function Show-Status {
    Write-Header
    Write-Host "📊 СТАТУС БОТА..." -ForegroundColor $Cyan
    Write-Host ""

    if ($script:botProcess -and !$script:botProcess.HasExited) {
        Write-Host "✅ Бот ЗАПУЩЕН" -ForegroundColor $Green
        Write-Host "   PID: $($script:botProcess.Id)" -ForegroundColor $White
    } else {
        Write-Host "❌ Бот НЕ ЗАПУЩЕН" -ForegroundColor $Red
    }

    Write-Host ""

    $dbPath = Join-Path $scriptPath "metro.db"

    if (Test-Path $dbPath) {
        $statsPy = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
cur = conn.cursor()
try:
    cur.execute('SELECT COUNT(*) FROM players')
    print('players:' + str(cur.fetchone()[0]))
except Exception:
    print('players:ERR')
try:
    cur.execute('SELECT COUNT(*) FROM access_keys')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM access_keys WHERE used_by IS NOT NULL')
    used = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM access_keys WHERE used_by IS NULL')
    unused = cur.fetchone()[0]
    print(f'keys:{total}:{used}:{unused}')
except Exception:
    print('keys:ERR:0:0')
conn.close()
"@

        $result = python -c $statsPy 2>&1

        Write-Host "📊 БД:" -ForegroundColor $Cyan
        foreach ($line in $result -split "`n") {
            if ($line -like "players:*") {
                $n = $line -replace "players:", ""
                Write-Host "   👥 Игроков: $n" -ForegroundColor $Green
            } elseif ($line -like "keys:*") {
                $parts = $line -replace "keys:", "" -split ":"
                Write-Host "   🔑 Ключей: $($parts[0]) | активировано: $($parts[1]) | свободно: $($parts[2])" -ForegroundColor $Green
            }
        }
    } else {
        Write-Host "   ❌ База данных не найдена: $dbPath" -ForegroundColor $Red
    }

    Write-Host ""
    Pause
}

function Show-Keys {
    param([string]$Mode = "all")

    Write-Header
    switch ($Mode) {
        "used"   { Write-Host "✅ АКТИВИРОВАННЫЕ КЛЮЧИ..." -ForegroundColor $Cyan }
        "unused" { Write-Host "🕓 НЕАКТИВИРОВАННЫЕ КЛЮЧИ..." -ForegroundColor $Cyan }
        default  { Write-Host "📋 ВСЕ КЛЮЧИ..." -ForegroundColor $Cyan }
    }
    Write-Host ""

    $dbPath = Join-Path $scriptPath "metro.db"
    if (-not (Test-Path $dbPath)) {
        Write-Host "❌ metro.db не найдена" -ForegroundColor $Red
        Pause
        return
    }

    $modePy = switch ($Mode) {
        "used"   { "used" }
        "unused" { "unused" }
        default  { "all" }
    }

    $pyCode = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
mode = '$modePy'

if mode == 'used':
    cur.execute('SELECT key, key_type, used_by, activated_at, expires_at, created_at FROM access_keys WHERE used_by IS NOT NULL ORDER BY activated_at DESC')
elif mode == 'unused':
    cur.execute('SELECT key, key_type, used_by, activated_at, expires_at, created_at FROM access_keys WHERE used_by IS NULL ORDER BY created_at DESC')
else:
    cur.execute('SELECT key, key_type, used_by, activated_at, expires_at, created_at FROM access_keys ORDER BY created_at DESC')

rows = cur.fetchall()
if not rows:
    print('EMPTY')
else:
    for r in rows:
        k = r['key'] or '?'
        t = r['key_type'] or '?'
        u = r['used_by']
        a = r['activated_at']
        e = r['expires_at']
        c = r['created_at']
        if u is None:
            status = 'свободен'
        else:
            status = f'активирован user_id={u}'
        exp = ''
        if e:
            exp = f' | истекает: {e}'
        act = f' | активирован: {a}' if a else ''
        created = f' | создан: {c}' if c else ''
        print(f'{k} | {t} | {status}{act}{exp}{created}')
conn.close()
"@

    $env:PYTHONIOENCODING = "utf-8"
    $result = python -X utf8 -c $pyCode 2>&1

    if ($result -eq "EMPTY" -or -not $result) {
        Write-Host "📭 Ключей нет" -ForegroundColor $Yellow
    } else {
        $count = 0
        foreach ($line in $result -split "`n") {
            $line = $line.TrimEnd()
            if (-not $line) { continue }
            $count++

            if ($Mode -eq "used") {
                Write-Host "  $line" -ForegroundColor $Green
            } elseif ($Mode -eq "unused") {
                Write-Host "  $line" -ForegroundColor $Yellow
            } else {
                if ($line -match "активирован") {
                    Write-Host "  $line" -ForegroundColor $Green
                } else {
                    Write-Host "  $line" -ForegroundColor $Yellow
                }
            }
        }
        Write-Host ""
        Write-Host "Всего: $count" -ForegroundColor $Cyan
    }

    Write-Host ""
    Pause
}

function Revoke-Key {
    Write-Header
    Write-Host "🔓 ОТОЗВАТЬ КЛЮЧ (сброс активации)..." -ForegroundColor $Yellow
    Write-Host ""
    Write-Host "Ключ останется в БД, но станет снова свободным." -ForegroundColor $DarkGray
    Write-Host ""

    $key = Read-Host "Введите ключ (MTR-XXXX-XXXX)"
    if (-not $key) { return }

    $dbPath = Join-Path $scriptPath "metro.db"

    $pyCode = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
cur = conn.cursor()
cur.execute('SELECT 1 FROM access_keys WHERE key = ?', ('$key',))
if not cur.fetchone():
    print('NOT_FOUND')
else:
    cur.execute('UPDATE access_keys SET used_by = NULL, activated_at = NULL, expires_at = NULL WHERE key = ?', ('$key',))
    conn.commit()
    print('OK')
conn.close()
"@

    $env:PYTHONIOENCODING = "utf-8"
    $result = python -X utf8 -c $pyCode 2>&1

    if ($result -eq "OK") {
        Write-Host "✅ Ключ отозван (сброшена активация)" -ForegroundColor $Green
    } else {
        Write-Host "❌ Ключ не найден" -ForegroundColor $Red
    }

    Write-Host ""
    Pause
}

function Delete-Key {
    Write-Header
    Write-Host "🗑️ УДАЛИТЬ КЛЮЧ ИЗ БД..." -ForegroundColor $Red
    Write-Host ""
    Write-Host "⚠️ Ключ будет полностью удалён из базы." -ForegroundColor $Yellow
    Write-Host ""

    $key = Read-Host "Введите ключ (MTR-XXXX-XXXX)"
    if (-not $key) { return }

    $dbPath = Join-Path $scriptPath "metro.db"

    $infoPy = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT key, key_type, used_by, activated_at, expires_at FROM access_keys WHERE key = ?', ('$key',))
r = cur.fetchone()
if not r:
    print('NOT_FOUND')
else:
    u = r['used_by']
    status = 'свободен' if u is None else 'активирован user_id=' + str(u)
    exp = ''
    if r['expires_at']:
        exp = ' | истекает: ' + str(r['expires_at'])
    act = ''
    if r['activated_at']:
        act = ' | активирован: ' + str(r['activated_at'])
    line = str(r['key']) + ' | ' + str(r['key_type']) + ' | ' + status + act + exp
    print(line)
conn.close()
"@

    $env:PYTHONIOENCODING = "utf-8"
    $info = python -X utf8 -c $infoPy 2>&1

    if ($info -eq "NOT_FOUND") {
        Write-Host "❌ Ключ не найден" -ForegroundColor $Red
        Pause
        return
    }

    if ($info -match "Traceback" -or $info -match "Error") {
        Write-Host "❌ Ошибка чтения ключа:" -ForegroundColor $Red
        Write-Host $info -ForegroundColor $DarkGray
        Pause
        return
    }

    Write-Host "Найден ключ:" -ForegroundColor $Cyan
    Write-Host "  $info" -ForegroundColor $White
    Write-Host ""

    $confirm = Read-Host "Удалить ключ полностью? Введите УДАЛИТЬ для подтверждения"

    if ($confirm -ne "УДАЛИТЬ" -and $confirm -ne "удалить" -and $confirm -ne "DELETE" -and $confirm -ne "delete") {
        Write-Host "❌ Отмена." -ForegroundColor $Yellow
        Pause
        return
    }

    $delPy = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
cur = conn.cursor()
cur.execute('DELETE FROM access_keys WHERE key = ?', ('$key',))
conn.commit()
deleted = cur.rowcount
conn.close()
print('OK:' + str(deleted))
"@

    $env:PYTHONIOENCODING = "utf-8"
    $result = python -X utf8 -c $delPy 2>&1

    if ($result -like "OK:1*") {
        Write-Host "✅ Ключ удалён из БД" -ForegroundColor $Green
    } elseif ($result -like "OK:0*") {
        Write-Host "⚠️ Ключ не был удалён (не найден?)" -ForegroundColor $Yellow
    } else {
        Write-Host "❌ Ошибка удаления: $result" -ForegroundColor $Red
    }

    Write-Host ""
    Pause
}

function Backup-DB {
    Write-Header
    Write-Host "💾 БЭКАП БАЗЫ ДАННЫХ..." -ForegroundColor $Green
    Write-Host ""

    if (-not (Test-Path "metro.db")) {
        Write-Host "❌ metro.db не найдена" -ForegroundColor $Red
        Pause
        return
    }

    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $backupDir = "backups"

    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir | Out-Null
    }

    $backupFile = "$backupDir\metro_$timestamp.db"

    Copy-Item "metro.db" $backupFile

    $size = [math]::Round((Get-Item $backupFile).Length / 1KB, 1)
    Write-Host "✅ Бэкап создан:" -ForegroundColor $Green
    Write-Host "   $backupFile ($size KB)" -ForegroundColor $White

    Write-Host ""
    Pause
}

function Show-Players {
    Write-Header
    Write-Host "👥 СПИСОК ИГРОКОВ..." -ForegroundColor $Cyan
    Write-Host ""

    $dbPath = Join-Path $scriptPath "metro.db"

    $pyCode = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
cur = conn.cursor()
try:
    cur.execute('SELECT user_id, name, level, location, is_alive FROM players ORDER BY level DESC LIMIT 30')
    rows = cur.fetchall()
    if not rows:
        print('Нет игроков')
    else:
        for r in rows:
            uid, name, lvl, loc, alive = r
            status = '💀' if not alive else '❤️'
            print(f'{status} {name} (Ур. {lvl}) | {uid} | {loc}')
except sqlite3.OperationalError as e:
    print(f'Ошибка: {e}')
conn.close()
"@

    $env:PYTHONIOENCODING = "utf-8"
    $result = python -X utf8 -c $pyCode 2>&1

    if ($result) {
        Write-Host $result -ForegroundColor $White
    } else {
        Write-Host "📭 Игроков нет" -ForegroundColor $Yellow
    }

    Write-Host ""
    Pause
}

function Delete-Player {
    Write-Header
    Write-Host "🗑️ УДАЛИТЬ ИГРОКА..." -ForegroundColor $Red
    Write-Host ""

    $uid = Read-Host "Введите user_id игрока"
    if (-not $uid) { return }

    $dbPath = Join-Path $scriptPath "metro.db"

    $namePy = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
cur = conn.cursor()
cur.execute('SELECT name FROM players WHERE user_id = ?', ($uid,))
row = cur.fetchone()
print(row[0] if row else 'NOT_FOUND')
conn.close()
"@

    $name = python -c $namePy 2>&1

    if ($name -eq "NOT_FOUND") {
        Write-Host "❌ Игрок с ID $uid не найден" -ForegroundColor $Red
        Pause
        return
    }

    Write-Host "⚠️ Найден игрок: $name" -ForegroundColor $Yellow
    $confirm = Read-Host "Удалить? (y/n)"

    if ($confirm -eq "y" -or $confirm -eq "Y") {
        $delPy = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
cur = conn.cursor()
cur.execute('DELETE FROM players WHERE user_id = ?', ($uid,))
conn.commit()
conn.close()
"@
        python -c $delPy 2>&1 | Out-Null
        Write-Host "✅ Игрок $name удалён" -ForegroundColor $Green
    } else {
        Write-Host "Отмена" -ForegroundColor $Yellow
    }

    Write-Host ""
    Pause
}

function Wipe-GameData {
    Write-Header
    Write-Host "💥 ВАЙП ИГРОВЫХ ДАННЫХ..." -ForegroundColor $Red
    Write-Host ""
    Write-Host "⚠️ ВНИМАНИЕ! Будут удалены:" -ForegroundColor $Yellow
    Write-Host "   • Все игроки (таблица players)" -ForegroundColor $White
    Write-Host "   • Все бригады (brigades, brigade_members, brigade_invites)" -ForegroundColor $White
    Write-Host ""
    Write-Host "✅ Ключи доступа (access_keys) НЕ будут удалены." -ForegroundColor $Green
    Write-Host ""

    $dbPath = Join-Path $scriptPath "metro.db"

    if (-not (Test-Path $dbPath)) {
        Write-Host "❌ metro.db не найдена" -ForegroundColor $Red
        Pause
        return
    }

    $statsPy = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
cur = conn.cursor()
try:
    cur.execute('SELECT COUNT(*) FROM players')
    players = cur.fetchone()[0]
except Exception:
    players = -1
try:
    cur.execute('SELECT COUNT(*) FROM access_keys')
    keys = cur.fetchone()[0]
except Exception:
    keys = -1
try:
    cur.execute('SELECT COUNT(*) FROM access_keys WHERE used_by IS NOT NULL')
    keys_used = cur.fetchone()[0]
except Exception:
    keys_used = -1
print(f'{players}|{keys}|{keys_used}')
conn.close()
"@

    $env:PYTHONIOENCODING = "utf-8"
    $stats = python -X utf8 -c $statsPy 2>&1
    $parts = $stats -split "\|"

    if ($parts.Length -ge 3) {
        Write-Host "📊 Сейчас в БД:" -ForegroundColor $Cyan
        Write-Host "   👥 Игроков: $($parts[0])" -ForegroundColor $White
        Write-Host "   🔑 Ключей всего: $($parts[1]) (активировано: $($parts[2]))" -ForegroundColor $White
        Write-Host ""
    }

    Write-Host "🛑 Бот должен быть ОСТАНОВЛЕН перед вайпом!" -ForegroundColor $Red
    Write-Host ""

    if ($script:botProcess -and !$script:botProcess.HasExited) {
        Write-Host "⚠️ Бот сейчас запущен (PID: $($script:botProcess.Id))" -ForegroundColor $Yellow
        $stopFirst = Read-Host "Остановить бота и продолжить вайп? (y/n)"
        if ($stopFirst -eq "y" -or $stopFirst -eq "Y") {
            Write-Host "Останавливаем бота..." -ForegroundColor $Yellow
            Stop-Process -Id $script:botProcess.Id -Force
            Start-Sleep -Seconds 2
            Write-Host "✅ Бот остановлен" -ForegroundColor $Green
        } else {
            Write-Host "Отмена вайпа." -ForegroundColor $Yellow
            Pause
            return
        }
    }

    Write-Host ""

    Write-Host "Для подтверждения введите слово  " -NoNewline -ForegroundColor $Yellow
    Write-Host "ВАЙП" -NoNewline -ForegroundColor $Red
    Write-Host "  (заглавными):" -ForegroundColor $Yellow
    $confirm1 = Read-Host

    if ($confirm1 -ne "ВАЙП" -and $confirm1 -ne "вайп" -and $confirm1 -ne "WIPE" -and $confirm1 -ne "wipe") {
        Write-Host "❌ Неверное подтверждение. Отмена." -ForegroundColor $Red
        Pause
        return
    }

    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $backupDir = "backups"
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir | Out-Null
    }
    $backupFile = "$backupDir\metro_before_wipe_$timestamp.db"
    Copy-Item $dbPath $backupFile
    Write-Host "💾 Создан бэкап перед вайпом: $backupFile" -ForegroundColor $Green
    Write-Host ""

    $wipePy = @"
import sqlite3
conn = sqlite3.connect(r'$dbPath')
cur = conn.cursor()

report = []

tables_to_clear = [
    ('players', 'DELETE FROM players'),
    ('brigade_members', 'DELETE FROM brigade_members'),
    ('brigade_invites', 'DELETE FROM brigade_invites'),
    ('brigades', 'DELETE FROM brigades'),
]

for name, sql in tables_to_clear:
    try:
        cur.execute(f'SELECT COUNT(*) FROM {name}')
        before = cur.fetchone()[0]
    except Exception:
        before = 0

    try:
        cur.execute(sql)
        report.append(f'{name}: удалено {before}')
    except Exception as e:
        report.append(f'{name}: ОШИБКА — {e}')

try:
    cur.execute('SELECT COUNT(*) FROM access_keys')
    keys_after = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM access_keys WHERE used_by IS NOT NULL')
    keys_used_after = cur.fetchone()[0]
    report.append(f'access_keys: сохранено {keys_after} (активировано {keys_used_after})')
except Exception as e:
    report.append(f'access_keys: ОШИБКА проверки — {e}')

conn.commit()
conn.close()
print('\n'.join(report))
"@

    $env:PYTHONIOENCODING = "utf-8"
    $result = python -X utf8 -c $wipePy 2>&1

    Write-Host "===============================================" -ForegroundColor $DarkGray
    Write-Host "📋 РЕЗУЛЬТАТ ВАЙПА:" -ForegroundColor $Cyan
    Write-Host "===============================================" -ForegroundColor $DarkGray

    if ($result) {
        Write-Host $result -ForegroundColor $White
    } else {
        Write-Host "(нет вывода)" -ForegroundColor $DarkGray
    }

    Write-Host "===============================================" -ForegroundColor $DarkGray
    Write-Host ""
    Write-Host "✅ Вайп завершён. Ключи доступа сохранены." -ForegroundColor $Green
    Write-Host "💾 Бэкап: $backupFile" -ForegroundColor $DarkGray
    Write-Host ""
    Pause
}

function Show-Logs {
    Write-Header
    Write-Host "📝 ПОСЛЕДНИЕ ЛОГИ..." -ForegroundColor $Cyan
    Write-Host ""

    if (Test-Path "logs") {
        $logFiles = Get-ChildItem -Path "logs" -Filter "*.log" | Sort-Object LastWriteTime -Descending
        if ($logFiles) {
            Write-Host "Выберите файл лога:" -ForegroundColor $White
            Write-Host ""
            for ($i = 0; $i -lt [Math]::Min($logFiles.Count, 10); $i++) {
                $size = [math]::Round($logFiles[$i].Length / 1KB, 1)
                Write-Host "  [$($i+1)] $($logFiles[$i].Name) ($size KB)" -ForegroundColor $Cyan
            }
            Write-Host ""
            Write-Host "  [0] Назад" -ForegroundColor $DarkGray
            Write-Host ""

            $choice = Read-Host "Выберите номер"
            if ($choice -eq "0") { return }

            $index = [int]$choice - 1
            if ($index -ge 0 -and $index -lt $logFiles.Count) {
                $file = $logFiles[$index]
                Write-Host ""
                Write-Host "===============================================" -ForegroundColor $DarkGray
                Write-Host "📄 $($file.Name)" -ForegroundColor $Yellow
                Write-Host "===============================================" -ForegroundColor $DarkGray
                Write-Host ""

                Get-Content -Path $file.FullName -Tail 80 -Encoding UTF8

                Write-Host ""
                Write-Host "===============================================" -ForegroundColor $DarkGray
                Write-Host "Показаны последние 80 строк" -ForegroundColor $DarkGray
            }
        } else {
            Write-Host "📭 Логов нет" -ForegroundColor $Yellow
        }
    } else {
        Write-Host "📭 Папка logs не найдена" -ForegroundColor $Yellow
    }

    Write-Host ""
    Pause
}

function Clear-Logs {
    Write-Header
    Write-Host "🧹 ОЧИСТКА ЛОГОВ..." -ForegroundColor $DarkGray
    Write-Host ""

    if (Test-Path "logs") {
        $logFiles = Get-ChildItem -Path "logs" -Filter "*.log"
        if ($logFiles) {
            Write-Host "Найдено $($logFiles.Count) файлов логов" -ForegroundColor $Yellow
            $confirm = Read-Host "Удалить все логи? (y/n)"
            if ($confirm -eq "y" -or $confirm -eq "Y") {
                foreach ($file in $logFiles) {
                    Remove-Item -Path $file.FullName -Force
                }
                Write-Host "✅ Логи очищены" -ForegroundColor $Green
            } else {
                Write-Host "Отмена" -ForegroundColor $Yellow
            }
        } else {
            Write-Host "📭 Логов нет" -ForegroundColor $Yellow
        }
    } else {
        Write-Host "📭 Папка logs не найдена" -ForegroundColor $Yellow
    }

    Write-Host ""
    Pause
}

function Check-Configs {
    Write-Header
    Write-Host "✅ ПРОВЕРКА КОНФИГОВ..." -ForegroundColor $Green
    Write-Host ""

    $configs = @(
        "ammo.json", "armor.json", "balance.json", "diseases.json",
        "factions.json", "filters.json", "food.json", "health.json",
        "items.json", "magazines.json", "melee.json", "modules.json",
        "mutants.json", "pharmacy.json", "stations.json", "weapons.json"
    )

    $errors = 0
    foreach ($cfg in $configs) {
        $path = "config\$cfg"
        if (-not (Test-Path $path)) {
            Write-Host "  ❌ $cfg — НЕ НАЙДЕН" -ForegroundColor $Red
            $errors++
            continue
        }

        $result = python -c "import json; json.load(open(r'$path', encoding='utf-8')); print('OK')" 2>&1
        if ($result -eq "OK") {
            Write-Host "  ✅ $cfg" -ForegroundColor $Green
        } else {
            Write-Host "  ⚠️ $cfg — ОШИБКА JSON" -ForegroundColor $Red
            Write-Host "     $result" -ForegroundColor $DarkGray
            $errors++
        }
    }

    Write-Host ""
    if ($errors -eq 0) {
        Write-Host "✅ Все конфиги в порядке!" -ForegroundColor $Green
    } else {
        Write-Host "⚠️ Найдено ошибок: $errors" -ForegroundColor $Red
    }

    Write-Host ""
    Pause
}

function Run-Diagnostics {
    Write-Header
    Write-Host "🔧 ДИАГНОСТИКА..." -ForegroundColor $Magenta
    Write-Host ""

    Write-Host "📁 Проверка файлов:" -ForegroundColor $Cyan
    $files = @(
        "main.py",
        "config/map_config.py",
        "config/balance.json",
        "config/weapons.json",
        "config/stations.json",
        "config/factions.json",
        "config/armor.json",
        "database/db.py"
    )
    foreach ($file in $files) {
        if (Test-Path $file) {
            Write-Host "  ✅ $file" -ForegroundColor $Green
        } else {
            Write-Host "  ❌ $file" -ForegroundColor $Red
        }
    }

    Write-Host ""
    Write-Host "📁 Проверка папок:" -ForegroundColor $Cyan
    $dirs = @("config", "database", "func", "utils", "logs")
    foreach ($dir in $dirs) {
        if (Test-Path $dir) {
            Write-Host "  ✅ $dir" -ForegroundColor $Green
        } else {
            Write-Host "  ❌ $dir" -ForegroundColor $Red
        }
    }

    Write-Host ""
    Write-Host "📦 Проверка Python пакетов:" -ForegroundColor $Cyan
    $packages = @("discord", "aiosqlite", "aiohttp")
    foreach ($pkg in $packages) {
        $result = python -c "import $pkg; print('OK')" 2>$null
        if ($result -eq "OK") {
            Write-Host "  ✅ $pkg" -ForegroundColor $Green
        } else {
            Write-Host "  ❌ $pkg" -ForegroundColor $Red
        }
    }

    Write-Host ""
    Write-Host "📊 Версия Python:" -ForegroundColor $Cyan
    python --version

    Write-Host ""
    Write-Host "🗄️ БД:" -ForegroundColor $Cyan
    if (Test-Path "metro.db") {
        $size = [math]::Round((Get-Item "metro.db").Length / 1KB, 1)
        Write-Host "  ✅ metro.db ($size KB)" -ForegroundColor $Green
    } else {
        Write-Host "  ❌ metro.db не найдена" -ForegroundColor $Red
    }

    Write-Host ""
    Pause
}

function Open-ProjectFolder {
    Write-Header
    Write-Host "📂 ОТКРЫТЬ ПАПКУ ПРОЕКТА..." -ForegroundColor $Cyan
    Write-Host ""

    Invoke-Item $scriptPath
    Write-Host "✅ Папка открыта" -ForegroundColor $Green
    Write-Host ""
    Pause
}

# ==================== ОСНОВНОЙ ЦИКЛ ====================

$script:botProcess = $null

do {
    Write-Menu
    $choice = Read-Host "Выберите действие"

    switch ($choice) {
        "1" { Start-Bot }
        "2" { Stop-Bot }
        "3" { Restart-Bot }
        "4" { Show-Status }
        "5" { Show-Keys -Mode "all" }
        "6" { Show-Keys -Mode "used" }
        "7" { Show-Keys -Mode "unused" }
        "8" { Revoke-Key }
        "9" { Delete-Key }
        "10" { Backup-DB }
        "11" { Show-Players }
        "12" { Delete-Player }
        "13" { Show-Logs }
        "14" { Clear-Logs }
        "15" { Wipe-GameData }
        "16" { Check-Configs }
        "17" { Run-Diagnostics }
        "18" { Open-ProjectFolder }
        "0" {
            Write-Host ""
            Write-Host "До свидания!" -ForegroundColor $Green
            if ($script:botProcess -and !$script:botProcess.HasExited) {
                Stop-Process -Id $script:botProcess.Id -Force
            }
            break
        }
        default {
            Write-Host "❌ Неверный выбор!" -ForegroundColor $Red
            Start-Sleep -Seconds 1
        }
    }
} while ($choice -ne "0")