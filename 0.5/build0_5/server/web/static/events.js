/* 44 WHITE CURTAIN — ГЛОБАЛЬНЫЕ ИВЕНТЫ. Панель: активное событие, таймер, зоны, журнал.
   Данные: WS global_event (start/end) + /api/event/state. Сервер — единственный источник правды. */
(() => {
'use strict';
const WC = window.WC; if (!WC) { console.warn('[events] нет шины WC'); return; }
if (window.__WCEVENTS__) return;
window.__WCEVENTS__ = true;

const CSS = `
#wcevt.wce{position:fixed;inset:0;z-index:8550;display:flex;justify-content:flex-end;
 font:14px/1.5 "Segoe UI",Roboto,Inter,system-ui,sans-serif;
 --void:#07090b;--surf:#10151a;--panel:#161d24;--over:#1c252e;--edge:#2b3844;--edge2:#202b36;
 --ink:#ece4d3;--mute:#a8bac6;--dim:#8b9daa;--amber:#ffb02e;--gold:#ffd23f;--rad:#66ff99;
 --rust:#ff6b5c;--steel:#6cb8ff;--track:#0a0e12}
#wcevt.wce.hidden{display:none!important}
#wcevt.wce *{box-sizing:border-box}
#wcevt .wce-scrim{position:absolute;inset:0;background:rgba(5,8,12,.5);backdrop-filter:blur(2px)}
#wcevt .wce-panel{position:relative;width:min(460px,96vw);height:100%;display:flex;flex-direction:column;
 background:linear-gradient(180deg,var(--surf),var(--void));border-left:1px solid var(--edge);
 box-shadow:-30px 0 80px rgba(0,0,0,.6);color:var(--ink)}
#wcevt .wce-head{flex:0 0 auto;display:flex;align-items:center;gap:10px;padding:12px 14px;
 background:linear-gradient(180deg,var(--over),var(--surf));border-bottom:1px solid var(--edge)}
#wcevt .wce-head h3{margin:0;font:800 13px/1.2 ui-monospace,monospace;letter-spacing:2px;color:#fff}
#wcevt .wce-live{display:inline-flex;align-items:center;gap:6px;margin-left:auto;font:700 10px ui-monospace,monospace;
 color:var(--dim);letter-spacing:1px}
#wcevt .wce-live i{width:8px;height:8px;border-radius:50%;background:#4c5a67}
#wcevt .wce-live.on{color:var(--gold)}
#wcevt .wce-live.on i{background:var(--rust);box-shadow:0 0 8px var(--rust);animation:wce-pulse 1.6s infinite}
@keyframes wce-pulse{0%,100%{opacity:1}50%{opacity:.35}}
#wcevt .wce-x{width:32px;height:32px;flex:0 0 auto;border-radius:8px;border:1px solid var(--edge);
 background:var(--panel);color:var(--mute);cursor:pointer;font-size:15px;line-height:1}
#wcevt .wce-x:hover{border-color:var(--rust);color:#fff;background:#5c2620}
#wcevt .wce-body{flex:1 1 auto;overflow-y:auto;padding:13px;display:flex;flex-direction:column;gap:11px}
#wcevt .wce-card{background:var(--panel);border:1px solid var(--edge);border-radius:11px;padding:13px}
#wcevt .wce-card.active{border-color:var(--edge);position:relative;overflow:hidden}
#wcevt .wce-card.active::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;
 background:linear-gradient(90deg,transparent,var(--acc),transparent)}
#wcevt .wce-top{display:flex;align-items:flex-start;gap:10px;margin-bottom:8px}
#wcevt .wce-ico{flex:0 0 auto;width:42px;height:42px;border-radius:10px;display:flex;align-items:center;
 justify-content:center;font-size:22px;background:var(--void);border:1px solid var(--edge)}
#wcevt .wce-title{font:800 14px/1.3 ui-monospace,monospace;color:#fff;word-break:break-word}
#wcevt .wce-kind{display:inline-block;margin-top:4px;padding:2px 8px;border-radius:99px;
 font:700 9.5px ui-monospace,monospace;letter-spacing:1px;border:1px solid currentColor}
#wcevt .wce-kind.buff{color:var(--rad)}
#wcevt .wce-kind.debuff{color:var(--rust)}
#wcevt .wce-kind.neutral{color:var(--amber)}
#wcevt .wce-desc{margin:0 0 10px;font-size:12px;color:#c2cfd8;border-left:2px solid var(--edge);padding-left:9px}
#wcevt .wce-zones{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
#wcevt .wce-zones span{padding:3px 9px;border-radius:99px;border:1px solid var(--edge);background:var(--void);
 font:600 10.5px ui-monospace,monospace;color:var(--mute)}
#wcevt .wce-zones span::before{content:"📍 "}
#wcevt .wce-time{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:5px}
#wcevt .wce-time b{font:800 20px/1 ui-monospace,monospace;color:var(--gold);letter-spacing:1px}
#wcevt .wce-time span{font:600 10px ui-monospace,monospace;color:var(--dim);letter-spacing:1px}
#wcevt .wce-bar{height:8px;border-radius:99px;background:var(--track);border:1px solid var(--edge2);overflow:hidden}
#wcevt .wce-bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--acc),var(--gold));
 transition:width 1s linear}
#wcevt .wce-empty{font-size:12px;color:var(--dim);line-height:1.6}
#wcevt .wce-sec{margin:2px 0 0;font:700 10px ui-monospace,monospace;letter-spacing:1.5px;color:var(--dim);
 text-transform:uppercase;display:flex;align-items:center;gap:7px}
#wcevt .wce-sec em{margin-left:auto;font-style:normal;color:var(--dim)}
#wcevt .wce-hist{display:flex;flex-direction:column;gap:6px}
#wcevt .wce-h-row{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:9px;
 background:var(--void);border:1px solid var(--edge2)}
#wcevt .wce-h-row.live{border-color:var(--amber)}
#wcevt .wce-h-ico{flex:0 0 auto;font-size:16px}
#wcevt .wce-h-main{flex:1 1 auto;min-width:0}
#wcevt .wce-h-main b{display:block;font:600 12px inherit;color:var(--ink);overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
#wcevt .wce-h-main span{display:block;font:500 10px ui-monospace,monospace;color:var(--dim)}
#wcevt .wce-h-state{flex:0 0 auto;font:700 9px ui-monospace,monospace;letter-spacing:1px;
 padding:2px 7px;border-radius:99px;border:1px solid var(--edge);color:var(--dim)}
#wcevt .wce-h-state.live{color:var(--gold);border-color:var(--amber)}
#wcevt .wce-h-state.check{color:var(--steel);border-color:var(--steel)}
#wcevt .wce-note{font-size:10.5px;color:var(--dim);line-height:1.5}
#wcevt .wce-body{scrollbar-width:thin;scrollbar-color:#c97f10 var(--track)}
#wcevt .wce-body::-webkit-scrollbar{width:10px}
#wcevt .wce-body::-webkit-scrollbar-track{background:var(--track);border-left:1px solid var(--edge2)}
#wcevt .wce-body::-webkit-scrollbar-thumb{border:2px solid var(--track);border-radius:6px;
 background:linear-gradient(180deg,var(--amber),#c97f10)}
#events-btn.has-unread{border-color:var(--amber);color:var(--amber)}
#events-timer{background:var(--rust);color:#fff;font-style:normal}
@media(max-width:620px){#wcevt .wce-panel{width:100vw}}
`;
(function(){ let s=document.getElementById('wce-css');
  if(!s){ s=document.createElement('style'); s.id='wce-css'; document.head.appendChild(s); } s.textContent=CSS; })();

const esc = s => String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const sfx = f => { try { WC.sfx && WC.sfx(f); } catch(_){} };
const toast = (t,k) => { try { WC.toast && WC.toast(t,k); } catch(_){} };
const api = p => WC.api(p);

const ICONS = { trade_caravan:'🛒', mutant_activity:'⚠️', frost:'❄️', station_celebration:'🎉',
  radiation_spike:'☢️', grand_sale:'🏪', gas_leak:'☠️', stalker_workshop:'🔧', mutant_breach:'🧟',
  raider_raid:'⚔️', chemical_cloud:'☣️', heating_failure:'🥶' };
const KIND = { buff:'БАФФ', debuff:'ДЕБАФФ', neutral:'СОБЫТИЕ' };
const ACC  = { buff:'#66ff99', debuff:'#ff6b5c', neutral:'#ffb02e' };
const HIST_KEY = 'wc.events.hist';

const E = { open:false, active:null, history:[], timer:0, poll:0 };
try{ E.history = JSON.parse(localStorage.getItem(HIST_KEY) || '[]'); }catch(_){ E.history = []; }
// Всё "живое", пережившее перезагрузку страницы, — НЕДОВЕРЕННОЕ, пока сервер не подтвердит.
// Иначе после рестарта сервера журнал врёт "LIVE".
E.history.forEach(h => { if (!h.ended) h.verified = false; });

let HOST = document.getElementById('wcevt');
if (!HOST) { HOST = document.createElement('div'); HOST.id='wcevt'; document.body.appendChild(HOST); }
HOST.className = 'wce hidden'; HOST.setAttribute('aria-hidden','true');
HOST.innerHTML = `
<div class="wce-scrim"></div>
<div class="wce-panel" role="dialog" aria-modal="true" aria-label="Глобальные ивенты">
 <header class="wce-head">
  <h3>ГЛОБАЛЬНЫЕ ИВЕНТЫ</h3>
  <span class="wce-live" data-r="live"><i></i><span data-r="liveTxt">ЭФИР ТИХ</span></span>
  <button class="wce-x" data-r="close" type="button" aria-label="Закрыть">✕</button>
 </header>
 <div class="wce-body">
  <div data-r="active"></div>
  <h4 class="wce-sec">Журнал событий <em data-r="hCount">0</em></h4>
  <div class="wce-hist" data-r="hist"></div>
  <div class="wce-note">Ивенты запускаются автоматически каждые 45–90 минут, пока в сети есть игроки.
   Команда <b>/event</b> в терминале покажет сводку. Баффы — зелёные, дебаффы — красные.</div>
 </div>
</div>`;
const R = {}; HOST.querySelectorAll('[data-r]').forEach(n => R[n.dataset.r] = n);

const clean = t => String(t||'').replace(/\*\*/g,'').replace(/^[^A-Za-zА-Яа-яЁё0-9]+/,'').trim();
const mmss = s => { s=Math.max(0,Math.round(s)); return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0'); };
const hhmm = ts => new Date(ts*1000).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'});
function saveHist(){ try{ localStorage.setItem(HIST_KEY, JSON.stringify(E.history.slice(0,20))); }catch(_){} }

/* ---------- СВЕРКА С СЕРВЕРОМ (единственный источник правды) ---------- */
function reconcile(act){
  const now = Date.now()/1000;
  E.history.forEach(h => {
    if (h.ended) return;
    if (act && h.id === act.id) { h.verified = true; return; }   // сервер подтвердил — живём
    h.ended = now; h.interrupted = true; h.verified = false;     // сирота после рестарта — прерван
  });
  saveHist();
}
async function load(){
  const r = await api('/api/event/state');
  if (!(r && r.ok && r.d && r.d.ok)) { render(); return; }       // сервер молчит/401 — состояние не трогаем
  const act = r.d.active || null;
  reconcile(act);
  if (act) setActive(act, true);
  else if (E.active) clearActive();
  render();
}
function setActive(d, quiet){
  if (E.active && E.active.id === d.id && E.active.ts === d.ts) { E.active.remaining = d.remaining; render(); return; }
  E.active = { id:d.id, kind:d.kind||'neutral', title:clean(d.title), desc:d.description||'',
    stations:d.station_names||[], duration:d.duration||1, remaining:d.remaining||0, ts:d.ts||Date.now()/1000 };
  let h = E.history.find(x => x.id === d.id && !x.ended);
  if (!h){ h = { id:d.id, kind:E.active.kind, title:E.active.title, started:E.active.ts, ended:null }; E.history.unshift(h); }
  h.verified = true; h.interrupted = false;
  E.history = E.history.slice(0,20); saveHist();
  if (!quiet){ toast(`${ICONS[d.id]||'🌍'} ${E.active.title}`, d.kind==='debuff'?'warn':'success'); sfx('ding.mp3'); }
  render();
}
function clearActive(id){
  if (E.active && id && E.active.id !== id) return;
  const a = E.active; E.active = null;
  if (a){ const h = E.history.find(x => x.id===a.id && !x.ended);
    if (h){ h.ended = Date.now()/1000; h.verified = false; saveHist(); } }
  render();
}

/* ---------- отрисовка ---------- */
function chip(){
  const btn = document.getElementById('events-btn'), badge = document.getElementById('events-timer');
  if (btn) btn.classList.toggle('has-unread', !!E.active);
  if (badge){
    if (E.active){ badge.textContent = mmss(E.active.remaining); badge.classList.remove('hidden'); }
    else badge.classList.add('hidden');
  }
}
function activeCard(){
  const a = E.active;
  if (!a) return `<div class="wce-card"><div class="wce-empty">🌫️ Эфир тих — активных ивентов нет.<br>
    Следующее событие появится здесь автоматически и продублируется в ленту.</div></div>`;
  const acc = ACC[a.kind] || ACC.neutral;
  const pct = Math.min(100, Math.max(0, (1 - a.remaining / a.duration) * 100));
  const zones = a.stations.length
    ? `<div class="wce-zones">${a.stations.map(s=>`<span>${esc(s)}</span>`).join('')}</div>`
    : `<div class="wce-zones"><span>вся линия</span></div>`;
  return `<div class="wce-card active" style="--acc:${acc}">
    <div class="wce-top">
      <div class="wce-ico">${ICONS[a.id]||'🌍'}</div>
      <div><div class="wce-title">${esc(a.title)}</div>
        <span class="wce-kind ${esc(a.kind)}">${KIND[a.kind]||'СОБЫТИЕ'}</span></div>
    </div>
    ${a.desc?`<p class="wce-desc">${esc(a.desc)}</p>`:''}
    ${zones}
    <div class="wce-time"><b data-r="clock">${mmss(a.remaining)}</b><span>ДО ЗАВЕРШЕНИЯ</span></div>
    <div class="wce-bar"><i data-r="bar" style="width:${pct}%"></i></div>
  </div>`;
}
function histRows(){
  if (!E.history.length) return '<div class="wce-empty">Журнал пуст. Он заполнится с первым ивентом.</div>';
  return E.history.map(h => {
    const live = !h.ended;
    const state = live ? (h.verified ? 'LIVE' : 'ПРОВЕРКА') : (h.interrupted ? 'ПРЕРВАН' : 'ЗАВЕРШЁН');
    const cls = live ? (h.verified ? 'live' : 'check') : '';
    const sub = live
      ? (h.verified ? `начался в ${hhmm(h.started)} · идёт сейчас` : `начался в ${hhmm(h.started)} · сверяюсь с сервером…`)
      : `${hhmm(h.started)} – ${hhmm(h.ended)}`;
    return `<div class="wce-h-row ${cls}">
      <span class="wce-h-ico">${ICONS[h.id]||'🌍'}</span>
      <div class="wce-h-main"><b>${esc(h.title)}</b><span>${sub}</span></div>
      <span class="wce-h-state ${cls}">${state}</span>
    </div>`;
  }).join('');
}
function render(){
  R.active.innerHTML = activeCard();
  R.hist.innerHTML = histRows();
  R.hCount.textContent = String(E.history.length);
  R.live.classList.toggle('on', !!E.active);
  R.liveTxt.textContent = E.active ? 'В ЭФИРЕ' : 'ЭФИР ТИХ';
  chip();
}
function tick(){
  if (!E.active) return;
  E.active.remaining = Math.max(0, E.active.remaining - 1);
  const clock = HOST.querySelector('[data-r="clock"]'), bar = HOST.querySelector('[data-r="bar"]');
  if (clock) clock.textContent = mmss(E.active.remaining);
  if (bar) bar.style.width = Math.min(100,(1 - E.active.remaining/E.active.duration)*100) + '%';
  chip();
  if (E.active.remaining <= 0) clearActive();
}

/* ---------- окно ---------- */
let prevFocus = null;
function open(){ if (E.open) return; E.open = true; prevFocus = document.activeElement;
  HOST.classList.remove('hidden'); HOST.setAttribute('aria-hidden','false'); load();
  window.dispatchEvent(new Event('resize')); }
function close(){ if (!E.open) return; E.open = false;
  HOST.classList.add('hidden'); HOST.setAttribute('aria-hidden','true');
  window.dispatchEvent(new Event('resize'));
  if (prevFocus && prevFocus.focus) try{ prevFocus.focus(); }catch(_){} }
function toggle(){ E.open ? close() : open(); }

HOST.addEventListener('click', e => {
  if (e.target.closest('[data-r="close"]') || e.target.classList.contains('wce-scrim')) close();
});
const btn = document.getElementById('events-btn');
if (btn) btn.onclick = toggle;
document.querySelectorAll('[data-open-events]').forEach(b => b.onclick = open);
document.addEventListener('keydown', e => {
  const tag = document.activeElement && document.activeElement.tagName;
  const typing = ['INPUT','TEXTAREA','SELECT'].includes(tag);
  if (e.key === 'Escape' && E.open) { close(); return; }
  if (!E.open && !typing && !e.ctrlKey && !e.metaKey && !e.altKey && ['e','E','у','У'].includes(e.key)) {
    e.preventDefault(); open();
  }
});

/* ---------- шина ---------- */
WC.on('global_event', d => {
  if (!d || !d.id) return;
  if (d.action === 'start' || d.action === 'state') setActive(d, d.action === 'state');
  else if (d.action === 'end'){ clearActive(d.id); toast(`${ICONS[d.id]||'🌍'} Ивент завершён: ${clean(d.title)}`, 'info'); }
});
WC.on('ready', () => load());
WC.on('online', up => { if (up) load(); });

E.timer = setInterval(tick, 1000);
// Перепроверка наличия активного ивента: ловим рестарт сервера, даже если WS-событие не пришло.
E.poll = setInterval(() => { if (E.open || E.active) load(); }, 30000);
WC.events = { open, close, toggle, refresh: load };
render();
load();
})();