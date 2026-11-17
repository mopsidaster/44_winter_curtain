let currentUser = "";
let globalData = {};
let isLoggedIn = false;
let tempSkills = { "сила": 0, "выносливость": 0, "стойкость": 0, "меткость": 0, "здоровье": 0, "инженерия": 0 };
let maxPoints = 10;

// Утилиты
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
function showScreen(id) {
    document.querySelectorAll('.terminal-container').forEach(el => el.style.display = 'none');
    document.getElementById(id).style.display = 'flex';
}

async function fetchData() {
    const res = await fetch('/api/data');
    globalData = await res.json();
}

async function saveData() {
    await fetch('/api/update', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(globalData) });
}

// === АВТОРИЗАЦИЯ ===
async function login() {
    const u = document.getElementById('auth-user').value.trim().toLowerCase();
    const p = document.getElementById('auth-pass').value;
    await fetchData();

    if (globalData.users && globalData.users[u] && globalData.users[u].password === p) {
        currentUser = u;
        isLoggedIn = true;

        if (globalData.players[u] && globalData.players[u].prologue_completed) {
            showScreen('game-screen');
            updateMainMenu();
        } else {
            showScreen('create-screen');
            updateSkillsUI();
        }
    } else alert("Неверный логин");
}

async function register() {
    const u = document.getElementById('auth-user').value.trim().toLowerCase();
    const p = document.getElementById('auth-pass').value;
    await fetchData();
    if (!globalData.users[u]) {
        globalData.users[u] = { password: p, isAdmin: false };
        globalData.players[u] = { user_id: Math.floor(Math.random()*10000), hp: 30, max_hp: 30, money: 250, inventory: {}, location: "бульвар_дмитрия_донского", prologue_completed: false };
        await saveData();
        alert("Успешно! Войдите.");
    } else alert("Логин занят");
}

// === ПРОЛОГ ===
function updateSkillsUI() {
    const container = document.getElementById('skills-menu');
    let spent = 0;
    for (let s in tempSkills) spent += tempSkills[s];
    let left = maxPoints - spent;

    let html = "";
    for (let s in tempSkills) {
        html += `<div class="stat-line" style="margin-bottom: 8px;">
            <span>${s.toUpperCase()}: ${tempSkills[s]}</span>
            <button class="term-btn small" onclick="addSkill('${s}')" ${left <= 0 ? 'disabled' : ''}>+</button>
        </div>`;
    }
    html += `<div class="stat-line" style="color:var(--term-amber); margin-top:15px;"><span>Осталось:</span> <span>${left}</span></div>`;
    if (left === 0) html += `<button class="term-btn success" style="width:100%; margin-top:20px;" onclick="finishPrologue()">НАЧАТЬ ПУТЬ</button>`;
    container.innerHTML = html;
}

function addSkill(skill) {
    let spent = 0;
    for (let s in tempSkills) spent += tempSkills[s];
    if (spent < maxPoints) { tempSkills[skill]++; updateSkillsUI(); }
}

async function finishPrologue() {
    const name = document.getElementById('char-name').value.trim();
    if (!name) return alert("Введите имя!");

    const p = globalData.players[currentUser];
    Object.assign(p, { name, origin: document.getElementById('char-origin').value, prologue_completed: true });

    await saveData();
    await fetch('/api/create_character', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ player: p, name, skills: tempSkills })
    });

    showScreen('game-screen');
    updateMainMenu();
}

// === ГЛАВНОЕ МЕНЮ (РЕНДЕР ОТ PYTHON) ===
async function updateMainMenu() {
    const p = globalData.players[currentUser];
    const res = await fetch('/api/main_menu', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ player: p }) });
    const data = await res.json();

    if (data.status === 'ok') {
        const menu = data.menu;
        p.hp = menu.hp; // Синхронизация

        // Отрисовка статов
        document.getElementById('header-user').innerText = currentUser.toUpperCase();
        document.getElementById('header-location').innerText = `📍 ${menu.location.toUpperCase()}`;
        document.getElementById('player-stats').innerHTML = `
            <div>❤️ HP: ${menu.hp} / ${menu.max_hp}</div>
            <div>💰 Никели: ${menu.money}</div>
        `;

        // Отрисовка кнопок
        const btnContainer = document.getElementById('main-buttons');
        btnContainer.innerHTML = `
            <button class="term-btn" onclick="openMoveMenu()">🗺️ ПЕРЕМЕСТИТЬСЯ</button>
            <button class="term-btn" onclick="alert('Действия в разработке')">🎯 ДЕЙСТВИЯ</button>
            <button class="term-btn" onclick="alert('Инвентарь в разработке')">🎒 РЮКЗАК</button>
            <button class="term-btn" onclick="alert('Карта в разработке')">🚇 КАРТА</button>
            <button class="term-btn" onclick="alert('Статус в разработке')">📊 СТАТУС</button>
            <button class="term-btn" onclick="alert('Фракции в разработке')">🏴 ФРАКЦИИ</button>
        `;

        if (menu.buttons.npc) {
            btnContainer.innerHTML += `<button class="term-btn warning" onclick="openNpcMenu()">👥 NPC РЯДОМ</button>`;
        }
        if (menu.buttons.trade) {
            btnContainer.innerHTML += `<button class="term-btn success" onclick="alert('Торговля в разработке')">🏪 ТОРГОВЛЯ</button>`;
        }

        btnContainer.innerHTML += `<button class="term-btn danger" style="margin-top:20px;" onclick="logout()">🔌 ВЫЙТИ</button>`;
    }
}

// === ПЕРЕМЕЩЕНИЕ ===
async function openMoveMenu() {
    document.getElementById('move-modal').style.display = 'flex';
    const container = document.getElementById('move-stations');
    container.innerHTML = "Загрузка...";

    const p = globalData.players[currentUser];
    const res = await fetch('/api/move/connections', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ player: p }) });
    const data = await res.json();

    if (data.status === 'ok') {
        container.innerHTML = "";
        data.stations.forEach(st => {
            container.innerHTML += `<button class="term-btn" onclick="doMove('${st.id}')">${st.name} (Опасность: ${st.danger})</button>`;
        });
    }
}

async function doMove(dest) {
    closeModal('move-modal');
    const p = globalData.players[currentUser];
    const res = await fetch('/api/move/action', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ player: p, destination: dest }) });
    const data = await res.json();

    if (data.status === 'ok') {
        document.getElementById('game-log').innerHTML = `<div>> ${data.message}</div>` + document.getElementById('game-log').innerHTML;
        p.hp = data.player_hp;
        p.location = data.new_location;
        await saveData();
        updateMainMenu(); // Перерисовываем меню (вдруг появилась торговля)
    }
}

// === NPC ===
async function openNpcMenu() {
    document.getElementById('npc-modal').style.display = 'flex';
    const container = document.getElementById('npc-list');
    container.innerHTML = "...";

    const p = globalData.players[currentUser];
    const res = await fetch('/api/npcs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ player: p }) });
    const data = await res.json();

    if (data.status === 'ok') {
        container.innerHTML = "";
        data.npcs.forEach(npc => {
            container.innerHTML += `<button class="term-btn" onclick="startDialog('${npc.id}')">${npc.emoji} ${npc.name}</button>`;
        });
    }
}

async function startDialog(npcId, nodeId = null) {
    closeModal('npc-modal');
    document.getElementById('dialog-modal').style.display = 'flex';

    const p = globalData.players[currentUser];
    const res = await fetch('/api/dialog', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ player: p, npc_id: npcId, node_id: nodeId }) });
    const data = await res.json();

    if (data.status === 'ok') {
        document.getElementById('dialog-speaker').innerText = data.speaker;
        document.getElementById('dialog-text').innerText = data.text;
        const opts = document.getElementById('dialog-options');
        opts.innerHTML = "";
        data.options.forEach(opt => {
            let btn = document.createElement('button');
            btn.className = 'term-btn';
            btn.innerText = opt.label;
            btn.onclick = () => {
                if (opt.next) startDialog(npcId, opt.next);
                else if (opt.action) alert("Действие в разработке");
                else closeModal('dialog-modal');
            };
            opts.appendChild(btn);
        });
    }
}

function logout() { location.reload(); }
window.onload = () => fetchData();