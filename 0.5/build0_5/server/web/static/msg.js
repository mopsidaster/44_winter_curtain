/* 44 WHITE CURTAIN — связь: контакты, личные сообщения, архив.
   Дедуп двухуровневый: по id в памяти (Map) и по data-mid в DOM.
   Отправка писем удалена; архив только для чтения. */
(() => {
'use strict';
const WC = window.WC; if (!WC) { console.warn('[msg] нет шины WC'); return; }
if (window.__WCMSG__) return;
window.__WCMSG__ = true;

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const sfx = f => { try { WC.sfx && WC.sfx(f); } catch(_){} };
const toast = (t,k) => { try { WC.toast && WC.toast(t,k); } catch(_){} };
const api = (p,b,m) => WC.api(p,b,m);
const time = ts => { if(!ts) return '';
  const d=new Date(ts*1000), n=new Date();
  return d.toDateString()===n.toDateString()
    ? d.toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})
    : d.toLocaleDateString('ru-RU',{day:'2-digit',month:'2-digit'}); };
const full = ts => ts ? new Date(ts*1000).toLocaleString('ru-RU') : '';

const M = {
  open:false, tab:'chats', me:null, peer:null, peerName:'',
  chats:[], requests:[], letters:[], directory:[],
  threads:new Map(), unread:{dm:0,mail:0,requests:0},
  online:new Map(), letter:null, loading:false, typingTs:0, typingTimer:0
};

const el = {
  drawer:$('#msg'), list:$('#msg-list'), thread:$('#msg-thread'), body:$('#thread-body'),
  name:$('#thread-name'), state:$('#thread-state'), back:$('#thread-back'), block:$('#thread-block'),
  form:$('#thread-form'), input:$('#thread-input'), typing:$('#thread-typing'),
  count:$('#msg-count'), btn:$('#msg-btn'), close:$('#msg-x'), refresh:$('#msg-refresh'),
  addForm:$('#add-contact'), login:$('#contact-login'), dir:$('#directory'),
  tabs:[...document.querySelectorAll('.mtab')],
  bDm:$('#tab-dm'), bReq:$('#tab-req'), bMail:$('#tab-mail')
};
if (!el.drawer || !el.list || !el.body) { console.warn('[msg] разметка мессенджера не найдена'); return; }

/* ═══════════ ХРАНИЛИЩЕ: идемпотентно по id ═══════════ */
function bucket(peer){
  let b = M.threads.get(peer);
  if (!b) { b = new Map(); M.threads.set(peer, b); }
  return b;
}
function put(peer, m){
  if (!m || m.id == null || !peer) return false;
  const b = bucket(peer);
  if (b.has(m.id)) return false;
  b.set(m.id, m);
  return true;
}
function putMany(peer, arr){ let n=0; for (const m of (arr||[])) if (put(peer,m)) n++; return n; }
function messages(peer){
  const b = M.threads.get(peer);
  return b ? [...b.values()].sort((a,c)=>(a.ts-c.ts)||(a.id-c.id)) : [];
}
function touchChat(peer, m){
  const c = M.chats.find(x => x.id === peer);
  if (!c) return;
  if (!c.last || (m.ts >= c.last.ts && m.id > (c.last.id||0)))
    c.last = { body:m.body, ts:m.ts, kind:m.kind, sender:m.sender, id:m.id };
}
function bumpUnread(peer, m){
  if (M.me && m.sender === M.me.id) return;
  if (M.open && M.tab === 'chats' && M.peer === peer) return;
  const c = M.chats.find(x => x.id === peer);
  if (c) c.unread = (c.unread||0) + 1;
  M.unread.dm = (M.unread.dm||0) + 1;
  badges();
}

/* ═══════════ БЕЙДЖИ ═══════════ */
function badges(){
  const dm=M.unread.dm||0, rq=M.unread.requests||0, ml=M.unread.mail||0;
  const set=(node,n)=>{ if(!node)return; node.textContent=String(n); node.classList.toggle('hidden',!n); };
  set(el.bDm,dm); set(el.bReq,rq); set(el.bMail,ml);
  const total=dm+rq+ml;
  if (el.count){ el.count.textContent=String(total); el.count.classList.toggle('hidden',!total); }
  if (el.btn) el.btn.classList.toggle('has-unread',!!total);
}

/* ═══════════ ЗАГРУЗКА ═══════════ */
async function overview(){
  if (M.loading) return;
  M.loading = true;
  const r = await api('/api/msg/overview');
  M.loading = false;
  if (!r || !r.ok || !r.d) { renderList(); return; }
  const d = r.d;
  M.me = d.me || M.me;
  M.chats = Array.isArray(d.contacts) ? d.contacts : [];
  M.requests = Array.isArray(d.requests) ? d.requests : [];
  M.directory = Array.isArray(d.directory) ? d.directory : [];
  M.unread = d.unread || M.unread;
  if (el.dir) el.dir.innerHTML = M.directory.map(x=>`<option value="${esc(x.login)}">`).join('');
  badges(); renderList();
  if (M.peer) paintHead();
}
async function openThread(peer){
  peer = Number(peer)||0;
  if (!peer) return;
  M.peer = peer; M.letter = null;
  const c = M.chats.find(x => x.id === peer);
  M.peerName = c ? (c.alias||c.login) : String(peer);
  el.thread.classList.remove('hidden');
  el.form.classList.remove('hidden');
  paintHead();
  el.body.innerHTML = '<div class="msg-empty">Загружаю переписку…</div>';
  const r = await api('/api/msg/thread?peer=' + peer);
  if (M.peer !== peer) return;                 // успели переключиться — не рисуем чужое
  if (r && r.ok && r.d) {
    putMany(peer, r.d.messages);
    if (r.d.peer && r.d.peer.login && !c) M.peerName = r.d.peer.login;
    if (c) c.unread = 0;
  }
  renderThread();                              // полная перерисовка из Map — дублей нет
  api('/api/msg/read', { peer }).then(()=>overview());
  try { el.input.focus(); } catch(_){}
}
function closeThread(){
  M.peer = null; M.letter = null;
  el.thread.classList.add('hidden');
  el.typing.classList.add('hidden');
  renderList();
}
async function openArchive(){
  const r = await api('/api/msg/mail');
  M.letters = (r && r.ok && r.d && Array.isArray(r.d.letters)) ? r.d.letters : [];
  renderList();
}
function openLetter(id){
  const l = M.letters.find(x => x.id === id);
  if (!l) return;
  M.letter = l; M.peer = null;
  el.thread.classList.remove('hidden');
  el.name.textContent = l.subject || 'Без темы';
  el.state.textContent = 'архив';
  el.block.classList.add('hidden');
  el.form.classList.add('hidden');
  el.typing.classList.add('hidden');
  el.body.innerHTML = `<div class="msg-letter">
     <div class="msg-letter-head"><b>${esc(l.subject||'Без темы')}</b><time>${esc(full(l.ts))}</time></div>
     <div class="msg-letter-from">от ${esc(l.sender_login||'система')}</div>
     <div class="msg-letter-body">${esc(l.body)}</div>
     <div class="msg-letter-note">Архив только для чтения. Отправка писем отключена — пиши в личные сообщения.</div>
   </div>`;
  if (!l.read){ l.read=1; api('/api/msg/read',{ids:[l.id]}).then(()=>overview()); }
  renderList();
}

/* ═══════════ ОТРИСОВКА ═══════════ */
function paintHead(){
  const c = M.chats.find(x => x.id === M.peer);
  el.name.textContent = c ? (c.alias||c.login) : (M.peerName||String(M.peer));
  const on = M.online.get(M.peer);
  el.state.textContent = c && c.state === 'blocked' ? 'заблокирован' : (on ? (on.location||'в сети') : 'не в сети');
  el.block.classList.remove('hidden');
  el.block.textContent = c && c.state === 'blocked' ? 'Разблок' : 'Блок';
  el.form.classList.toggle('hidden', !!(c && c.state === 'blocked'));
}
function bubble(m){
  const mine = M.me && m.sender === M.me.id;
  const sys = m.kind === 'system' || !m.sender;
  const mid = esc(m.id);
  if (sys) return `<div class="bub sys" data-mid="${mid}"><div class="b-text">${esc(m.body)}</div><time>${esc(time(m.ts))}</time></div>`;
  return `<div class="bub ${mine?'mine':'theirs'}" data-mid="${mid}">
    ${mine?'':`<div class="b-from">${esc(m.sender_login||'')}</div>`}
    <div class="b-text">${esc(m.body)}</div><time>${esc(time(m.ts))}</time></div>`;
}
function renderThread(){
  if (!M.peer || M.letter) return;
  const list = messages(M.peer);
  el.body.innerHTML = list.length ? list.map(bubble).join('')
    : '<div class="msg-empty">Сообщений пока нет. Напиши первым.</div>';
  el.body.scrollTop = el.body.scrollHeight;
  paintHead();
}
function appendBubble(m){
  if (!M.peer || M.letter || !m || m.id == null) return;
  // DOM-дедуп: пузырь с этим id уже на экране — второй раз не рисуем
  if (el.body.querySelector('[data-mid="'+CSS.escape(String(m.id))+'"]')) return;
  const near = el.body.scrollHeight - el.body.scrollTop - el.body.clientHeight < 140;
  const wrap = document.createElement('div');
  wrap.innerHTML = bubble(m);
  const node = wrap.firstElementChild;
  if (node) el.body.appendChild(node);
  if (near) el.body.scrollTop = el.body.scrollHeight;
}
function renderList(){
  if (M.tab === 'chats') {
    const rows = M.chats.filter(c => c.state !== 'in');
    if (!rows.length){ el.list.innerHTML='<div class="msg-empty">Диалогов нет. Добавь контакт внизу.</div>'; return; }
    rows.sort((a,b)=>((b.last&&b.last.ts)||0)-((a.last&&a.last.ts)||0));
    el.list.innerHTML = rows.map(c=>{
      const on=M.online.get(c.id);
      const sub=c.state==='blocked'?'заблокирован':(on?(on.location||'в сети'):'не в сети');
      return `<button class="msg-row chat ${c.unread?'unread':''} ${M.peer===c.id?'active':''}"
        data-act="chat" data-id="${c.id}" data-login="${esc(c.login)}" type="button">
        <div class="chat-top"><b>${esc(c.alias||c.login)}</b><time>${esc(c.last?time(c.last.ts):'')}</time></div>
        <div class="chat-last">${esc(((c.last&&c.last.body)||sub).slice(0,90))}</div>
        ${c.unread?`<em class="badge inline">${c.unread}</em>`:''}</button>`;
    }).join('');
    return;
  }
  if (M.tab === 'contacts') {
    const req=M.requests.map(r=>`<div class="msg-row req"><b>${esc(r.login)}</b><span>заявка в контакты</span>
      <div class="row-btns">
        <button class="btn tiny success" data-act="accept" data-id="${r.id}" type="button">Принять</button>
        <button class="btn tiny secondary" data-act="decline" data-id="${r.id}" type="button">Отклонить</button>
      </div></div>`).join('');
    const ok=M.chats.filter(c=>c.state==='ok').map(c=>`<div class="msg-row contact">
      <button class="row-main" data-act="chat" data-id="${c.id}" data-login="${esc(c.login)}" type="button">
        <b>${esc(c.alias||c.login)}</b><span>${esc(M.online.has(c.id)?'в сети':'не в сети')}</span></button>
      <div class="row-btns">
        <button class="btn tiny secondary" data-act="rename" data-id="${c.id}" data-login="${esc(c.alias||c.login)}" type="button">Имя</button>
        <button class="btn tiny secondary" data-act="remove" data-id="${c.id}" type="button">Убрать</button>
        <button class="btn tiny danger" data-act="block" data-id="${c.id}" type="button">Блок</button>
      </div></div>`).join('');
    const out=M.chats.filter(c=>c.state==='out').map(c=>`<div class="msg-row contact"><b>${esc(c.login)}</b><span>заявка отправлена</span>
      <div class="row-btns"><button class="btn tiny secondary" data-act="decline" data-id="${c.id}" type="button">Отменить</button></div></div>`).join('');
    const blocked=M.chats.filter(c=>c.state==='blocked').map(c=>`<div class="msg-row contact blocked"><b>${esc(c.alias||c.login)}</b><span>заблокирован</span>
      <div class="row-btns"><button class="btn tiny secondary" data-act="remove" data-id="${c.id}" type="button">Снять</button></div></div>`).join('');
    el.list.innerHTML = (req+ok+out+blocked) || '<div class="msg-empty">Контактов нет. Добавь игрока внизу.</div>';
    return;
  }
  if (!M.letters.length){ el.list.innerHTML='<div class="msg-empty">Архив пуст. Отправка писем отключена.</div>'; return; }
  el.list.innerHTML = M.letters.map(l=>`<button class="msg-row mail ${l.read?'':'unread'} ${M.letter&&M.letter.id===l.id?'active':''}"
      data-act="letter" data-id="${l.id}" type="button">
      <div class="mail-head"><b>${esc(l.subject||'Без темы')}</b><time>${esc(time(l.ts))}</time></div>
      <div class="mail-from">от ${esc(l.sender_login||'система')}</div>
      <div class="chat-last">${esc(String(l.body||'').slice(0,90))}</div></button>`).join('');
}
function setTab(tab){
  M.tab = tab;
  el.tabs.forEach(b=>b.classList.toggle('active', b.dataset.tab===tab));
  if (tab !== 'chats') closeThread();
  if (tab === 'mail'){ M.letter=null; el.thread.classList.add('hidden'); openArchive(); }
  else renderList();
}

/* ═══════════ ДЕЙСТВИЯ ═══════════ */
async function sendDm(){
  const body = (el.input.value||'').trim();
  if (!body || !M.peer) return;
  const c = M.chats.find(x => x.id === M.peer);
  if (c && c.state === 'blocked'){ toast('Контакт заблокирован','warn'); return; }
  const peer = M.peer;
  el.input.value = '';
  const r = await api('/api/msg/send', { to: peer, body, kind:'dm' });
  if (!r || !r.ok || !r.d || !r.d.ok){
    if (M.peer === peer) el.input.value = body;
    toast((r&&r.d&&r.d.error)||'Не удалось отправить','error');
    return;
  }
  const m = r.d.message;
  // одна вставка: put вернёт false, если эхо уже успело положить это id
  if (put(peer, m) && M.peer === peer && !M.letter) appendBubble(m);
  touchChat(peer, m); renderList();
  sfx('button.mp3');
}
async function contactAction(act, id, login){
  id = Number(id)||0;
  if (!id) return;
  if (act === 'chat'){ setTab('chats'); openThread(id); return; }
  if (act === 'letter'){ openLetter(id); return; }
  if (act === 'rename'){
    const alias = window.prompt('Имя контакта (пусто — сбросить)', login||'');
    if (alias === null) return;
    const r = await api('/api/contacts/rename', { id, alias });
    if (!r||!r.ok){ toast((r&&r.d&&r.d.error)||'Не удалось переименовать','error'); return; }
    toast('Имя обновлено','success'); overview(); return;
  }
  const map={ accept:'/api/contacts/accept', decline:'/api/contacts/decline', remove:'/api/contacts/decline', block:'/api/contacts/block' };
  const url=map[act]; if (!url) return;
  const r = await api(url, { id });
  if (!r||!r.ok){ toast((r&&r.d&&r.d.error)||'Действие не выполнено','error'); return; }
  sfx('button.mp3');
  if (act === 'block' && M.peer === id) closeThread();
  overview();
}
async function toggleBlock(){
  if (!M.peer) return;
  const c = M.chats.find(x => x.id === M.peer);
  const blocked = c && c.state === 'blocked';
  const r = await api(blocked?'/api/contacts/decline':'/api/contacts/block', { id: M.peer });
  if (!r||!r.ok){ toast((r&&r.d&&r.d.error)||'Не удалось','error'); return; }
  toast(blocked?'Блокировка снята':'Контакт заблокирован','success');
  closeThread(); overview();
}

/* ═══════════ ОКНО ═══════════ */
function open(){
  if (M.open) return;
  M.open = true;
  el.drawer.classList.remove('hidden');
  overview();
  if (M.tab === 'mail') openArchive();
  window.dispatchEvent(new Event('resize'));
  setTimeout(()=>{ try{ (M.peer?el.input:el.login).focus(); }catch(_){} }, 120);
}
function close(){
  if (!M.open) return;
  M.open = false;
  el.drawer.classList.add('hidden');
  el.typing.classList.add('hidden');
  window.dispatchEvent(new Event('resize'));
}
function toggle(){ M.open ? close() : open(); }

/* ═══════════ СОБЫТИЯ ═══════════ */
if (el.btn) el.btn.onclick = toggle;
if (el.close) el.close.onclick = close;
if (el.refresh) el.refresh.onclick = () => { sfx('button.mp3'); overview(); if (M.tab==='mail') openArchive(); };
if (el.back) el.back.onclick = () => { closeThread(); if (M.tab==='mail') openArchive(); };
if (el.block) el.block.onclick = toggleBlock;
el.tabs.forEach(b => b.onclick = () => { sfx('button.mp3'); setTab(b.dataset.tab); });
el.list.addEventListener('click', e => {
  const t = e.target.closest('[data-act]');
  if (t) contactAction(t.dataset.act, t.dataset.id, t.dataset.login);
});
if (el.form) el.form.addEventListener('submit', e => { e.preventDefault(); sendDm(); });
if (el.input){
  el.input.addEventListener('keydown', e => { if (e.key==='Enter'&&(e.ctrlKey||e.metaKey)){ e.preventDefault(); sendDm(); } });
  el.input.addEventListener('input', () => {
    if (!M.peer) return;
    const now=Date.now();
    if (now - M.typingTs < 1800) return;
    M.typingTs = now;
    try { WC.send({ type:'typing', to: M.peer }); } catch(_){}
  });
}
if (el.addForm) el.addForm.addEventListener('submit', async e => {
  e.preventDefault();
  const login=(el.login.value||'').trim();
  if (!login) return;
  const r = await api('/api/contacts/request', { login });
  if (!r||!r.ok||!r.d||!r.d.ok){ toast((r&&r.d&&r.d.error)||'Заявка не отправлена','error'); return; }
  el.login.value='';
  toast(r.d.accepted?'Теперь вы в контактах':'Заявка отправлена','success');
  sfx('ding.mp3'); setTab('contacts'); overview();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && M.open){
    if (M.peer || M.letter){ closeThread(); if (M.tab==='mail') openArchive(); return; }
    close();
  }
});

/* ═══════════ ШИНА ═══════════ */
function incoming(m, echo){
  if (!m || m.id == null) return;
  const mine = M.me && m.sender === M.me.id;
  const peer = echo ? m.recipient : (mine ? m.recipient : m.sender);
  if (!peer) return;
  if (!put(peer, m)) return;                   // id уже есть (ответ на отправку / эхо / повтор) — выходим
  touchChat(peer, m);
  if (M.open && M.tab === 'chats' && M.peer === peer){
    appendBubble(m);                           // + DOM-дедуп внутри
    if (!mine) api('/api/msg/read', { peer });
  } else if (!mine){
    bumpUnread(peer, m);
  }
  if (!M.chats.some(c => c.id === peer)) overview(); else renderList();
  if (!mine && M.open && M.peer === peer) sfx('ding.mp3');
}
WC.on('msg', d => incoming(d && d.message ? d.message : d, false));
WC.on('msg_echo', d => incoming(d && d.message ? d.message : d, true));
WC.on('contacts', () => {
  if (M.open) overview();
  else api('/api/msg/overview').then(r => { if (r&&r.ok&&r.d&&r.d.unread){ M.unread=r.d.unread; badges(); } });
});
WC.on('typing', d => {
  if (!d || !M.open || M.peer !== d.from) return;
  el.typing.textContent = (d.login||'собеседник') + ' печатает…';
  el.typing.classList.remove('hidden');
  clearTimeout(M.typingTimer);
  M.typingTimer = setTimeout(()=>el.typing.classList.add('hidden'), 2600);
});
WC.on('world', w => {
  if (!w) return;
  M.online = new Map((w.online||[]).map(p => [p.id, p]));
  if (w.me) M.me = { id: w.me.id, login: w.me.login || w.me.name };
  if (w.unread){ M.unread = w.unread; badges(); }
  if (M.open){ renderList(); if (M.peer) paintHead(); }
});
WC.on('toggle-msg', toggle);
WC.on('ready', () => overview());
WC.on('online', up => { if (!up) el.typing.classList.add('hidden'); });

WC.msg = { open, close, toggle, thread: openThread, refresh: overview };
badges();
api('/api/me').then(r => { if (r && r.ok) overview(); });
})();