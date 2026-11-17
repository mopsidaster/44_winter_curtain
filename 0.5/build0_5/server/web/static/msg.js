/* Мессенджер: контакты, диалоги, почва/почта, онлайн-присутствие. Работает поверх шины WC. */
(() => {
'use strict';
if(!window.WC) return;
const WC = window.WC, $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = WC.esc, md = WC.md;

const M = { data: null, tab: 'chats', peer: null, letters: [], typingTimer: null, lastTyping: 0, open: false };

const time = ts => new Date(ts * 1000).toLocaleString('ru-RU',
  { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

function badge(sel, n){
  const el = $(sel); if(!el) return;
  el.textContent = n; el.classList.toggle('hidden', !n);
}
function badges(){
  const u = (M.data && M.data.unread) || { dm: 0, mail: 0, requests: 0 };
  badge('#tab-dm', u.dm); badge('#tab-mail', u.mail); badge('#tab-req', u.requests);
  const total = u.dm + u.mail + u.requests;
  badge('#msg-count', total);
  $('#msg-btn').classList.toggle('on', total > 0);
}

async function load(){
  const r = await WC.api('/api/msg/overview');
  if(!r.ok) return;
  M.data = r.d;
  $('#directory').innerHTML = (r.d.directory || []).map(d => `<option value="${esc(d.login)}">`).join('');
  badges(); renderList();
}

function renderList(){
  if(!M.data) return;
  const box = $('#msg-list');
  const me = M.data.me.id;
  if(M.tab === 'contacts'){
    const reqs = M.data.requests || [];
    const list = (M.data.contacts || []).filter(c => c.state !== 'in');
    box.innerHTML =
      (reqs.length ? `<div class="msg-sec">Заявки</div>` + reqs.map(r => `
        <div class="msg-row req">
          <b>${esc(r.login)}</b>
          <span class="grow">хочет добавить тебя в контакты</span>
          <button class="btn tiny success" data-act="accept" data-id="${r.id}" type="button">Принять</button>
          <button class="btn tiny secondary" data-act="decline" data-id="${r.id}" type="button">Отклонить</button>
        </div>`).join('') : '') +
      `<div class="msg-sec">Контакты (${list.length})</div>` +
      (list.length ? list.map(c => `
        <div class="msg-row">
          <i class="dot ${c.online ? 'on' : 'off'}"></i>
          <button class="row-main" data-act="chat" data-id="${c.id}" data-login="${esc(c.login)}" type="button">
            <b>${esc(c.alias || c.login)}</b>
            <span>${esc(c.online ? (c.location || 'в сети') : 'не в сети')}</span>
          </button>
          ${c.state === 'blocked' ? '<span class="tag bad">блок</span>' : ''}
          <button class="btn tiny secondary" data-act="remove" data-id="${c.id}" type="button">✕</button>
        </div>`).join('') : '<div class="empty">Контактов пока нет. Добавь игрока по позывному внизу.</div>');
    return;
  }
  if(M.tab === 'mail'){
    box.innerHTML = M.letters.length ? M.letters.map(l => `
      <div class="msg-row mail ${l.read ? '' : 'unread'}" data-act="letter" data-id="${l.id}">
        <div class="mail-head"><b>${esc(l.subject || 'Без темы')}</b><time>${time(l.ts)}</time></div>
        <div class="mail-from">от ${esc(l.sender_login)}</div>
        <div class="mail-body">${md(l.body)}</div>
      </div>`).join('') : '<div class="empty">Почта пуста. Системные уведомления тоже приходят сюда.</div>';
    return;
  }
  const chats = (M.data.contacts || []).filter(c => c.state === 'ok' && c.last);
  box.innerHTML = chats.length ? chats.map(c => `
    <button class="msg-row chat ${c.unread ? 'unread' : ''}" data-act="chat" data-id="${c.id}" data-login="${esc(c.login)}" type="button">
      <i class="dot ${c.online ? 'on' : 'off'}"></i>
      <div class="grow">
        <div class="chat-top"><b>${esc(c.alias || c.login)}</b><time>${c.last ? time(c.last.ts) : ''}</time></div>
        <div class="chat-last">${esc((c.last && c.last.body || '').slice(0, 90))}</div>
      </div>
      ${c.unread ? `<em class="badge inline">${c.unread}</em>` : ''}
    </button>`).join('') : '<div class="empty">Диалогов нет. Открой контакт и напиши первым.</div>';
}

async function openThread(id, login){
  M.peer = { id, login };
  const r = await WC.api('/api/msg/thread?peer=' + id);
  if(!r.ok){ WC.toast('Не удалось открыть диалог', 'error'); return; }
  $('#thread-name').textContent = login || r.d.peer.login;
  const c = (M.data?.contacts || []).find(x => x.id === id);
  $('#thread-state').textContent = c ? (c.online ? (c.location || 'в сети') : 'не в сети') : '—';
  $('#thread-body').innerHTML = r.d.messages.map(m => bubble(m)).join('') ||
    '<div class="empty">Сообщений нет. Начни разговор.</div>';
  $('#msg-list').classList.add('hidden');
  $('#msg-thread').classList.remove('hidden');
  $('#msg-compose').classList.add('hidden');
  scrollThread();
  await load();
}
function bubble(m){
  const mine = M.data && m.sender === M.data.me.id;
  return `<div class="bubble ${mine ? 'mine' : ''} ${m.kind === 'system' ? 'sys' : ''}">
    ${mine ? '' : `<div class="b-from">${esc(m.sender_login)}</div>`}
    <div class="b-body">${md(m.body)}</div>
    <time>${time(m.ts)}</time></div>`;
}
function scrollThread(){ const b = $('#thread-body'); b.scrollTop = b.scrollHeight; }
function closeThread(){
  M.peer = null;
  $('#msg-thread').classList.add('hidden');
  $('#msg-list').classList.remove('hidden');
}

function openDrawer(){ M.open = true; $('#msg').classList.remove('hidden'); load(); if(M.tab === 'mail') loadMail(); }
function closeDrawer(){ M.open = false; $('#msg').classList.add('hidden'); }
WC.on('toggle-msg', () => M.open ? closeDrawer() : openDrawer());
WC.on('close-msg', closeDrawer);
WC.on('open-chat', ({ id, login }) => { openDrawer(); openThread(id, login); });
WC.on('ready', () => { load(); });
WC.on('online', ok => { if(ok) load(); });
WC.on('contacts', () => load());
WC.on('world', w => {
  if(M.data){ M.data.unread = w.unread; badges(); }
  if(M.peer){
    const p = (w.online || []).find(x => x.id === M.peer.id);
    $('#thread-state').textContent = p ? (p.location || 'в сети') : 'не в сети';
  }
});
WC.on('msg', ({ message }) => {
  if(M.peer && message.sender === M.peer.id){
    $('#thread-body').insertAdjacentHTML('beforeend', bubble(message));
    scrollThread(); WC.api('/api/msg/read', { peer: message.sender });
  } else {
    WC.toast(`✉ ${message.sender_login}: ${message.body.slice(0, 80)}`, 'info');
  }
  WC.sfx('ding.mp3'); load();
});
WC.on('msg_echo', ({ message }) => {
  if(M.peer && message.recipient === M.peer.id){
    $('#thread-body').insertAdjacentHTML('beforeend', bubble(message)); scrollThread();
  }
  load();
});
WC.on('typing', d => {
  if(M.peer && d.from === M.peer.id){
    $('#thread-typing').classList.remove('hidden');
    clearTimeout(M.typingTimer);
    M.typingTimer = setTimeout(() => $('#thread-typing').classList.add('hidden'), 2500);
  }
});

$('#msg-btn').onclick = () => M.open ? closeDrawer() : openDrawer();
$('#msg-x').onclick = closeDrawer;
$('#msg-refresh').onclick = () => { load(); if(M.tab === 'mail') loadMail(); };
$('#thread-back').onclick = closeThread;
$$('.mtab').forEach(b => b.onclick = async () => {
  M.tab = b.dataset.tab;
  $$('.mtab').forEach(x => x.classList.toggle('active', x === b));
  closeThread(); $('#msg-compose').classList.add('hidden');
  if(M.tab === 'mail') await loadMail(); else renderList();
});
async function loadMail(){
  const r = await WC.api('/api/msg/mail');
  if(r.ok){ M.letters = r.d.letters || []; renderList(); }
}

$('#msg-list').addEventListener('click', async e => {
  const el = e.target.closest('[data-act]'); if(!el) return;
  const act = el.dataset.act, id = +el.dataset.id;
  if(act === 'chat'){ openThread(id, el.dataset.login); return; }
  if(act === 'letter'){
    const l = M.letters.find(x => x.id === id); if(!l) return;
    if(!l.read){ await WC.api('/api/msg/read', { ids: [id] }); l.read = 1; renderList(); load(); }
    WC.toast(`**${l.subject || 'Письмо'}**\n${l.body}`, 'info');
    return;
  }
  const map = { accept: '/api/contacts/accept', decline: '/api/contacts/decline',
                remove: '/api/contacts/decline', block: '/api/contacts/block' };
  if(map[act]){
    const r = await WC.api(map[act], { id });
    if(r.ok){ WC.sfx('button.mp3'); await load(); if(M.peer && M.peer.id === id) closeThread(); }
    else WC.toast(r.d.error || 'Не получилось', 'warn');
  }
});
$('#thread-block').onclick = async () => {
  if(!M.peer) return;
  await WC.api('/api/contacts/block', { id: M.peer.id });
  WC.toast('Контакт заблокирован', 'warn'); closeThread(); load();
};
$('#thread-form').addEventListener('submit', async e => {
  e.preventDefault();
  const inp = $('#thread-input'), body = inp.value.trim();
  if(!body || !M.peer) return;
  const r = await WC.api('/api/msg/send', { to: M.peer.id, body, kind: 'dm' });
  if(r.ok){
    inp.value = ''; WC.sfx('button.mp3');
    $('#thread-body').insertAdjacentHTML('beforeend', bubble(r.d.message)); scrollThread(); load();
  } else WC.toast(r.d.error || 'Сообщение не отправлено', 'warn');
});
$('#thread-input').addEventListener('keydown', e => {
  if(e.key === 'Enter' && (e.ctrlKey || e.metaKey)){ e.preventDefault(); $('#thread-form').requestSubmit(); }
});
$('#thread-input').addEventListener('input', () => {
  if(!M.peer) return;
  const now = Date.now();
  if(now - M.lastTyping > 1800){ M.lastTyping = now; WC.send({ type: 'typing', to: M.peer.id }); }
});
$('#add-contact').addEventListener('submit', async e => {
  e.preventDefault();
  const login = $('#contact-login').value.trim(); if(!login) return;
  const r = await WC.api('/api/contacts/request', { login });
  if(r.ok){
    $('#contact-login').value = ''; WC.sfx('ding.mp3');
    WC.toast(r.d.accepted ? 'Контакт добавлен взаимно' : 'Заявка отправлена', 'success');
    M.tab = 'contacts'; $$('.mtab').forEach(x => x.classList.toggle('active', x.dataset.tab === 'contacts'));
    await load();
  } else WC.toast(r.d.error || 'Не удалось добавить', 'warn');
});
$('#new-mail').onclick = () => { $('#msg-compose').classList.toggle('hidden'); $('#mail-to').focus(); };
$('#mail-cancel').onclick = () => $('#msg-compose').classList.add('hidden');
$('#mail-form').addEventListener('submit', async e => {
  e.preventDefault();
  const r = await WC.api('/api/msg/send', {
    to: $('#mail-to').value.trim(), subject: $('#mail-subject').value.trim() || 'Депеша',
    body: $('#mail-body').value.trim(), kind: 'mail' });
  if(r.ok){
    $('#mail-body').value = ''; $('#mail-subject').value = '';
    $('#msg-compose').classList.add('hidden');
    WC.toast('Письмо отправлено', 'success'); WC.sfx('ding.mp3');
    M.tab = 'mail'; $$('.mtab').forEach(x => x.classList.toggle('active', x.dataset.tab === 'mail'));
    await loadMail();
  } else WC.toast(r.d.error || 'Письмо не отправлено', 'warn');
});
})();