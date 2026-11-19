/* 44 WHITE CURTAIN — панель бригад. Состав, режимы, приглашения, список бригад.
   Логика живёт в игре (func.social.brigade_manager), здесь только интерфейс. */
(() => {
'use strict';
const WC = window.WC; if (!WC) { console.warn('[brigada] нет шины WC'); return; }
if (window.__WCBRIGADA__) return;
window.__WCBRIGADA__ = true;

const CSS = `
#wcbrig.wcb{position:fixed;inset:0;z-index:8600;display:flex;justify-content:flex-end;
 font:14px/1.5 "Segoe UI",Roboto,Inter,system-ui,sans-serif;
 --void:#07090b;--surf:#10151a;--panel:#161d24;--over:#1c252e;--edge:#2b3844;--edge2:#202b36;
 --ink:#ece4d3;--mute:#a8bac6;--dim:#8b9daa;--amber:#ffb02e;--gold:#ffd23f;--rad:#66ff99;
 --rust:#ff6b5c;--steel:#6cb8ff;--track:#0a0e12}
#wcbrig.wcb.hidden{display:none!important}
#wcbrig.wcb *{box-sizing:border-box}
#wcbrig .wcb-scrim{position:absolute;inset:0;background:rgba(5,8,12,.5);backdrop-filter:blur(2px)}
#wcbrig .wcb-panel{position:relative;width:min(470px,96vw);height:100%;display:flex;flex-direction:column;
 background:linear-gradient(180deg,var(--surf),var(--void));border-left:1px solid var(--edge);
 box-shadow:-30px 0 80px rgba(0,0,0,.6);color:var(--ink)}
#wcbrig .wcb-head{flex:0 0 auto;display:flex;align-items:center;gap:10px;padding:12px 14px;
 background:linear-gradient(180deg,var(--over),var(--surf));border-bottom:1px solid var(--edge)}
#wcbrig .wcb-head h3{margin:0;font:800 13px/1.2 ui-monospace,monospace;letter-spacing:2px;color:#fff}
#wcbrig .wcb-tabs{display:flex;gap:4px;margin-left:auto}
#wcbrig .wcb-tab{padding:6px 10px;border-radius:8px;border:1px solid var(--edge);background:var(--panel);
 color:var(--mute);font:600 11px inherit;cursor:pointer;display:inline-flex;align-items:center;gap:5px}
#wcbrig .wcb-tab:hover{border-color:var(--amber);color:var(--ink)}
#wcbrig .wcb-tab.active{border-color:var(--amber);color:var(--amber);background:#2a1e0c}
#wcbrig .wcb-tab em{font-style:normal;font:700 10px ui-monospace,monospace;background:var(--rust);color:#fff;
 border-radius:99px;padding:1px 5px}
#wcbrig .wcb-tab em.hidden{display:none}
#wcbrig .wcb-x{width:32px;height:32px;flex:0 0 auto;border-radius:8px;border:1px solid var(--edge);
 background:var(--panel);color:var(--mute);cursor:pointer;font-size:15px;line-height:1}
#wcbrig .wcb-x:hover{border-color:var(--rust);color:#fff;background:#5c2620}
#wcbrig .wcb-body{flex:1 1 auto;overflow-y:auto;padding:13px;display:flex;flex-direction:column;gap:11px}
#wcbrig .wcb-card{background:var(--panel);border:1px solid var(--edge);border-radius:11px;padding:12px}
#wcbrig .wcb-card>h4{margin:0 0 9px;font:700 10px ui-monospace,monospace;letter-spacing:1.5px;
 color:var(--dim);text-transform:uppercase;display:flex;align-items:center;gap:7px}
#wcbrig .wcb-card>h4 em{margin-left:auto;font-style:normal;color:var(--dim);font-size:10px}
#wcbrig .wcb-name{display:flex;align-items:center;gap:9px;margin-bottom:6px}
#wcbrig .wcb-name b{font:800 16px/1.2 ui-monospace,monospace;color:#fff;min-width:0;word-break:break-word}
#wcbrig .wcb-badge{flex:0 0 auto;padding:3px 8px;border-radius:99px;font:700 9.5px ui-monospace,monospace;
 border:1px solid currentColor}
#wcbrig .wcb-desc{margin:0 0 9px;font-size:11.5px;color:#c2cfd8;border-left:2px solid var(--edge);padding-left:9px}
#wcbrig .wcb-kv{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
#wcbrig .wcb-kv span{padding:3px 8px;border-radius:99px;border:1px solid var(--edge);background:var(--void);
 font:600 10px ui-monospace,monospace;color:var(--mute)}
#wcbrig .wcb-mem{display:flex;flex-direction:column;gap:5px}
#wcbrig .wcb-mem-row{display:flex;align-items:center;gap:8px;padding:7px 9px;border-radius:8px;
 background:var(--void);border:1px solid var(--edge2)}
#wcbrig .wcb-mem-row.dead{opacity:.6}
#wcbrig .wcb-role{flex:0 0 auto;font-size:13px}
#wcbrig .wcb-mem-main{flex:1 1 auto;min-width:0}
#wcbrig .wcb-mem-main b{display:block;font:600 12.5px inherit;color:var(--ink);overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
#wcbrig .wcb-mem-main span{display:block;font-size:10.5px;color:var(--dim)}
#wcbrig .wcb-dot{flex:0 0 auto;width:8px;height:8px;border-radius:50%;background:#4c5a67}
#wcbrig .wcb-dot.on{background:var(--rad);box-shadow:0 0 7px var(--rad)}
#wcbrig .wcb-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:8px 12px;
 border-radius:8px;border:1px solid #3d5266;cursor:pointer;color:var(--ink);
 background:linear-gradient(180deg,var(--over),var(--panel));font:600 11.5px/1 inherit;
 box-shadow:0 2px 0 rgba(4,7,10,.8)}
#wcbrig .wcb-btn:hover:not(:disabled){border-color:var(--amber);color:#fff}
#wcbrig .wcb-btn:disabled{opacity:.42;cursor:not-allowed}
#wcbrig .wcb-btn:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
#wcbrig .wcb-btn.go{border-color:#3ba46c;color:#eafff2;background:linear-gradient(180deg,#37a065,#1f6b41)}
#wcbrig .wcb-btn.stop{border-color:#b8564c;color:#ffeceb;background:linear-gradient(180deg,#a34a41,#6b2c25)}
#wcbrig .wcb-btn.on{border-color:var(--amber);color:var(--amber);background:#2a1e0c}
#wcbrig .wcb-btn.sm{padding:5px 8px;font-size:10.5px}
#wcbrig .wcb-row{display:flex;gap:6px;margin-top:10px}
#wcbrig .wcb-row>*{flex:1}
#wcbrig .wcb-seg{display:flex;border:1px solid var(--edge);border-radius:8px;overflow:hidden;margin-bottom:10px}
#wcbrig .wcb-seg button{flex:1;padding:8px;border:0;background:var(--void);color:var(--mute);
 font:600 11.5px inherit;cursor:pointer}
#wcbrig .wcb-seg button+button{border-left:1px solid var(--edge)}
#wcbrig .wcb-seg button.on{background:#2a1e0c;color:var(--amber)}
#wcbrig .wcb-seg button:disabled{opacity:.45;cursor:not-allowed}
#wcbrig .wcb-fld{display:flex;flex-direction:column;gap:5px;margin-bottom:9px}
#wcbrig .wcb-fld span{font-size:10.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.8px}
#wcbrig input,#wcbrig textarea{width:100%;padding:8px 10px;border-radius:8px;border:1px solid var(--edge);
 background:var(--void);color:var(--ink);font:inherit;font-size:12.5px}
#wcbrig input:focus,#wcbrig textarea:focus{outline:none;border-color:var(--amber)}
#wcbrig textarea{resize:vertical;min-height:56px}
#wcbrig .wcb-inv{display:flex;flex-direction:column;gap:8px}
#wcbrig .wcb-inv-row{padding:10px;border-radius:9px;background:var(--void);border:1px solid var(--edge)}
#wcbrig .wcb-inv-row b{display:block;font:700 13px inherit;color:#fff;margin-bottom:3px}
#wcbrig .wcb-inv-row span{display:block;font-size:11px;color:var(--mute)}
#wcbrig .wcb-timer{font:700 11px ui-monospace,monospace;color:var(--gold)}
#wcbrig .wcb-timer.low{color:var(--rust)}
#wcbrig .wcb-list{display:flex;flex-direction:column;gap:8px}
#wcbrig .wcb-b-row{padding:10px;border-radius:9px;background:var(--void);border:1px solid var(--edge2)}
#wcbrig .wcb-b-row.mine{border-color:var(--amber)}
#wcbrig .wcb-b-top{display:flex;align-items:center;gap:8px;margin-bottom:5px}
#wcbrig .wcb-b-top b{font:700 13px inherit;color:#fff;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#wcbrig .wcb-b-top em{margin-left:auto;font-style:normal;font:600 10.5px ui-monospace,monospace;color:var(--dim)}
#wcbrig .wcb-b-mem{font-size:11px;color:var(--mute);line-height:1.6}
#wcbrig .wcb-empty{font-size:11.5px;color:var(--dim);line-height:1.55}
#wcbrig .wcb-note{font-size:10.5px;color:var(--dim);line-height:1.5;margin-top:8px}
#wcbrig .wcb-err{padding:8px 10px;border-radius:8px;border:1px solid rgba(255,107,92,.5);
 background:rgba(30,15,13,.9);color:#ffb3aa;font-size:11.5px}
#wcbrig .wcb-err.hidden{display:none}
#wcbrig .wcb-body{scrollbar-width:thin;scrollbar-color:#c97f10 var(--track)}
#wcbrig .wcb-body::-webkit-scrollbar{width:10px}
#wcbrig .wcb-body::-webkit-scrollbar-track{background:var(--track);border-left:1px solid var(--edge2)}
#wcbrig .wcb-body::-webkit-scrollbar-thumb{border:2px solid var(--track);border-radius:6px;
 background:linear-gradient(180deg,var(--amber),#c97f10)}
@media(max-width:620px){#wcbrig .wcb-panel{width:100vw}}
`;
(function(){ let s=document.getElementById('wcb-css');
  if(!s){ s=document.createElement('style'); s.id='wcb-css'; document.head.appendChild(s); } s.textContent=CSS; })();

const esc = s => String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const sfx = f => { try { WC.sfx && WC.sfx(f); } catch(_){} };
const toast = (t,k) => { try { WC.toast && WC.toast(t,k); } catch(_){} };
const api = (p,b) => WC.api(p,b);

const B = { open:false, tab:'mine', data:null, loading:false, busy:false, err:'', timer:0 };

let HOST = document.getElementById('wcbrig');
if (!HOST) { HOST = document.createElement('div'); HOST.id='wcbrig'; document.body.appendChild(HOST); }
HOST.className = 'wcb hidden'; HOST.setAttribute('aria-hidden','true');
HOST.innerHTML = `
<div class="wcb-scrim"></div>
<div class="wcb-panel" role="dialog" aria-modal="true" aria-label="Бригада">
 <header class="wcb-head">
  <h3>БРИГАДА</h3>
  <div class="wcb-tabs">
   <button class="wcb-tab active" data-tab="mine" type="button">Моя</button>
   <button class="wcb-tab" data-tab="invites" type="button">Приглашения <em data-r="invBadge" class="hidden">0</em></button>
   <button class="wcb-tab" data-tab="all" type="button">Все</button>
  </div>
  <button class="wcb-x" data-r="close" type="button" aria-label="Закрыть">✕</button>
 </header>
 <div class="wcb-body">
  <div class="wcb-err hidden" data-r="err"></div>
  <div data-r="content"></div>
 </div>
</div>`;
const R = {}; HOST.querySelectorAll('[data-r]').forEach(n => R[n.dataset.r] = n);
const TABS = [...HOST.querySelectorAll('.wcb-tab')];

/* ═══════════ ДАННЫЕ ═══════════ */
async function refresh(quiet){
  if (B.loading) return;
  B.loading = true;
  const r = await api('/api/brigada/state');
  B.loading = false;
  if (!r || !r.ok || !r.d || !r.d.ok) {
    B.err = (r && r.d && r.d.error) || 'Не удалось получить данные бригад';
    render(); return;
  }
  B.err = ''; B.data = r.d;
  badge(); render();
  if (!quiet) tickTimer();
}
function badge(){
  const n = (B.data && B.data.invites ? B.data.invites.length : 0);
  if (R.invBadge) { R.invBadge.textContent = String(n); R.invBadge.classList.toggle('hidden', !n); }
  const top = document.getElementById('brigada-count');
  if (top) { top.textContent = String(n); top.classList.toggle('hidden', !n); }
  const btn = document.getElementById('brigada-btn');
  if (btn) btn.classList.toggle('has-unread', !!n);
}
function tickTimer(){
  clearInterval(B.timer);
  if (!B.open || !B.data || !B.data.invites || !B.data.invites.length) return;
  B.timer = setInterval(() => {
    let alive = false;
    B.data.invites.forEach(i => { i.expires_in = Math.max(0, i.expires_in - 1); if (i.expires_in > 0) alive = true; });
    HOST.querySelectorAll('[data-exp]').forEach(n => {
      const inv = B.data.invites.find(x => x.id === n.dataset.exp);
      if (!inv) return;
      n.textContent = inv.expires_in + ' с';
      n.classList.toggle('low', inv.expires_in <= 15);
    });
    if (!alive) { clearInterval(B.timer); refresh(true); }
  }, 1000);
}
async function act(path, body, okMsg){
  if (B.busy) return;
  B.busy = true; B.err = ''; render();
  const r = await api(path, body || {});
  B.busy = false;
  if (!r || !r.ok || !r.d || !r.d.ok) {
    B.err = (r && r.d && r.d.error) || 'Действие не выполнено';
    render(); toast(B.err, 'error'); return false;
  }
  sfx('button.mp3');
  if (okMsg) toast(okMsg, 'success');
  await refresh(true);
  return true;
}

/* ═══════════ ОТРИСОВКА ═══════════ */
function memRow(m, canKick){
  return `<div class="wcb-mem-row ${m.alive ? '' : 'dead'}">
    <span class="wcb-role">${m.leader ? '👑' : '👤'}</span>
    <span class="wcb-dot ${m.online ? 'on' : ''}" title="${m.online ? 'в сети' : 'не в сети'}"></span>
    <div class="wcb-mem-main"><b>${esc(m.name)}${m.login ? ' · ' + esc(m.login) : ''}</b>
      <span>📍 ${esc(m.location_name)}${m.alive ? '' : ' · 💀 мёртв'}${m.sleeping ? ' · 😴 спит' : ''}</span></div>
    ${canKick && !m.leader ? `<button class="wcb-btn sm stop" data-kick="${m.id}" type="button">Исключить</button>` : ''}
  </div>`;
}
function mineView(){
  const d = B.data;
  if (!d) return '<div class="wcb-empty">Загружаю…</div>';
  if (!d.me.has_character)
    return '<div class="wcb-card"><h4>Нет персонажа</h4><div class="wcb-empty">Сначала создай персонажа командой <b>/start</b>, потом собери бригаду.</div></div>';
  const b = d.mine;
  if (!b) {
    return `<div class="wcb-card"><h4>Создать бригаду</h4>
      <div class="wcb-empty" style="margin-bottom:10px">До 3 человек. Бригада наследует твою фракцию.
        Режим «Вместе» — переходы идут группой, «Расход» — каждый сам.</div>
      <label class="wcb-fld"><span>Название</span>
        <input data-r2="cName" maxlength="50" placeholder="Стальные крысы"></label>
      <label class="wcb-fld"><span>Описание (необязательно)</span>
        <textarea data-r2="cDesc" maxlength="300" rows="3" placeholder="Кратко о целях группы"></textarea></label>
      <div class="wcb-row"><button class="wcb-btn go" data-a="create" type="button" ${B.busy?'disabled':''}>🤝 Создать</button></div>
      <div class="wcb-note">Ты сейчас на станции <b>${esc(d.location)}</b>. Приглашать можно только тех, кто рядом.</div>
    </div>`;
  }
  const cand = d.candidates || [];
  const inviteBlock = b.i_lead ? `<div class="wcb-card"><h4>Пригласить <em>${b.full ? 'состав полон' : 'рядом: ' + cand.length}</em></h4>
      ${b.full ? '<div class="wcb-empty">В бригаде уже 3 человека.</div>' : `
      <label class="wcb-fld"><span>Позывной игрока</span>
        <input data-r2="iName" list="wcb-cand" placeholder="${cand.length ? esc(cand[0].login || cand[0].name) : 'позывной'}"></label>
      <datalist id="wcb-cand">${cand.map(c=>`<option value="${esc(c.login || c.name)}">${esc(c.name)}${c.online?' · в сети':''}</option>`).join('')}</datalist>
      <div class="wcb-row"><button class="wcb-btn go" data-a="invite" type="button" ${B.busy?'disabled':''}>✉ Пригласить</button></div>
      ${cand.length ? `<div class="wcb-note">Рядом: ${cand.map(c=>esc(c.login||c.name)).join(', ')}</div>`
                    : '<div class="wcb-note">На твоей станции нет свободных сталкеров.</div>'}`}
    </div>` : '';
  return `<div class="wcb-card">
    <div class="wcb-name"><b>${esc(b.name)}</b>
      <span class="wcb-badge" style="color:${esc(b.faction_color)}">${esc(b.faction_name)}</span></div>
    ${b.description ? `<p class="wcb-desc">${esc(b.description)}</p>` : ''}
    <div class="wcb-kv"><span>${b.size}/${b.max} человек</span><span>👑 ${esc(b.leader_name)}</span>
      <span>${b.active ? '🚶 Вместе' : '🔀 Расход'}</span></div>
    <div class="wcb-seg">
      <button data-state="active" class="${b.active?'on':''}" type="button" ${b.i_lead&&!B.busy?'':'disabled'}>🚶 Вместе</button>
      <button data-state="no_active" class="${b.active?'':'on'}" type="button" ${b.i_lead&&!B.busy?'':'disabled'}>🔀 Расход</button>
    </div>
    ${b.i_lead ? '<div class="wcb-note" style="margin:-4px 0 10px">Для «Вместе» все участники должны быть на станции лидера.</div>' : ''}
    <h4>Состав</h4>
    <div class="wcb-mem">${b.members.map(m=>memRow(m, b.i_lead)).join('')}</div>
    <div class="wcb-row"><button class="wcb-btn stop" data-a="leave" type="button" ${B.busy?'disabled':''}>
      ${b.i_lead ? '🚪 Покинуть (лидер)' : '🚪 Покинуть'}</button></div>
    ${b.i_lead ? '<div class="wcb-note">Если лидер уходит, бригаду возглавит самый давний участник. Если никого не осталось — бригада распускается.</div>' : ''}
  </div>${inviteBlock}`;
}
function invitesView(){
  const list = (B.data && B.data.invites) || [];
  if (!list.length) return '<div class="wcb-card"><h4>Приглашения</h4><div class="wcb-empty">Входящих приглашений нет. Их присылают лидеры бригад, когда вы на одной станции. Приглашение живёт 60 секунд.</div></div>';
  return `<div class="wcb-card"><h4>Входящие <em>${list.length}</em></h4><div class="wcb-inv">
    ${list.map(i=>`<div class="wcb-inv-row">
      <b>${esc(i.brigade_name)}</b>
      <span>Зовёт ${esc(i.inviter_name)}${i.inviter_login?' · '+esc(i.inviter_login):''} · состав ${i.brigade_size}/3</span>
      <span>Осталось <span class="wcb-timer ${i.expires_in<=15?'low':''}" data-exp="${esc(i.id)}">${i.expires_in} с</span></span>
      <div class="wcb-row">
        <button class="wcb-btn go" data-accept="${esc(i.id)}" type="button" ${B.busy||i.brigade_full?'disabled':''}>✅ Принять</button>
        <button class="wcb-btn" data-decline="${esc(i.id)}" type="button" ${B.busy?'disabled':''}>❌ Отказаться</button>
      </div>${i.brigade_full?'<div class="wcb-note">Бригада уже полная.</div>':''}</div>`).join('')}
  </div></div>`;
}
function allView(){
  const list = (B.data && B.data.brigades) || [];
  if (!list.length) return '<div class="wcb-card"><h4>Все бригады</h4><div class="wcb-empty">Пока ни одной бригады не создано. Создай первую во вкладке «Моя».</div></div>';
  return `<div class="wcb-card"><h4>Все бригады <em>${list.length}</em></h4><div class="wcb-list">
    ${list.map(b=>`<div class="wcb-b-row ${b.mine?'mine':''}">
      <div class="wcb-b-top"><b>${esc(b.name)}</b>
        <span class="wcb-badge" style="color:${esc(b.faction_color)}">${esc(b.faction_name)}</span>
        <em>${b.size}/${b.max} · ${b.active?'🚶':'🔀'}</em></div>
      ${b.description?`<div class="wcb-b-mem" style="margin-bottom:5px">${esc(b.description)}</div>`:''}
      <div class="wcb-b-mem">${b.members.map(m=>`${m.leader?'👑':'👤'} ${esc(m.name)} — 📍${esc(m.location_name)}${m.alive?'':' 💀'}`).join('<br>')}</div>
    </div>`).join('')}
  </div></div>`;
}
function render(){
  TABS.forEach(t => t.classList.toggle('active', t.dataset.tab === B.tab));
  R.err.textContent = B.err;
  R.err.classList.toggle('hidden', !B.err);
  R.content.innerHTML = B.tab === 'mine' ? mineView() : B.tab === 'invites' ? invitesView() : allView();
}

/* ═══════════ СОБЫТИЯ ═══════════ */
HOST.addEventListener('click', async e => {
  const t = e.target;
  const tab = t.closest('.wcb-tab');
  if (tab) { B.tab = tab.dataset.tab; sfx('button.mp3'); render(); if (B.tab==='invites') tickTimer(); return; }
  if (t.closest('[data-r="close"]') || t.classList.contains('wcb-scrim')) { close(); return; }
  const kick = t.closest('[data-kick]');
  if (kick) { await act('/api/brigada/kick', { id: Number(kick.dataset.kick) }, 'Игрок исключён'); return; }
  const acc = t.closest('[data-accept]');
  if (acc) { if (await act('/api/brigada/accept', { id: acc.dataset.accept }, 'Ты в бригаде')) { B.tab='mine'; render(); } return; }
  const dec = t.closest('[data-decline]');
  if (dec) { await act('/api/brigada/decline', { id: dec.dataset.decline }, 'Приглашение отклонено'); return; }
  const st = t.closest('[data-state]');
  if (st) { await act('/api/brigada/state', { state: st.dataset.state }, 'Режим изменён'); return; }
  const a = t.closest('[data-a]');
  if (!a) return;
  const kind = a.dataset.a;
  if (kind === 'create') {
    const n = HOST.querySelector('[data-r2="cName"]'), d = HOST.querySelector('[data-r2="cDesc"]');
    if (await act('/api/brigada/create', { name: n ? n.value : '', description: d ? d.value : '' }, 'Бригада создана')) sfx('ding.mp3');
    return;
  }
  if (kind === 'invite') {
    const n = HOST.querySelector('[data-r2="iName"]');
    const v = n ? n.value.trim() : '';
    if (!v) { B.err='Укажи позывной'; render(); return; }
    if (await act('/api/brigada/invite', { target: v }, 'Приглашение отправлено')) { if (n) n.value=''; render(); }
    return;
  }
  if (kind === 'leave') {
    const b = B.data && B.data.mine;
    const q = b && b.i_lead ? 'Покинуть бригаду? Лидерство перейдёт другому участнику, либо бригада распустится.' : 'Покинуть бригаду?';
    if (!window.confirm(q)) return;
    await act('/api/brigada/leave', {}, 'Готово');
  }
});
TABS.forEach(t => t.setAttribute('aria-selected','false'));

let prevFocus = null;
function open(){
  if (B.open) return;
  B.open = true; prevFocus = document.activeElement;
  HOST.classList.remove('hidden'); HOST.setAttribute('aria-hidden','false');
  refresh();
  window.dispatchEvent(new Event('resize'));
}
function close(){
  if (!B.open) return;
  B.open = false; clearInterval(B.timer);
  HOST.classList.add('hidden'); HOST.setAttribute('aria-hidden','true');
  window.dispatchEvent(new Event('resize'));
  if (prevFocus && prevFocus.focus) try { prevFocus.focus(); } catch(_){}
}
function toggle(){ B.open ? close() : open(); }

const btn = document.getElementById('brigada-btn');
if (btn) btn.onclick = toggle;
document.querySelectorAll('[data-open-brigada]').forEach(b => b.onclick = open);
document.addEventListener('keydown', e => {
  const tag = document.activeElement && document.activeElement.tagName;
  const typing = ['INPUT','TEXTAREA','SELECT'].includes(tag);
  if (e.key === 'Escape' && B.open) { close(); return; }
  if (!B.open && !typing && !e.ctrlKey && !e.metaKey && !e.altKey && ['b','B','и','И'].includes(e.key)) {
    e.preventDefault(); open();
  }
});

WC.on('brigade', d => {
  if (d && d.state) { B.data = d.state; B.err=''; badge(); render(); }
  else if (B.open) refresh(true);
  else api('/api/brigada/state').then(r => { if (r && r.ok && r.d && r.d.ok) { B.data = r.d; badge(); } });
  if (d && d.text) toast(d.text, d.kind === 'invite' ? 'success' : 'info');
  if (d && d.kind === 'invite') { sfx('ding.mp3'); if (!B.open) { B.tab = 'invites'; } }
  if (B.open && B.tab === 'invites') tickTimer();
});
WC.on('world', () => { if (B.open) refresh(true); });
WC.on('ready', () => { refresh(true); });

WC.brigada = { open, close, toggle, refresh };
api('/api/me').then(r => { if (r && r.ok) refresh(true); });
})();