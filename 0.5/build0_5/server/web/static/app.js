/* 44 WHITE CURTAIN — ядро терминала. Шина WC доступна модулю мессенджера. */
(() => {
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const LS = 'wc.ui.v2';

const S = {
  ws: null, screens: new Map(), order: [], commands: [], user: null, world: null, lan: null,
  modal: null, submitting: false, errors: [], history: [], hIdx: -1,
  acItems: [], acIdx: -1, retry: 800, timer: null, alive: false,
  cfg: { font: 15, density: 'normal', scan: true, grain: true, motion: true, amb: true, sfx: true, autoref: true }
};
const bus = {};
const WC = {
  state: S,
  on(type, fn){ (bus[type] = bus[type] || []).push(fn); },
  fire(type, data){ (bus[type] || []).forEach(f => { try{ f(data); }catch(e){ console.error(e); } }); },
  send, toast, sfx, api, esc, md, hhmm, copy,
  openUrl(url){ window.open(url, '_blank', 'noopener'); }
};
window.WC = WC;

/* ---------- настройки ---------- */
function loadCfg(){ try{ Object.assign(S.cfg, JSON.parse(localStorage.getItem(LS) || '{}')); }catch(e){} }
function saveCfg(){ try{ localStorage.setItem(LS, JSON.stringify(S.cfg)); }catch(e){} }
function applyCfg(){
  const c = S.cfg;
  document.documentElement.style.setProperty('--fs', c.font + 'px');
  document.body.dataset.density = c.density;
  document.body.classList.toggle('no-scan', !c.scan);
  document.body.classList.toggle('no-grain', !c.grain);
  document.body.classList.toggle('no-motion', !c.motion);
  $('#set-font').value = c.font; $('#set-font-v').textContent = c.font;
  $('#set-density').value = c.density;
  ['scan','grain','motion','amb','sfx','autoref'].forEach(k => { $('#set-' + k).checked = !!c[k]; });
  const on = c.sfx || c.amb;
  const b = $('#sound'); b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on));
  b.firstChild.nodeValue = on ? '🔊' : '🔇';
  b.title = on ? 'Звук включён' : 'Звук выключен';
  ambience(on && c.amb);
}

/* ---------- звук ---------- */
const pool = {};
function sfx(name){
  if(!S.cfg.sfx) return;
  try{
    const a = pool[name] || (pool[name] = new Audio('/sounds/' + name));
    a.currentTime = 0; a.volume = .5; a.play().catch(()=>{});
  }catch(e){}
}
let AC = null, ambGain = null, ambStarted = false;
function ambience(on){
  if(!on){ if(ambGain && AC) ambGain.gain.setTargetAtTime(0, AC.currentTime, .4); return; }
  try{
    if(!AC) AC = new (window.AudioContext || window.webkitAudioContext)();
    if(AC.state === 'suspended') AC.resume().catch(()=>{});
    if(!ambStarted){
      const len = AC.sampleRate * 4, buf = AC.createBuffer(1, len, AC.sampleRate), d = buf.getChannelData(0);
      let last = 0;
      for(let i = 0; i < len; i++){ const w = Math.random() * 2 - 1; last = (last + .02 * w) / 1.02; d[i] = last * 3.2; }
      const src = AC.createBufferSource(); src.buffer = buf; src.loop = true;
      const lp = AC.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 220;
      const lfo = AC.createOscillator(), lfoG = AC.createGain();
      lfo.frequency.value = .07; lfoG.gain.value = 60; lfo.connect(lfoG).connect(lp.frequency); lfo.start();
      ambGain = AC.createGain(); ambGain.gain.value = 0;
      src.connect(lp).connect(ambGain).connect(AC.destination); src.start();
      ambStarted = true;
    }
    ambGain.gain.setTargetAtTime(.05, AC.currentTime, 1.2);
  }catch(e){}
}

/* ---------- утилиты ---------- */
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function md(t){
  if(!t) return '';
  let s = esc(t);
  s = s.replace(/```([\s\S]*?)```/g, (_, x) => '<pre>' + x.replace(/^\n/, '') + '</pre>');
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  s = s.replace(/&lt;(a?):([\w~]{2,32}):(\d{5,25})&gt;/g, (_, a, n, id) =>
    `<img class="emoji custom" src="https://cdn.discordapp.com/emojis/${id}.${a ? 'gif' : 'png'}?size=48" alt="${n}" data-fallback="◈" loading="lazy">`);
  s = s.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  s = s.replace(/__([^_]+)__/g, '<u>$1</u>');
  s = s.replace(/~~([^~]+)~~/g, '<s>$1</s>');
  s = s.replace(/^\s*&gt;\s?(.+)$/gm, '<blockquote>$1</blockquote>');
  return s.replace(/\n/g, '<br>');
}

document.addEventListener('error', e => {
  const t = e.target;
  if(!t || t.tagName !== 'IMG') return;
  const fb = t.dataset.fallback || '';
  const holder = t.closest('figure');
  if(!fb){ if(holder) holder.remove(); else t.remove(); return; }
  const span = document.createElement('span');
  span.className = 'img-fallback';
  span.textContent = fb;
  t.replaceWith(span);
}, true);

function emojiHTML(c){
  if(c.emoji_url) return `<img class="emoji custom" src="${esc(c.emoji_url)}" alt="${esc(c.emoji_name || '')}" data-fallback="◈" loading="lazy">`;
  return c.emoji ? `<span class="emoji">${esc(c.emoji)}</span>` : '';
}
function hhmm(ts){ return new Date((ts || Date.now() / 1000) * 1000)
  .toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }); }
async function api(path, body, method){
  const opt = { method: method || (body ? 'POST' : 'GET'), headers: {} };
  if(body){ opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  const r = await fetch(path, opt);
  let d = {}; try{ d = await r.json(); }catch(e){}
  return { ok: r.ok, status: r.status, d };
}
async function copy(text, btn){
  try{ await navigator.clipboard.writeText(text); }
  catch(e){
    const ta = document.createElement('textarea'); ta.value = text; document.body.append(ta);
    ta.select(); document.execCommand('copy'); ta.remove();
  }
  if(btn){ const t = btn.textContent; btn.textContent = 'Скопировано'; setTimeout(() => btn.textContent = t, 1400); }
}

/* ---------- тосты и журнал ---------- */
function toast(text, kind = 'info', trace){
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.innerHTML = md(text);
  if(trace){
    const d = document.createElement('details');
    d.innerHTML = '<summary>Трассировка</summary><pre>' + esc(trace) + '</pre>';
    const cp = document.createElement('button');
    cp.className = 'btn tiny secondary copy'; cp.type = 'button'; cp.textContent = 'Копировать';
    cp.onclick = () => copy(trace, cp);
    d.append(cp); el.append(d);
  }
  $('#toasts').append(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 250); }, trace ? 14000 : 5200);
  if(kind === 'error'){ sfx('ding.mp3'); logError(text, trace, 'error'); }
  else if(kind === 'warn'){ logError(text, trace, 'warn'); }
  else sfx('ding.mp3');
  if(S.modal && S.submitting && (kind === 'warn' || kind === 'error')){
    S.submitting = false; $('#modal-ok').disabled = false; $('#modal-ok').textContent = 'Подтвердить';
  }
}
function logError(text, trace, kind){
  S.errors.unshift({ text, trace, kind, t: Date.now() });
  if(S.errors.length > 60) S.errors.pop();
  renderErrors();
}
function renderErrors(){
  const n = S.errors.length, badge = $('#err-count');
  badge.textContent = n; badge.classList.toggle('hidden', n === 0);
  const list = $('#err-list');
  if(!n){ list.innerHTML = '<div class="err-empty">Ошибок нет. Всё, что сломается на сервере, появится здесь с трассировкой.</div>'; return; }
  list.innerHTML = S.errors.map(e => `<div class="err-item ${e.kind}">
    <div class="err-head"><span>${esc(e.text)}</span><time>${new Date(e.t).toLocaleTimeString('ru-RU')}</time></div>
    ${e.trace ? '<pre>' + esc(e.trace) + '</pre>' : ''}</div>`).join('');
}

/* ---------- HUD ---------- */
const VMEM = {};
function measure(v){
  const s = String(v == null ? '' : v).replace(/\*\*/g, '').trim();
  const pair = s.match(/(-?\d+(?:[.,]\d+)?)\s*\/\s*(-?\d+(?:[.,]\d+)?)/);
  if(pair) return { kind:'pair', cur:+pair[1].replace(',', '.'), max:+pair[2].replace(',', '.'), text:s };
  const pct = s.match(/(-?\d+(?:[.,]\d+)?)\s*%/);
  if(pct) return { kind:'pct', cur:+pct[1].replace(',', '.'), max:100, text:s };
  const cnt = s.match(/(-?\d+)\s*(шт|штук|ед|x|×)\b/i);
  if(cnt) return { kind:'count', count:+cnt[1], text:s };
  const mins = s.match(/(-?\d+(?:[.,]\d+)?)\s*(мин|минут|минуты|м)\b/i);
  if(mins) return { kind:'time', cur:+mins[1].replace(',', '.'), text:s };
  if(/^(нет|не установлен|отсутствует|снят|пусто|—|-)$/i.test(s)) return { kind:'empty', text:s };
  const bare = s.match(/^(-?\d+(?:[.,]\d+)?)$/);
  if(bare) return { kind:'bare', cur:+bare[1].replace(',', '.'), text:s };
  return { kind:'none', text:s };
}
function setVital(k, m){
  const box = document.querySelector(`.vital[data-k="${k}"]`); if(!box) return;
  const bar = box.querySelector('i'), out = box.querySelector('span');
  const mem = VMEM[k] || (VMEM[k] = { pct:null, peak:null });
  let pct = null;
  if(m.kind === 'pair' && m.max > 0) pct = m.cur / m.max * 100;
  else if(m.kind === 'pct') pct = m.cur;
  else if(m.kind === 'empty') pct = 0;
  else if(m.kind === 'time'){
    if(mem.peak == null || m.cur > mem.peak) mem.peak = m.cur;
    pct = mem.peak > 0 ? m.cur / mem.peak * 100 : null;
  }
  else if(m.kind === 'bare'){
    if(k === 'filter'){
      if(mem.peak == null || m.cur > mem.peak) mem.peak = m.cur;
      pct = mem.peak > 0 ? m.cur / mem.peak * 100 : null;
    } else pct = m.cur;
  }
  if(pct != null && isFinite(pct)){
    mem.pct = Math.max(0, Math.min(100, pct));
    bar.style.width = mem.pct + '%';
    box.classList.toggle('low', mem.pct < 30 && mem.pct >= 12);
    box.classList.toggle('crit', mem.pct < 12);
  }
  out.textContent = m.text || '—';
}
function stockLine(label, value){
  let dd = document.getElementById('v-filters');
  if(!dd){
    const kv = document.querySelector('.kv'); if(!kv) return;
    const row = document.createElement('div');
    row.innerHTML = '<dt>Фильтры в рюкзаке</dt><dd id="v-filters">—</dd>';
    kv.append(row); dd = row.querySelector('dd');
  }
  dd.textContent = value;
}
function updateHUD(screen){
  for(const e of (screen.embeds || [])){
    const filterCands = [];
    for(const f of (e.fields || [])){
      const raw = String(f.name || ''), n = raw.toLowerCase(), v = String(f.value || '');
      const m = measure(v);
      if(n.includes('здоров')) setVital('hp', m);
      else if(n.includes('вынослив')) setVital('st', m);
      else if(n.includes('радиа') || n.includes('фон')) setVital('rad', m);
      else if(n.includes('фильтр')){
        let score = 0;
        if(m.kind === 'pct' || m.kind === 'pair') score += 4;
        if(m.kind === 'time') score += 3;
        if(/ресурс|износ|состоян|остат|заряд|время/.test(n)) score += 3;
        if(m.kind === 'count') score -= 6;
        if(/запас|рюкзак|инвент|кол-?во|штук|в наличии/.test(n)) score -= 6;
        if(m.kind === 'empty') score += 1;
        filterCands.push({ score, m, raw });
      }
      else if(n.includes('локац') || n.includes('станц')) $('#station').textContent = v.replace(/\*\*/g, '');
      else if(n.includes('фракц')) $('#v-faction').textContent = v.replace(/\*\*/g, '');
      else if(n.includes('никел') || n.includes('деньг') || n.includes('баланс')) $('#v-money').textContent = v.replace(/\*\*/g, '');
    }
    if(filterCands.length){
      filterCands.sort((a, b) => b.score - a.score);
      const best = filterCands[0];
      if(best.score > 0 || best.m.kind === 'empty') setVital('filter', best.m);
      const stock = filterCands.find(x => x.m.kind === 'count');
      if(stock) stockLine('Фильтры в рюкзаке', stock.m.text);
    }
    const d = (e.description || '') + ' ' + (e.title || '');
    const lvl = d.match(/Уровень:\s*\**\s*(\d+)/i); if(lvl) $('#v-level').textContent = lvl[1];
    const nm = d.match(/Добро пожаловать,\s*\*\*([^*]+)\*\*/i);
    if(nm && S.user) $('#who').textContent = nm[1] + (S.user.admin ? ' · admin' : '');
  }
}

/* ---------- лента ---------- */
function componentsHTML(view){
  if(!view) return '';
  return view.rows.map(row => '<div class="row">' + row.map(c => {
    if(c.type === 'button'){
      if(c.url) return `<a class="btn link" href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.label)}</a>`;
      return `<button type="button" class="btn ${esc(c.style)}" data-view="${esc(view.id)}" data-item="${esc(c.id)}"
        ${c.disabled ? 'disabled' : ''}>${emojiHTML(c)}${esc(c.label)}</button>`;
    }
    if(c.type === 'select'){
      return `<select class="sel" data-view="${esc(view.id)}" data-item="${esc(c.id)}" ${c.disabled ? 'disabled' : ''}>
        <option value="">${esc(c.placeholder || 'Выбрать…')}</option>
        ${c.options.map(o => `<option value="${esc(o.value)}">${o.emoji ? esc(o.emoji) + ' ' : ''}${esc(o.label)}${o.description ? ' — ' + esc(o.description) : ''}</option>`).join('')}
      </select>`;
    }
    return '';
  }).join('') + '</div>').join('');
}
function cardHTML(s){
  const embeds = (s.embeds || []).map(e => {
    const col = e.color != null ? '#' + Number(e.color).toString(16).padStart(6, '0') : 'var(--amber)';
    const author = (e.author && e.author.name)
      ? `<div class="e-author">${e.author.icon_url ? `<img class="e-avatar" src="${esc(e.author.icon_url)}" alt="" data-fallback="◈" loading="lazy">` : '<i class="e-mark"></i>'}<span>${md(e.author.name)}</span></div>` : '';
    const thumb = e.thumbnail
      ? `<figure class="e-thumb"><img src="${esc(e.thumbnail)}" alt="" data-fallback="" loading="lazy"><i class="holo"></i><i class="corner tl"></i><i class="corner br"></i></figure>` : '';
    const image = e.image
      ? `<figure class="e-image"><img src="${esc(e.image)}" alt="" data-fallback="" loading="lazy"><i class="holo"></i></figure>` : '';
    const fields = (e.fields || []).map(f => `<div class="field ${f.inline ? 'inline' : ''}">
      <div class="f-name">${md(f.name)}</div><div class="f-val">${md(f.value)}</div></div>`).join('');
    const footer = (e.footer && e.footer.text)
      ? `<div class="e-footer">${e.footer.icon_url ? `<img class="e-ficon" src="${esc(e.footer.icon_url)}" alt="" data-fallback="·" loading="lazy">` : ''}${md(e.footer.text)}</div>` : '';
    return `<div class="embed ${thumb ? 'has-thumb' : ''}" style="--accent:${col}">
      <div class="e-main">${author}
        ${e.title ? `<div class="e-title">${md(e.title)}</div>` : ''}
        ${e.description ? `<div class="e-desc">${md(e.description)}</div>` : ''}
        ${fields ? `<div class="fields">${fields}</div>` : ''}
        ${image}${footer}</div>${thumb}</div>`;
  }).join('');
  return embeds + (s.content ? `<div class="content">${md(s.content)}</div>` : '') + componentsHTML(s.view);
}
function render(s){
  if(!s || !s.id) return;
  const feed = $('#feed');
  const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 180;
  let el = document.getElementById(s.id);
  if(!el){
    el = document.createElement('article');
    el.id = s.id; el.className = 'card' + (s.ephemeral ? ' ephemeral' : '');
    feed.append(el); S.order.push(s.id);
    while(S.order.length > 40){ const old = S.order.shift(); document.getElementById(old)?.remove(); S.screens.delete(old); }
  }
  el.dataset.time = hhmm(s.ts);
  el.innerHTML = cardHTML(s);
  el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
  S.screens.set(s.id, s);
  updateHUD(s);
  if(nearBottom) feed.scrollTop = feed.scrollHeight;
}
function apply(op){
  switch(op.op){
    case 'send': case 'edit': render(op); break;
    case 'delete': case 'drop':
      document.getElementById(op.id)?.remove(); S.screens.delete(op.id);
      S.order = S.order.filter(x => x !== op.id); break;
    case 'modal': openModal(op); break;
    case 'modal_close': closeModal(); break;
    case 'toast': toast(op.text, op.kind || 'info', op.trace); break;
  }
  if(S.modal && ['send','edit','delete','drop'].includes(op.op)) closeModal();
  if(op.op !== 'toast') releasePending();
}
function releasePending(){ $$('.btn.pending').forEach(b => { b.classList.remove('pending'); b.disabled = false; }); }

/* ---------- модалки ---------- */
function openModal(m){
  S.modal = m; S.submitting = false;
  $('#modal-title').textContent = m.title || 'Ввод';
  const box = $('#modal-fields'); box.innerHTML = '';
  m.fields.forEach((f, i) => {
    const wrap = document.createElement('div'); wrap.className = 'mfield'; wrap.dataset.id = f.id;
    const lab = document.createElement('label');
    lab.setAttribute('for', 'mf' + i);
    lab.innerHTML = esc(f.label) + (f.required ? ' <span class="req">*</span>' : '');
    const inp = document.createElement(f.multiline ? 'textarea' : 'input');
    inp.id = 'mf' + i; inp.name = f.id; inp.value = f.value || '';
    if(!f.multiline) inp.type = 'text';
    if(f.placeholder) inp.placeholder = f.placeholder;
    if(f.required) inp.required = true;
    if(f.min) inp.minLength = f.min;
    if(f.max) inp.maxLength = f.max;
    inp.autocomplete = 'off';
    const meta = document.createElement('div'); meta.className = 'meta';
    meta.innerHTML = `<span class="hint">${f.min ? 'от ' + f.min + ' симв.' : (f.required ? 'обязательно' : 'необязательно')}</span>
      <span class="count">${(f.value || '').length}${f.max ? ' / ' + f.max : ''}</span>`;
    const err = document.createElement('div'); err.className = 'err';
    inp.addEventListener('input', () => {
      meta.querySelector('.count').textContent = inp.value.length + (f.max ? ' / ' + f.max : '');
      wrap.classList.remove('bad'); err.textContent = '';
    });
    wrap.append(lab, inp, meta, err); box.append(wrap);
  });
  $('#modal-ok').disabled = false; $('#modal-ok').textContent = 'Подтвердить';
  $('#modal-root').classList.remove('hidden');
  sfx('ding.mp3');
  setTimeout(() => box.querySelector('input,textarea')?.focus(), 40);
}
function closeModal(){
  S.modal = null; S.submitting = false;
  $('#modal-root').classList.add('hidden'); $('#modal-fields').innerHTML = '';
}
function validateModal(){
  let ok = true;
  for(const f of S.modal.fields){
    const wrap = document.querySelector(`.mfield[data-id="${CSS.escape(f.id)}"]`);
    const inp = wrap.querySelector('input,textarea'), err = wrap.querySelector('.err');
    const v = inp.value.trim(); let msg = '';
    if(f.required && !v) msg = 'Поле обязательно';
    else if(f.min && v.length < f.min) msg = `Минимум ${f.min} символов`;
    else if(f.max && v.length > f.max) msg = `Максимум ${f.max} символов`;
    wrap.classList.toggle('bad', !!msg); err.textContent = msg;
    if(msg && ok){ inp.focus(); ok = false; }
  }
  return ok;
}
$('#modal').addEventListener('submit', e => {
  e.preventDefault();
  if(!S.modal || S.submitting || !validateModal()) return;
  const values = {};
  S.modal.fields.forEach(f => {
    const el = document.querySelector(`.mfield[data-id="${CSS.escape(f.id)}"] input, .mfield[data-id="${CSS.escape(f.id)}"] textarea`);
    values[f.id] = el.value;
  });
  S.submitting = true; $('#modal-ok').disabled = true; $('#modal-ok').textContent = 'Отправка…';
  sfx('button.mp3'); send({ type: 'submit', modal: S.modal.id, values });
  setTimeout(() => { if(S.submitting){ S.submitting = false; $('#modal-ok').disabled = false; $('#modal-ok').textContent = 'Подтвердить'; } }, 9000);
});
$('#modal-cancel').onclick = closeModal;
$('#modal-x').onclick = closeModal;
$('#modal-root').addEventListener('mousedown', e => { if(e.target === $('#modal-root')) closeModal(); });

/* ---------- ввод игры ---------- */
$('#feed').addEventListener('click', e => {
  const b = e.target.closest('button[data-item]'); if(!b || b.disabled) return;
  b.classList.add('pending'); b.disabled = true; sfx('button.mp3');
  send({ type: 'click', view: b.dataset.view, item: b.dataset.item });
  setTimeout(() => { b.classList.remove('pending'); b.disabled = false; }, 9000);
});
$('#feed').addEventListener('change', e => {
  const s = e.target.closest('select[data-item]'); if(!s || !s.value) return;
  sfx('button.mp3');
  send({ type: 'click', view: s.dataset.view, item: s.dataset.item, values: [s.value] });
  s.disabled = true; setTimeout(() => { s.disabled = false; }, 6000);
});
function send(o){
  if(S.ws && S.ws.readyState === 1){ S.ws.send(JSON.stringify(o)); return true; }
  toast('Нет связи с сервером. Нажми «Связь» или подожди автопереподключения.', 'error');
  return false;
}
function runCommand(raw){
  const txt = String(raw || '').trim().replace(/^\//, '');
  if(!txt) return;
  const parts = txt.split(/\s+/);
  let name = parts[0], rest = parts.slice(1);
  const two = parts[0] + ' ' + (parts[1] || '');
  if(S.commands.some(c => c.name === two)){ name = two; rest = parts.slice(2); }
  const meta = S.commands.find(c => c.name === name);
  if(!meta){ toast(`Команда /${name} не найдена. Нажми / чтобы увидеть список.`, 'warn'); return; }
  const params = {};
  (meta.params || []).forEach((p, i) => { if(rest[i] !== undefined) params[p] = rest[i]; });
  if(send({ type: 'command', name, params })){
    S.history.unshift(txt); S.history = [...new Set(S.history)].slice(0, 40);
    try{ localStorage.setItem('wc.hist', JSON.stringify(S.history)); }catch(e){}
    S.hIdx = -1; $('#cmd').value = ''; hideAC(); sfx('button.mp3');
  }
}
function showAC(q){
  const list = S.commands.filter(c => c.name.startsWith(q.toLowerCase())).slice(0, 9);
  S.acItems = list; S.acIdx = list.length ? 0 : -1;
  const box = $('#ac');
  if(!list.length){ hideAC(); return; }
  box.innerHTML = list.map((c, i) => `<div class="ac-item ${i === 0 ? 'sel' : ''}" data-i="${i}" role="option">
    <b>/${esc(c.name)}</b><span>${esc(c.description || '')}</span><em>${(c.params || []).join(' · ')}</em></div>`).join('');
  box.classList.remove('hidden');
}
function hideAC(){ $('#ac').classList.add('hidden'); S.acItems = []; S.acIdx = -1; }
function moveAC(d){
  if(!S.acItems.length) return;
  S.acIdx = (S.acIdx + d + S.acItems.length) % S.acItems.length;
  $$('.ac-item').forEach((el, i) => el.classList.toggle('sel', i === S.acIdx));
  $$('.ac-item')[S.acIdx]?.scrollIntoView({ block: 'nearest' });
}
function acceptAC(){
  const c = S.acItems[S.acIdx]; if(!c) return false;
  $('#cmd').value = c.name + ((c.params || []).length ? ' ' : '');
  hideAC(); $('#cmd').focus(); return true;
}
$('#ac').addEventListener('mousedown', e => {
  const it = e.target.closest('.ac-item'); if(!it) return;
  e.preventDefault(); S.acIdx = +it.dataset.i; acceptAC();
});
$('#cmd').addEventListener('input', e => {
  const v = e.target.value.replace(/^\//, '');
  if(!v || v.includes(' ')) hideAC(); else showAC(v);
});
$('#cmd').addEventListener('keydown', e => {
  if(e.key === 'Enter'){
    e.preventDefault();
    if(!$('#ac').classList.contains('hidden') && S.acIdx >= 0 && !e.target.value.includes(' ')){ if(acceptAC()) return; }
    runCommand(e.target.value);
  }
  else if(e.key === 'Tab'){ if(!$('#ac').classList.contains('hidden')){ e.preventDefault(); acceptAC(); } }
  else if(e.key === 'ArrowDown'){
    if(!$('#ac').classList.contains('hidden')){ e.preventDefault(); moveAC(1); }
    else if(S.history.length){ e.preventDefault(); S.hIdx = Math.min(S.hIdx + 1, S.history.length - 1); e.target.value = S.history[S.hIdx] || ''; }
  }
  else if(e.key === 'ArrowUp'){
    if(!$('#ac').classList.contains('hidden')){ e.preventDefault(); moveAC(-1); }
    else if(S.history.length){ e.preventDefault(); S.hIdx = Math.max(S.hIdx - 1, 0); e.target.value = S.history[S.hIdx] || ''; }
  }
  else if(e.key === 'Escape') hideAC();
});
$('#cmd-send').onclick = () => runCommand($('#cmd').value);
$$('.quick button').forEach(b => b.onclick = () => runCommand(b.dataset.cmd));
$('#force-refresh').onclick = () => { send({ type: 'refresh' }); sfx('button.mp3'); };

/* ---------- мир ---------- */
function renderWorld(w){
  S.world = w;
  const n = (w.online || []).length;
  $('#sync-text').textContent = n + ' в сети';
  $('#online-count').textContent = n;
  const list = $('#online-list');
  if(!n) list.innerHTML = '<div class="empty">Никого нет в сети</div>';
  else list.innerHTML = w.online.map(p => `<button class="who-row" type="button" data-id="${p.id}" data-login="${esc(p.login)}">
      <i class="${p.alive ? 'on' : 'off'}"></i>
      <span class="who-name">${esc(p.name)}${p.id === w.me.id ? ' (ты)' : ''}</span>
      <span class="who-loc">${esc(p.location || '—')}</span></button>`).join('');
  const near = w.nearby || [];
  $('#nearby-box').classList.toggle('hidden', near.length === 0);
  $('#nearby-names').textContent = near.map(p => p.name).join(', ');
  if(w.me && w.me.location && w.me.location !== '—') $('#station').textContent = w.me.location;
  if(w.server && w.server.addresses && w.server.addresses.length){
    const ip = w.server.addresses.find(x => x.startsWith('26.')) || w.server.addresses[0];
    $('#lan-addr').textContent = ip + ':' + w.server.port;
  }
  WC.fire('world', w);
}
$('#online-list').addEventListener('click', e => {
  const b = e.target.closest('.who-row'); if(!b) return;
  const id = +b.dataset.id;
  if(S.world && id === S.world.me.id) return;
  WC.fire('open-chat', { id, login: b.dataset.login });
  if(WC.msg){ WC.msg.open(); WC.msg.thread(id); }   // мост к новому мессенджеру: open-chat он больше не слушает
});
$('#lan-chip').onclick = e => copy('http://' + $('#lan-addr').textContent, e.currentTarget);

/* ---------- соединение ---------- */
function net(state, text){ $('#net').className = 'pill ' + state; $('#net-text').textContent = text; }
function connect(){
  clearTimeout(S.timer);
  try{ S.ws?.close(); }catch(e){}
  net('wait', 'подключение…');
  const url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
  let ws; try{ ws = new WebSocket(url); }catch(e){ scheduleReconnect(); return; }
  S.ws = ws;
  ws.onopen = () => { S.alive = true; S.retry = 800; net('on', 'на связи'); WC.fire('online', true); };
  ws.onmessage = ev => {
    let d; try{ d = JSON.parse(ev.data); }catch(e){ return; }
    if(d.type === 'snapshot'){
      S.commands = d.commands || []; S.user = d.user || null;
      $('#feed').innerHTML = ''; S.screens.clear(); S.order = [];
      $('#who').textContent = (d.user?.name || '—') + (d.user?.admin ? ' · admin' : '');
      (d.screens || []).forEach(render);
      WC.fire('ready', d.user);
    }
    else if(d.type === 'ops') (d.ops || []).forEach(apply);
    else if(d.type === 'world') renderWorld(d);
    else if(d.type === 'toast') toast(d.text, d.kind || 'info', d.trace);
    else WC.fire(d.type, d);
  };
  ws.onerror = () => net('off', 'сбой связи');
  ws.onclose = () => { S.alive = false; releasePending(); WC.fire('online', false); scheduleReconnect(); };
}
function scheduleReconnect(){
  const sec = Math.round(S.retry / 1000);
  net('off', 'нет связи · повтор через ' + sec + 'с');
  clearTimeout(S.timer); S.timer = setTimeout(connect, S.retry);
  S.retry = Math.min(S.retry * 1.7, 12000);
}
$('#reconnect').onclick = () => { S.retry = 800; connect(); };

/* ---------- вход ---------- */
let mode = 'login';
function setMode(m){
  mode = m;
  $('#tab-login').classList.toggle('active', m === 'login');
  $('#tab-reg').classList.toggle('active', m === 'reg');
  $('#auth-go').textContent = m === 'login' ? 'Войти в тоннель' : 'Создать аккаунт';
  $('#pw').autocomplete = m === 'login' ? 'current-password' : 'new-password';
  $('#auth-err').textContent = '';
}
$('#tab-login').onclick = () => setMode('login');
$('#tab-reg').onclick = () => setMode('reg');
$('#auth-form').addEventListener('submit', async e => {
  e.preventDefault();
  const body = { login: $('#lg').value.trim(), password: $('#pw').value, pin: $('#pin').value };
  const btn = $('#auth-go'); btn.disabled = true; btn.textContent = 'Проверка…'; $('#auth-err').textContent = '';
  try{
    if(mode === 'reg'){
      const reg = await api('/api/register', body);
      if(!reg.ok){ $('#auth-err').textContent = reg.d.error || 'Не удалось создать аккаунт'; return; }
    }
    const res = await api('/api/login', body);
    if(!res.ok){ $('#auth-err').textContent = res.d.error || 'Неверный логин или пароль'; return; }
    enter();
  }catch(err){
    $('#auth-err').textContent = 'Сервер недоступен: ' + err.message;
  }finally{
    btn.disabled = false; btn.textContent = mode === 'login' ? 'Войти в тоннель' : 'Создать аккаунт';
  }
});
function enter(){
  $('#auth').classList.add('hidden'); $('#app').classList.remove('hidden');
  if(S.cfg.amb) ambience(true);
  connect(); setTimeout(() => $('#cmd').focus(), 120);
}
$('#logout').onclick = async () => {
  try{ await fetch('/api/logout', { method: 'POST' }); }catch(e){}
  try{ S.ws?.close(); }catch(e){}
  location.reload();
};

/* ---------- панель вида / журнал ---------- */
$('#set-font').oninput = e => { S.cfg.font = +e.target.value; applyCfg(); saveCfg(); };
$('#set-density').onchange = e => { S.cfg.density = e.target.value; applyCfg(); saveCfg(); };
['scan','grain','motion','amb','sfx','autoref'].forEach(k => {
  $('#set-' + k).onchange = e => { S.cfg[k] = e.target.checked; applyCfg(); saveCfg(); };
});
$('#set-reset').onclick = () => {
  S.cfg = { font: 15, density: 'normal', scan: true, grain: true, motion: true, amb: true, sfx: true, autoref: true };
  applyCfg(); saveCfg(); toast('Вид терминала сброшен', 'success');
};
$('#feed-clear').onclick = () => {
  $('#feed').innerHTML = ''; S.screens.clear(); S.order = [];
  toast('Лента очищена. Состояние игры не изменилось — /menu вернёт экран.', 'info');
};
$('#sound').onclick = () => {
  const on = !(S.cfg.sfx || S.cfg.amb);
  S.cfg.sfx = on; S.cfg.amb = on; applyCfg(); saveCfg();
  if(on) sfx('button.mp3');
};
$('#errors-btn').onclick = () => { $('#drawer').classList.toggle('hidden'); renderErrors(); };
$('#drawer-x').onclick = () => $('#drawer').classList.add('hidden');
$('#err-clear').onclick = () => { S.errors = []; renderErrors(); };
$('#err-copy').onclick = e => copy(S.errors.map(x =>
  `[${new Date(x.t).toLocaleString('ru-RU')}] ${x.kind}: ${x.text}\n${x.trace || ''}`).join('\n\n'), e.target);

document.addEventListener('keydown', e => {
  if(e.key === 'Escape'){
    if(S.modal) closeModal();
    else if(!$('#msg').classList.contains('hidden')) WC.fire('close-msg');
    else if(!$('#drawer').classList.contains('hidden')) $('#drawer').classList.add('hidden');
    else hideAC();
  }
  if((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'm'){ e.preventDefault(); WC.fire('toggle-msg'); }
  if(e.key === '/' && document.activeElement !== $('#cmd') && !S.modal &&
     !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){
    e.preventDefault(); $('#cmd').focus(); showAC('');
  }
  if((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k'){ e.preventDefault(); $('#cmd').focus(); showAC(''); }
});
document.addEventListener('pointerdown', () => { if(S.cfg.amb) ambience(true); }, { once: true });
window.addEventListener('online', () => { if(!S.alive && !$('#app').classList.contains('hidden')){ S.retry = 800; connect(); } });

/* ---------- старт ---------- */
loadCfg();
try{ S.history = JSON.parse(localStorage.getItem('wc.hist') || '[]'); }catch(e){ S.history = []; }
applyCfg(); renderErrors();
(async () => {
  try{
    const lan = await api('/api/lan');
    if(lan.ok){
      S.lan = lan.d;
      if(lan.d.pin) $('#pin-fld').classList.remove('hidden');
      const urls = ['127.0.0.1', ...(lan.d.addresses || [])].map(ip => `http://${ip}:${lan.d.port}`);
      $('#lan-box').classList.remove('hidden');
      $('#lan-list').innerHTML = urls.map(u => `<button type="button" class="lan-url" data-u="${esc(u)}">${esc(u)}</button>`).join('');
      $('#lan-list').onclick = e => { const b = e.target.closest('.lan-url'); if(b) copy(b.dataset.u, b); };
    }
  }catch(e){}
  try{ const r = await fetch('/api/me'); if(r.ok) enter(); }catch(e){}
})();
})();