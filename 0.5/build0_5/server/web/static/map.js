/* СХЕМА ЛИНИИ D6 — интерактивная карта метро.
Раскладка «Москва» ставит станции по реальной схеме Московского метрополитена,
связи и переходы берутся из данных игры. */
(() => {
'use strict';
const WC = window.WC; if(!WC) return;
const $ = s => document.querySelector(s);
const root = $('#mapx'), cv = $('#map-canvas'), ctx = cv.getContext('2d');
const LS = 'wc.map.v2';

/* ══════════ РЕАЛЬНАЯ СХЕМА МОСКОВСКОГО МЕТРОПОЛИТЕНА ══════════ */
const MSK_LINES = [
['1','Сокольническая','#ff3b30'], ['2','Замоскворецкая','#2fbf4f'],
['3','Арбатско-Покровская','#0a63c9'], ['4','Филёвская','#3fb6ff'],
['4В','Филёвская (ответвление)','#3fb6ff'], ['5','Кольцевая','#a1662f'],
['6','Калужско-Рижская','#ff8a1f'], ['7','Таганско-Краснопресненская','#a13bd6'],
['8','Калининская','#ffd21f'], ['8А','Солнцевская','#ffd21f'],
['9','Серпуховско-Тимирязевская','#9aa5ad'], ['10','Люблинско-Дмитровская','#a8e05f'],
['11','Большая кольцевая','#37d6c8'], ['12','Бутовская','#7fa8c9'],
['15','Некрасовская','#ff5cc8'], ['16','Троицкая','#ff7a5c']
];
const MSK_RAW = {
'1':'Бульвар Рокоссовского|785|255;Черкизовская|757|283;Преображенская площадь|729|311;Сокольники|701|339;Красносельская|668|375;Комсомольская|634|412;Красные Ворота|601|401;Чистые пруды|566|392;Лубянка|534|424;Охотный Ряд|497|462;Библиотека имени Ленина|462|512;Кропоткинская|414|540;Парк культуры|366|568;Фрунзенская|340|595;Спортивная|315|620;Воробьёвы горы|290|645;Университет|265|670;Проспект Вернадского|240|695;Юго-Западная|215|720;Тропарёво|190|745;Румянцево|165|770;Саларьево|140|795;Филатов луг|115|820;Прокшино|95|840;Ольховая|75|860;Коммунарка|55|880',
'2':'Ховрино|400|55;Беломорская|400|90;Речной вокзал|400|125;Водный стадион|400|160;Войковская|400|195;Сокол|406|230;Аэропорт|412|268;Динамо|418|308;Белорусская|422|356;Маяковская|456|400;Тверская|490|440;Театральная|515|480;Новокузнецкая|545|545;Павелецкая|578|624;Автозаводская|600|680;Технопарк|610|715;Коломенская|620|752;Каширская|630|790;Кантемировская|640|826;Царицыно|650|862;Орехово|660|894;Домодедовская|670|926;Красногвардейская|680|958;Алма-Атинская|700|990',
'3':'Пятницкое шоссе|25|300;Митино|55|320;Волоколамская|85|340;Мякинино|115|360;Строгино|145|380;Крылатское|175|400;Молодёжная|205|420;Кунцевская|240|440;Славянский бульвар|272|456;Парк Победы|302|472;Киевская|345|490;Смоленская|400|516;Арбатская|452|540;Площадь Революции|497|498;Курская|655|490;Бауманская|700|470;Электрозаводская|742|450;Семёновская|778|430;Партизанская|812|410;Измайловская|846|386;Первомайская|876|362;Щёлковская|906|338',
'4':'Кунцевская|240|454;Пионерская|214|478;Филёвский парк|196|506;Багратионовская|180|534;Фили|166|562;Кутузовская|152|590;Студенческая|205|574;Киевская|345|504;Смоленская|400|532;Александровский сад|440|528',
'4В':'Киевская|345|504;Выставочная|300|548;Международная|268|562',
'5':'Киевская|345|490;Краснопресненская|366|412;Белорусская|422|356;Новослободская|500|335;Проспект Мира|578|356;Комсомольская|634|412;Курская|655|490;Таганская|634|568;Павелецкая|578|624;Добрынинская|500|645;Октябрьская|422|624;Парк культуры|366|568',
'6':'Медведково|700|40;Бабушкинская|690|76;Свиблово|680|112;Ботанический сад|670|148;ВДНХ|655|186;Алексеевская|640|226;Рижская|620|272;Проспект Мира|586|348;Сухаревская|592|370;Тургеневская|583|383;Китай-город|600|450;Третьяковская|548|560;Октябрьская|422|624;Шаболовская|400|666;Ленинский проспект|380|702;Академическая|362|738;Профсоюзная|346|772;Новые Черёмушки|330|806;Калужская|315|840;Беляево|300|874;Коньково|286|906;Тёплый Стан|272|938;Ясенево|258|968;Новоясеневская|244|998',
'7':'Планерная|118|118;Сходненская|148|148;Тушинская|178|178;Спартак|204|204;Щукинская|230|230;Октябрьское Поле|258|258;Полежаевская|288|288;Беговая|318|318;Улица 1905 года|348|348;Баррикадная|372|386;Пушкинская|480|430;Кузнецкий Мост|552|437;Китай-город|606|458;Таганская|634|568;Пролетарская|666|592;Волгоградский проспект|700|622;Текстильщики|740|656;Кузьминки|776|690;Рязанский проспект|812|722;Выхино|846|752;Лермонтовский проспект|880|782;Жулебино|914|812;Котельники|948|842',
'8':'Новокосино|962|520;Новогиреево|926|520;Перово|890|520;Шоссе Энтузиастов|854|520;Авиамоторная|816|520;Площадь Ильича|762|522;Марксистская|650|552;Третьяковская|552|566',
'8А':'Деловой центр|300|556;Парк Победы|302|472;Минская|256|500;Ломоносовский проспект|226|522;Раменки|200|546;Мичуринский проспект|176|572;Озёрная|150|600;Говорово|124|626;Солнцево|98|652;Боровское шоссе|72|678;Новопеределкино|46|704;Рассказовка|20|730;Аэропорт Внуково|-6|756',
'9':'Алтуфьево|478|18;Бибирево|478|54;Отрадное|478|90;Владыкино|478|126;Петровско-Разумовская|478|162;Тимирязевская|478|198;Дмитровская|478|234;Савёловская|478|270;Менделеевская|490|322;Цветной бульвар|506|392;Чеховская|496|446;Боровицкая|430|546;Полянка|456|592;Серпуховская|506|650;Тульская|506|700;Нагатинская|506|740;Нагорная|506|776;Нахимовский проспект|506|812;Севастопольская|506|848;Чертановская|506|884;Южная|506|920;Пражская|506|956;Улица Академика Янгеля|506|992;Аннино|506|1028;Бульвар Дмитрия Донского|506|1064',
'10':'Физтех|560|8;Лианозово|556|44;Яхромская|552|80;Селигерская|548|116;Верхние Лихоборы|542|152;Окружная|536|188;Петровско-Разумовская|490|172;Фонвизинская|520|216;Бутырская|540|252;Марьина Роща|556|292;Достоевская|546|342;Трубная|512|396;Сретенский бульвар|592|400;Чкаловская|662|458;Римская|766|532;Крестьянская застава|672|602;Дубровка|690|662;Кожуховская|702|702;Печатники|722|746;Волжская|736|790;Люблино|750|832;Братиславская|766|872;Марьино|782|912;Зябликово|690|962',
'12':'Битцевский парк|248|1004;Лесопарковая|330|1032;Улица Старокачаловская|500|1070;Улица Скобелевская|560|1096;Бульвар Адмирала Ушакова|612|1118;Улица Горчакова|654|1138;Бунинская аллея|694|1158',
'15':'Электрозаводская|748|458;Лефортово|792|492;Авиамоторная|822|528;Нижегородская|832|572;Стахановская|862|612;Окская|888|648;Юго-Восточная|914|684;Косино|886|788;Улица Дмитриевского|920|822;Лухмановская|950|856;Некрасовка|980|890',
'16':'ЗИЛ|620|700;Крымская|560|736;Академическая|368|746;Вавиловская|340|776;Новаторская|302|802;Университет дружбы народов|272|832;Генерала Тюленева|246|862;Тютчевская|220|892;Корниловская|194|922;Бачуринская|168|952;Коммунарка|140|982;Сосенки|112|1012;Троицк|84|1042'
};
const BKL_ORDER = ['Марьина Роща','Рижская','Сокольники','Электрозаводская','Лефортово','Авиамоторная',
'Нижегородская','Текстильщики','Печатники','Нагатинский Затон','Кленовый бульвар','Каширская','Варшавская',
'Каховская','Зюзино','Воронцовская','Новаторская','Проспект Вернадского','Мичуринский проспект','Аминьевская',
'Давыдково','Кунцевская','Терехово','Мнёвники','Народное Ополчение','Шелепиха','Деловой центр','Хорошёвская',
'ЦСКА','Петровский парк','Савёловская'];
const HUB_ALIAS = { 'каховская':'Севастопольская','воронцовская':'Калужская','хорошёвская':'Полежаевская',
'петровский парк':'Динамо','марксистская':'Таганская','чкаловская':'Курская','римская':'Площадь Ильича',
'крестьянская застава':'Пролетарская','косино':'Лермонтовский проспект','зябликово':'Красногвардейская',
'битцевский парк':'Новоясеневская','улица старокачаловская':'Бульвар Дмитрия Донского',
'менделеевская':'Новослободская','баррикадная':'Краснопресненская','трубная':'Цветной бульвар',
'сретенский бульвар':'Чистые пруды','тургеневская':'Чистые пруды','кузнецкий мост':'Лубянка',
'пушкинская':'Тверская','чеховская':'Тверская','театральная':'Охотный Ряд',
'площадь революции':'Охотный Ряд','арбатская':'Библиотека имени Ленина',
'александровский сад':'Библиотека имени Ленина','боровицкая':'Библиотека имени Ленина',
'новокузнецкая':'Третьяковская','добрынинская':'Серпуховская','выставочная':'Деловой центр',
'международная':'Деловой центр' };
const NAME_ALIAS = { 'библиотека им ленина':'Библиотека имени Ленина','библиотека имени ленина':'Библиотека имени Ленина',
'воробьевы горы':'Воробьёвы горы','проспект мира':'Проспект Мира','китай город':'Китай-город',
'китайгород':'Китай-город','петровско разумовская':'Петровско-Разумовская','улица 1905 года':'Улица 1905 года',
'октябрьское поле':'Октябрьское Поле','шоссе энтузиастов':'Шоссе Энтузиастов','площадь ильича':'Площадь Ильича',
'марьина роща':'Марьина Роща','савеловская':'Савёловская','рижская':'Рижская','теплый стан':'Тёплый Стан',
'новые черемушки':'Новые Черёмушки','тропарево':'Тропарёво','щелковская':'Щёлковская','семеновская':'Семёновская',
'алтуфьево':'Алтуфьево','медведково':'Медведково','бульвар рокоссовского':'Бульвар Рокоссовского' };
const norm = s => String(s||'').toLowerCase().replace(/ё/g,'е').replace(/[^a-zа-я0-9]+/g,'');
const MSK = new Map();          // norm(имя) -> [{x,y,line,color,name}]
(function buildMSK(){
const meta = new Map(MSK_LINES.map(l => [l[0], l]));
const push = (name, lid, x, y) => {
const m = meta.get(lid); if(!m) return;
const key = norm(name);
if(!MSK.has(key)) MSK.set(key, []);
MSK.get(key).push({ name, x, y, line:m[1], num:lid, color:m[2] });
};
for(const [lid, str] of Object.entries(MSK_RAW)){
for(const chunk of str.split(';')){
const [name, x, y] = chunk.split('|');
push(name.trim(), lid, parseFloat(x), parseFloat(y));
}
}
const n = BKL_ORDER.length;
BKL_ORDER.forEach((name, i) => {
const a = -Math.PI/2 + (i/n) * Math.PI*2;
let x = 500 + Math.cos(a)*352, y = 500 + Math.sin(a)*338;
const key = norm(name);
const anchorName = HUB_ALIAS[key] ? norm(HUB_ALIAS[key]) : key;
const anchor = MSK.get(anchorName);
if(anchor && anchor.length){
const a0 = anchor[0];
const dx = a0.x - 500, dy = a0.y - 500, len = Math.hypot(dx,dy) || 1;
x = a0.x + dx/len*17 + 9; y = a0.y + dy/len*17 + 9;
}
push(name, '11', x, y);
});
})();

/* ══════════ СОСТОЯНИЕ ══════════ */
const THEMES = {
tunnel:{ bg:'#070c10', deep:'#0d151c', grid:'#16222c', ink:'#e9e0cd', mute:'#8ea3b0' },
radio:{ bg:'#06110a', deep:'#0b1a11', grid:'#16301f', ink:'#dff5cf', mute:'#7fa88a' },
night:{ bg:'#070c16', deep:'#0d1424', grid:'#182238', ink:'#dfe6f5', mute:'#8492b0' }
};
const C = { zoom:1, node:1, line:7, glow:12, fog:.3, speed:1, labels:'smart', theme:'tunnel',
terr:true, rad:true, tech:true, surf:true, danger:true, grid:false, players:true,
layout:'msk', spread:1 };
const S = { data:null, byId:new Map(), open:false, raf:0, dpr:1, W:1, H:1,
cam:{x:500,y:560,z:.7,tx:500,ty:560,tz:.7}, hover:null, sel:null,
route:[], walking:false, walkIdx:0, t:0, drag:null, pinch:null, lastTick:0,
dirty:true, online:[], me:null, matched:0, unmatched:0, errs:0, pending:null, ro:null };
try{ Object.assign(C, JSON.parse(localStorage.getItem(LS)||'{}')); }catch(e){}
const save = () => { try{ localStorage.setItem(LS, JSON.stringify(C)); }catch(e){} };
const clamp = (v,a,b) => Math.max(a, Math.min(b, v));
const lerp = (a,b,t) => a + (b-a)*t;
const theme = () => THEMES[C.theme] || THEMES.tunnel;
if(!ctx.roundRect){ ctx.roundRect = function(x,y,w,h,r){ this.beginPath();
this.moveTo(x+r,y); this.arcTo(x+w,y,x+w,y+h,r); this.arcTo(x+w,y+h,x,y+h,r);
this.arcTo(x,y+h,x,y,r); this.arcTo(x,y,x+w,y,r); this.closePath(); return this; }; }
const SERV_COLOR = { trader:'#ffd23f', npc:'#4aa8ff', doctor:'#ff7b9c', workshop:'#b9a06a',
campfire:'#ff8a3d', start:'#66ff99', food:'#c6ff7a', faction:'#9b7bff', quest:'#ff5cc8' };
const SERV_LABEL = { trader:'торговля', npc:'NPC', doctor:'медик', workshop:'мастерская',
campfire:'костёр', start:'стартовая', food:'еда', faction:'фракция', quest:'задания' };
const stColor = s => s._color || '#ff8a3d';
const stLine  = s => s._line || s.line || 'Тоннели';
function factionColor(name){
if(!name) return '#8ea3b0';
let h = 0; for(const ch of name) h = (h*31 + ch.charCodeAt(0)) >>> 0;
return `hsl(${h % 360} 68% 56%)`;
}

/* ══════════ РАСКЛАДКА ══════════ */
function applyLayout(){
if(!S.data) return;
S.matched = 0; S.unmatched = 0;
const used = new Map();
for(const s of S.data.stations){
s._gx = s.x; s._gy = s.y;
if(C.layout === 'graph'){
s._color = (S.data.lines.find(l => l.id === s.line_id) || {}).color || '#ff8a3d';
s._line = s.line; s._num = null; s._msk = false;
continue;
}
const aliasKey = NAME_ALIAS[norm(s.name)];
const key = aliasKey ? norm(aliasKey) : norm(s.name);
let cands = MSK.get(key);
if(!cands){
const idKey = norm(s.id);
cands = MSK.get(idKey);
}
if(cands && cands.length){
let pick = cands[0];
const hint = norm(s.line || '');
if(hint){
const byLine = cands.find(c => hint.includes(norm(c.line)) || norm(c.num) === hint);
if(byLine) pick = byLine;
}
const k = norm(pick.name) + pick.num;
const dup = used.get(k) || 0; used.set(k, dup + 1);
const off = dup ? 13 * C.spread * dup : 0;
s.x = pick.x + off; s.y = pick.y + off * .6;
s._color = pick.color; s._line = pick.line; s._num = pick.num; s._msk = true;
S.matched++;
} else {
s._msk = false; s._color = '#7f8c99'; s._line = s.line || 'Вне схемы'; s._num = null;
S.unmatched++;
}
}
const orphans = S.data.stations.filter(s => !s._msk && C.layout === 'msk');
orphans.forEach((s, i) => {
const near = (s.links||[]).map(l => S.byId.get(l.to)).filter(o => o && o._msk);
if(near.length){
const cx = near.reduce((a,o)=>a+o.x,0)/near.length;
const cy = near.reduce((a,o)=>a+o.y,0)/near.length;
const a = (i * 2.399) % (Math.PI * 2);
s.x = cx + Math.cos(a) * 46 * C.spread; s.y = cy + Math.sin(a) * 46 * C.spread;
} else {
const cols = 6, col = i % cols, row = Math.floor(i / cols);
s.x = 40 + col * 74; s.y = 1210 + row * 58;
}
});
renderLegend();
S.dirty = true;
}
function renderLegend(){
const box = $('#map-lines'); if(!box || !S.data) return;
if(C.layout === 'msk'){
const present = new Map();
for (const s of S.data.stations) if(s._msk) present.set(s._num, { name:s._line, color:s._color });
const order = MSK_LINES.filter(l => present.has(l[0]));
box.innerHTML = order.map(l => {
const p = present.get(l[0]);
return `<div><i style="background:${p.color};color:${p.color}"></i> <b style="font:700 10px ui-monospace,monospace;opacity:.8">${l[0]}</b> ${WC.esc(p.name)}</div>`;
}).join('') || '<div style="color:#8ea3b0;font-size:12px">Совпадений со схемой нет</div>';
} else {
box.innerHTML = S.data.lines.map(l =>
`<div><i style="background:${l.color};color:${l.color}"></i>${WC.esc(l.name)}</div>`).join('');
}
const note = $('#m-note');
if(note) note.textContent = C.layout === 'msk'
? `по схеме: ${S.matched} · вне схемы: ${S.unmatched}`
: `граф игры: ${S.data.stations.length} станций`;
}

/* ══════════ ДАННЫЕ ══════════ */
async function load(force){
const box = $('#map-load');
box.classList.remove('hidden');
box.innerHTML = '<div class="loader"><i></i><i></i><i></i></div><span>Читаю станции метро…</span>';
let r;
try{ r = await WC.api('/api/map' + (force ? '?force=1' : '')); }
catch(e){ r = { ok:false, d:{ error:String(e) } }; }
if(!r.ok || !r.d || !r.d.ok || !Array.isArray(r.d.stations) || !r.d.stations.length){
const err = (r.d && (r.d.error || r.d.reason)) || 'Сервер не отдал список станций';
box.innerHTML = `<div class="loader"><i></i><i></i><i></i></div><span>${WC.esc(err)}</span> <button class="mbtn" id="map-retry" type="button">Повторить</button>`;
$('#map-retry').onclick = () => load(true);
S.dirty = true; return;
}
S.data = r.d;
S.byId = new Map(r.d.stations.map(s => [s.id, s]));
S.me = r.d.me || null;
S.online = (r.d.online || []).map(p => ({ id:p.id, name:p.name, station:p.station || resolveByName(p.location) }));
for(const s of S.data.stations){
s._adj = (s.links||[]).map(l => l.to).filter(id => S.byId.has(id));
s._key = (s.services||[]).some(x => ['trader','npc','start','faction'].includes(x)) || s._adj.length > 2;
}
applyLayout();
$('#map-sub').textContent = `${r.d.stations.length} станций · ${S.matched} на схеме Москвы`;
box.classList.add('hidden');
resize(); fit(true);
if(S.me && S.me.station) selectStation(S.me.station, false);
S.dirty = true;
}
function resolveByName(loc){
if(!loc || !S.data) return null;
const k = norm(loc);
const hit = S.data.stations.find(s => norm(s.id) === k || norm(s.name) === k);
return hit ? hit.id : null;
}

/* ══════════ КАМЕРА ══════════ */
function resize(){
const rect = cv.getBoundingClientRect();
const w = Math.max(1, Math.round(rect.width)), h = Math.max(1, Math.round(rect.height));
S.dpr = Math.min(2, window.devicePixelRatio || 1);
if(w === S.W && h === S.H && cv.width === Math.round(w * S.dpr)) return;
S.W = w; S.H = h;
cv.width = Math.round(w * S.dpr); cv.height = Math.round(h * S.dpr);
ctx.setTransform(S.dpr,0,0,S.dpr,0,0);
S.dirty = true;
}
const toScreen = (x,y) => [ (x-S.cam.x)*S.cam.z + S.W/2, (y-S.cam.y)*S.cam.z + S.H/2 ];
const toWorld  = (x,y) => [ (x-S.W/2)/S.cam.z + S.cam.x, (y-S.H/2)/S.cam.z + S.cam.y ];
function bounds(){
const list = [...S.byId.values()];
if(!list.length) return { cx:500, cy:560, w:1000, h:1100 };
const xs = list.map(s=>s.x), ys = list.map(s=>s.y);
const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
return { cx:(x0+x1)/2, cy:(y0+y1)/2, w:(x1-x0)+180, h:(y1-y0)+180 };
}
function baseZoom(){ const b = bounds(); return clamp(Math.min(S.W/b.w, S.H/b.h), .18, 2.4); }
function fit(instant){
const b = bounds(), z = clamp(baseZoom()*C.zoom, .18, 3.2);
S.cam.tx = b.cx; S.cam.ty = b.cy; S.cam.tz = z;
if(instant){ S.cam.x = b.cx; S.cam.y = b.cy; S.cam.z = z; }
S.dirty = true;
}
function flyTo(id, z){
const s = S.byId.get(id); if(!s) return;
S.cam.tx = s.x; S.cam.ty = s.y; S.cam.tz = clamp(z || Math.max(S.cam.tz, 1.2), .18, 3.2);
S.dirty = true;
}

/* ══════════ ОТРИСОВКА ══════════ */
function drawEmpty(msg){
const T = theme();
ctx.fillStyle = T.bg; ctx.fillRect(0,0,S.W,S.H);
ctx.strokeStyle = T.grid; ctx.lineWidth = 1; ctx.globalAlpha = .5;
for(let x=0;x<S.W;x+=48){ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,S.H); ctx.stroke(); }
for(let y=0;y<S.H;y+=48){ ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(S.W,y); ctx.stroke(); }
ctx.globalAlpha = 1;
ctx.fillStyle = T.mute; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
ctx.font = '600 13px ui-monospace, monospace';
ctx.fillText(msg || 'Схема пуста', S.W/2, S.H/2);
ctx.textAlign = 'left';
}
function draw(){
if(!S.data || !S.byId.size){ drawEmpty('Загружаю схему метро…'); return; }
const T = theme(), z = S.cam.z;
ctx.fillStyle = T.bg; ctx.fillRect(0,0,S.W,S.H);
const g = ctx.createRadialGradient(S.W*.32, S.H*.18, 30, S.W*.5, S.H*.5, Math.max(S.W,S.H)*.95);
g.addColorStop(0, T.deep); g.addColorStop(1, T.bg);
ctx.fillStyle = g; ctx.fillRect(0,0,S.W,S.H);
if(C.grid){
const step = 60 * z, ox = (-S.cam.x * z + S.W/2) % step, oy = (-S.cam.y * z + S.H/2) % step;
ctx.strokeStyle = T.grid; ctx.lineWidth = 1; ctx.globalAlpha = .5; ctx.beginPath();
for(let x=ox;x<S.W;x+=step){ ctx.moveTo(x,0); ctx.lineTo(x,S.H); }
for(let y=oy;y<S.H;y+=step){ ctx.moveTo(0,y); ctx.lineTo(S.W,y); }
ctx.stroke(); ctx.globalAlpha = 1;
}
if(C.terr){
for(const s of S.byId.values()){
if(!s.faction) continue;
const [x,y] = toScreen(s.x,s.y), r = 74 * z * C.node, col = factionColor(s.faction);
const rg = ctx.createRadialGradient(x,y,2,x,y,Math.max(4,r));
rg.addColorStop(0, col.replace('hsl','hsla').replace(')',' / .20)'));
rg.addColorStop(1, col.replace('hsl','hsla').replace(')',' / 0)'));
ctx.fillStyle = rg; ctx.beginPath(); ctx.arc(x,y,Math.max(4,r),0,7); ctx.fill();
}
}
if(C.rad){
for(const s of S.byId.values()){
const lvl = Math.max(s.radiation||0, s.surface ? 42 : 0); if(lvl <= 0) continue;
const [x,y] = toScreen(s.x,s.y);
const r = Math.max(6,(30 + lvl * .5) * z * C.node) * (1 + Math.sin(S.t * 1.5 + s.x * .01) * .05 * C.speed);
const rg = ctx.createRadialGradient(x,y,2,x,y,r);
rg.addColorStop(0,'rgba(255,92,200,.22)'); rg.addColorStop(.55,'rgba(255,77,61,.11)'); rg.addColorStop(1,'rgba(255,92,200,0)');
ctx.fillStyle = rg; ctx.beginPath(); ctx.arc(x,y,r,0,7); ctx.fill();
}
}
ctx.lineCap = 'round'; ctx.lineJoin = 'round';
const drawn = new Set();
for(const s of S.byId.values()){
for(const link of (s.links||[])){
const o = S.byId.get(link.to); if(!o) continue;
const key = [s.id,o.id].sort().join('|'); if(drawn.has(key)) continue; drawn.add(key);
const kind = link.kind || 'tunnel';
if(kind === 'tech' && !C.tech) continue;
if(kind === 'surface' && !C.surf) continue;
const [x1,y1] = toScreen(s.x,s.y), [x2,y2] = toScreen(o.x,o.y);
const same = stLine(s) === stLine(o);
const dx = x2-x1, dy = y2-y1, len = Math.hypot(dx,dy)||1;
const bend = same ? 0 : Math.min(24 * z, len * .12);
const cxp = (x1+x2)/2 - dy/len * bend, cyp = (y1+y2)/2 + dx/len * bend;
const width = Math.max(1.2, (same ? C.line : C.line*.55) * clamp(z,.45,1.6));
ctx.save();
if(kind !== 'tunnel') ctx.setLineDash(kind === 'tech' ? [7 * z, 6 * z] : [3 * z, 7 * z]);
ctx.strokeStyle = 'rgba(0,0,0,.55)'; ctx.lineWidth = width+4;
ctx.beginPath(); ctx.moveTo(x1,y1); ctx.quadraticCurveTo(cxp,cyp,x2,y2); ctx.stroke();
if(C.glow > 0){ ctx.shadowColor = same ? stColor(s) : '#7f8c99'; ctx.shadowBlur = C.glow*clamp(z,.5,1.3); }
ctx.strokeStyle = same ? stColor(s) : (kind === 'surface' ? '#ff5cc8' : '#6f8290');
ctx.lineWidth = width; ctx.globalAlpha = same ? 1 : .72;
ctx.beginPath(); ctx.moveTo(x1,y1); ctx.quadraticCurveTo(cxp,cyp,x2,y2); ctx.stroke();
ctx.restore();
}
}
if(S.route.length > 1){
ctx.save();
ctx.setLineDash([12,9]); ctx.lineDashOffset = -S.t * 34 * C.speed;
ctx.strokeStyle = '#ffd23f'; ctx.lineWidth = Math.max(2.5, C.line*.55)*clamp(z,.6,1.5);
ctx.shadowColor = '#ffd23f'; ctx.shadowBlur = 16; ctx.beginPath();
S.route.forEach((id,i) => { const s = S.byId.get(id); if(!s) return;
const [x,y] = toScreen(s.x,s.y); i ? ctx.lineTo(x,y) : ctx.moveTo(x,y); });
ctx.stroke(); ctx.restore();
}
const labels = [];
for(const s of S.byId.values()){
const [x,y] = toScreen(s.x,s.y);
if(x < -90 || y < -90 || x > S.W+90 || y > S.H+90) continue;
const inter = new Set((s.links||[]).map(l => { const o = S.byId.get(l.to); return o ? stLine(o) : null; })).size > 1;
const base = Math.max(2.6, (inter ? 8 : 5.6) * C.node * clamp(z,.5,1.7));
const isMe = S.me && s.id === S.me.station, isSel = S.sel === s.id, isHov = S.hover === s.id;
const onRoute = S.route.includes(s.id);
if(C.danger && s.danger > 0){
ctx.strokeStyle = `rgba(255,77,61,${clamp(.16+s.danger*.08,.16,.65)})`;
ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x,y,base+5+s.danger*2,0,7); ctx.stroke();
}
if(isMe){
const p = (S.t * 1.05 * Math.max(.2,C.speed)) % 1;
ctx.strokeStyle = `rgba(255,210,63,${(1-p)*.85})`; ctx.lineWidth = 2.5;
ctx.beginPath(); ctx.arc(x,y,base+6+p*26,0,7); ctx.stroke();
}
ctx.save();
if(C.glow > 0){ ctx.shadowColor = isMe ? '#ffd23f' : stColor(s); ctx.shadowBlur = C.glow*(isMe?1.6:1); }
ctx.fillStyle = inter ? '#0d141a' : '#0a1015';
ctx.strokeStyle = isMe ? '#ffd23f' : (isSel ? '#ffffff' : stColor(s));
ctx.lineWidth = (inter ? 3.2 : 2.4) * clamp(z,.6,1.6);
ctx.beginPath(); ctx.arc(x,y,base,0,7); ctx.fill(); ctx.stroke();
ctx.restore();
const dot = (s.services||[]).find(k => SERV_COLOR[k]);
if(dot && base > 3.4){ ctx.fillStyle = SERV_COLOR[dot]; ctx.beginPath(); ctx.arc(x,y,base*.42,0,7); ctx.fill(); }
if(s.surface){ ctx.strokeStyle = '#ff5cc8'; ctx.lineWidth = 1.3; ctx.beginPath(); ctx.arc(x,y,base+3.4,0,7); ctx.stroke(); }
if(!s._msk && C.layout === 'msk'){
ctx.strokeStyle = '#7f8c99'; ctx.setLineDash([3,3]); ctx.lineWidth = 1;
ctx.beginPath(); ctx.arc(x,y,base+5,0,7); ctx.stroke(); ctx.setLineDash([]);
}
if(onRoute && base > 3){
const idx = S.route.indexOf(s.id);
ctx.fillStyle = idx < S.walkIdx ? '#66ff99' : (idx === S.walkIdx ? '#ffd23f' : '#0d141a');
ctx.strokeStyle = '#ffd23f'; ctx.lineWidth = 1.5;
ctx.beginPath(); ctx.arc(x+base+9, y-base-9, 8, 0, 7); ctx.fill(); ctx.stroke();
ctx.fillStyle = idx <= S.walkIdx ? '#0d1116' : '#ffd23f';
ctx.font = '700 10px ui-monospace, monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
ctx.fillText(String(idx), x+base+9, y-base-8.5); ctx.textAlign = 'left';
}
if(isHov || isSel){
ctx.strokeStyle = isSel ? '#fff' : '#ffd23f'; ctx.lineWidth = 1.2; ctx.globalAlpha = .85;
ctx.beginPath(); ctx.arc(x,y,base+7,0,7); ctx.stroke(); ctx.globalAlpha = 1;
}
const show = C.labels === 'all' ||
(C.labels === 'smart' && (z > .8 || s._key || isMe || isSel || onRoute)) ||
(C.labels === 'key' && (s._key || isMe || isSel || onRoute));
if(show) labels.push({ s, x, y, base, isMe, isSel });
}
ctx.textBaseline = 'middle';
const taken = [];
labels.sort((a,b) => (b.isMe?2:b.isSel?1:0)-(a.isMe?2:a.isSel?1:0) || b.base-a.base);
for(const it of labels){
const size = clamp(11*clamp(z,.7,1.3), 9.5, 15);
ctx.font = `${it.isMe||it.isSel ? 700 : 600} ${size}px ui-monospace, "Cascadia Mono", monospace`;
const w = ctx.measureText(it.s.name).width, h = size+4;
const bx = it.x+it.base+8, by = it.y-h/2, box = [bx-3, by-1, w+6, h+2];
if(box[0] > S.W || box[1] > S.H || box[1]+box[3] < 0) continue;
if(taken.some(t => !(box[0]+box[2] < t[0] || t[0]+t[2] < box[0] || box[1]+box[3] < t[1] || t[1]+t[3] < box[1]))) continue;
taken.push(box);
ctx.fillStyle = 'rgba(6,10,14,.8)';
ctx.roundRect(box[0],box[1],box[2],box[3],4); ctx.fill();
ctx.fillStyle = it.isMe ? '#ffd23f' : (it.isSel ? '#fff' : theme().ink);
ctx.fillText(it.s.name, bx, it.y);
}
if(C.players){
const grouped = new Map();
for(const p of S.online){
const sid = p.station || resolveByName(p.location);
if(!sid || (S.me && p.id === S.me.id)) continue;
grouped.set(sid, (grouped.get(sid)||0)+1);
}
for(const [sid,n] of grouped){
const s = S.byId.get(sid); if(!s) continue;
const [x,y] = toScreen(s.x,s.y), off = 14 * C.node;
for(let i=0;i<Math.min(n,4);i++){
ctx.fillStyle = '#ff5cc8'; ctx.shadowColor = '#ff5cc8'; ctx.shadowBlur = 10;
ctx.beginPath(); ctx.arc(x-off-i*9, y+off, 4.2, 0, 7); ctx.fill(); ctx.shadowBlur = 0;
}
if(n > 4){ ctx.fillStyle = '#ff5cc8'; ctx.font = '700 10px ui-monospace, monospace';
ctx.fillText('+'+(n-4), x-off-36, y+off+3); }
}
}
if(C.fog > 0){
const home = S.me && S.byId.get(S.me.station);
const [hx,hy] = home ? toScreen(home.x,home.y) : [S.W/2,S.H/2];
const R = Math.max(S.W,S.H) * .98;
const fg = ctx.createRadialGradient(hx,hy,Math.max(40,90 * clamp(z,.5,2)),hx,hy,R);
fg.addColorStop(0,'rgba(0,0,0,0)');
fg.addColorStop(.45, `rgba(3,6,10,${C.fog*.45})`);
fg.addColorStop(1, `rgba(3,6,10,${C.fog})`);
ctx.fillStyle = fg; ctx.fillRect(0,0,S.W,S.H);
}
}
function loop(ts){
if(!S.open){ S.raf = 0; return; }
S.raf = requestAnimationFrame(loop);
const dt = Math.min(.05, (ts - S.lastTick)/1000 || 0); S.lastTick = ts;
S.t += dt*(C.speed||0);
const k = 1 - Math.pow(.0016, dt || .016);
const p = [S.cam.x,S.cam.y,S.cam.z];
S.cam.x = lerp(S.cam.x,S.cam.tx,k); S.cam.y = lerp(S.cam.y,S.cam.ty,k); S.cam.z = lerp(S.cam.z,S.cam.tz,k);
const moved = Math.abs(p[0]-S.cam.x) >.03 || Math.abs(p[1]-S.cam.y) >.03 || Math.abs(p[2]-S.cam.z) >.0004;
if(moved || S.dirty || C.speed > 0){
try{ draw(); S.errs = 0; }
catch(e){
if(S.errs++ === 0){ console.error(e); WC.toast('Ошибка отрисовки схемы: '+e.message,'error'); }
if(S.errs > 4){ try{ drawEmpty('Ошибка отрисовки — нажми «Данные»'); }catch(_){} }
}
S.dirty = false;
}
}

/* ══════════ УКАЗАТЕЛЬ ══════════ */
function pick(mx,my){
let best = null, bd = Infinity;
const rad = Math.max(16, 13 * C.node * clamp(S.cam.z,.5,1.7));
for(const s of S.byId.values()){
const [x,y] = toScreen(s.x,s.y);
const d = Math.hypot(x-mx, y-my);
if(d < rad && d < bd){ bd = d; best = s.id; }
}
return best;
}
cv.addEventListener('pointerdown', e => {
if(e.button !== undefined && e.button !== 0) return;
try{ cv.setPointerCapture(e.pointerId); }catch(_){}
S.drag = { x:e.clientX, y:e.clientY, cx:S.cam.tx, cy:S.cam.ty, moved:0, id:e.pointerId };
cv.classList.add('drag');
});
cv.addEventListener('pointermove', e => {
const rect = cv.getBoundingClientRect();
const mx = e.clientX-rect.left, my = e.clientY-rect.top;
if(S.drag && S.drag.id === e.pointerId){
const dx = e.clientX-S.drag.x, dy = e.clientY-S.drag.y;
S.drag.moved = Math.max(S.drag.moved, Math.hypot(dx,dy));
S.cam.tx = S.drag.cx - dx/S.cam.z; S.cam.ty = S.drag.cy - dy/S.cam.z;
S.cam.x = S.cam.tx; S.cam.y = S.cam.ty; S.dirty = true; hideTip(); return;
}
const id = pick(mx,my);
if(id !== S.hover){ S.hover = id; S.dirty = true; }
if(id) showTip(id, e.clientX, e.clientY); else hideTip();
});
function endDrag(e){
if(S.drag && S.drag.id === e.pointerId){
if(S.drag.moved < 6){
const rect = cv.getBoundingClientRect();
const id = pick(e.clientX-rect.left, e.clientY-rect.top);
if(id){ selectStation(id, false); WC.sfx('button.mp3'); } else selectStation(null,false);
}
S.drag = null; cv.classList.remove('drag');
}
}
cv.addEventListener('pointerup', endDrag);
cv.addEventListener('pointercancel', () => { S.drag = null; cv.classList.remove('drag'); });
cv.addEventListener('pointerleave', () => { S.hover = null; hideTip(); S.dirty = true; });
cv.addEventListener('wheel', e => {
e.preventDefault();
const rect = cv.getBoundingClientRect();
const mx = e.clientX-rect.left, my = e.clientY-rect.top;
const [wx,wy] = toWorld(mx,my);
const nz = clamp(S.cam.tz * (e.deltaY < 0 ? 1.13 : .885), .18, 3.2);
S.cam.tz = nz; S.cam.tx = wx-(mx-S.W/2)/nz; S.cam.ty = wy-(my-S.H/2)/nz;
C.zoom = clamp(nz/baseZoom(), .2, 3.2); syncControls(); save(); S.dirty = true;
}, { passive:false });
const touches = new Map();
cv.addEventListener('touchstart', e => { for(const t of e.changedTouches) touches.set(t.identifier,t); }, { passive:true });
cv.addEventListener('touchmove', e => {
for(const t of e.changedTouches) touches.set(t.identifier,t);
if(touches.size === 2){
const [a,b] = [...touches.values()];
const d = Math.hypot(a.clientX-b.clientX, a.clientY-b.clientY);
if(S.pinch){
const nz = clamp(S.cam.tz*(d/S.pinch), .18, 3.2);
S.cam.tz = nz; C.zoom = clamp(nz/baseZoom(), .2, 3.2); syncControls(); save();
}
S.pinch = d; S.drag = null; S.dirty = true; e.preventDefault();
}
}, { passive:false });
cv.addEventListener('touchend', e => { for(const t of e.changedTouches) touches.delete(t.identifier); if(touches.size < 2) S.pinch = null; });
function showTip(id, cx, cy){
const s = S.byId.get(id), tip = $('#map-tip');
const serv = (s.services||[]).map(k => SERV_LABEL[k]||k).join(' · ');
tip.innerHTML = `<b>${WC.esc(s.name)}</b><span>${WC.esc(stLine(s))}${s.faction ? ' · '+WC.esc(s.faction) : ''}</span> ${serv ? `<div style="margin-top:4px;color:#ffd23f;font-size:11px">${WC.esc(serv)}</div>` : ''} <div style="margin-top:3px;font-size:11px;color:#8ea3b0">опасность ${s.danger||0} · радиация ${s.radiation||0}${s.surface?' · поверхность':''}${!s._msk&&C.layout==='msk'?' · вне схемы':''}</div>`;
tip.classList.remove('hidden');
tip.style.left = Math.min(window.innerWidth-tip.offsetWidth-12, cx+16)+'px';
tip.style.top = Math.max(8, cy-tip.offsetHeight-14)+'px';
}
function hideTip(){ $('#map-tip').classList.add('hidden'); }

/* ══════════ ДОСЬЕ ══════════ */
function selectStation(id, fly){
S.sel = id; S.dirty = true;
const box = $('#map-dossier');
if(!id || !S.byId.has(id)){ box.classList.add('hidden'); return; }
const s = S.byId.get(id);
box.classList.remove('hidden');
$('#dos-line').textContent = (s._num ? s._num+' · ' : '') + stLine(s);
$('#dos-line').style.color = stColor(s);
$('#dos-name').textContent = s.name;
$('#dos-tags').innerHTML = (s.services||[]).map(k =>
`<span class="on" style="background:${SERV_COLOR[k]||'#8ea3b0'}">${WC.esc(SERV_LABEL[k]||k)}</span>`).join('')
+ (s.surface ? '<span class="on" style="background:#ff5cc8">поверхность</span>' : '')
+ (!s._msk && C.layout==='msk' ? '<span class="on" style="background:#7f8c99">вне схемы</span>' : '')
+ (S.me && S.me.station === id ? '<span class="on" style="background:#ffd23f">ты здесь</span>' : '');
$('#dos-desc').textContent = s.desc || '';
const dmax = Math.max(1, ...S.data.stations.map(x => x.danger||0));
const rmax = Math.max(1, ...S.data.stations.map(x => x.radiation||0));
$('#dos-danger').style.width = clamp((s.danger||0)/dmax*100,0,100)+'%';
$('#dos-danger-v').textContent = (s.danger||0)+' / '+dmax;
$('#dos-rad').style.width = clamp((s.radiation||0)/rmax*100,0,100)+'%';
$('#dos-rad-v').textContent = (s.radiation||0)+' / '+rmax;
const rows = [['Линия', stLine(s)], ['Фракция', s.faction||'—'],
['Глубина', s.depth != null ? s.depth+' м' : '—'],
['Переходов', String((s.links||[]).length)],
['NPC', (s.npc||[]).length ? (s.npc||[]).join(', ') : '—']];
const here = S.online.filter(p => (p.station||resolveByName(p.location)) === id && (!S.me || p.id !== S.me.id));
if(here.length) rows.push(['Игроки', here.map(p=>p.name).join(', ')]);
$('#dos-kv').innerHTML = rows.map(([k,v]) => `<div><dt>${WC.esc(k)}</dt><dd>${WC.esc(v)}</dd></div>`).join('');
$('#dos-links').innerHTML = (s.links||[]).map(l => {
const o = S.byId.get(l.to); if(!o) return '';
return `<button type="button" data-go="${WC.esc(o.id)}"><i style="background:${stColor(o)}"></i>${WC.esc(o.name)} <em>${l.kind==='tech'?'техтоннель':l.kind==='surface'?'поверхность':'тоннель'}</em></button>`;
}).join('') || '<div style="font-size:12px;color:#8ea3b0">Переходов нет</div>';
const isHere = S.me && S.me.station === id;
$('#dos-go').disabled = isHere || !(S.me && S.me.has_character);
$('#dos-go').textContent = isHere ? 'Ты здесь' : 'Идти сюда';
if(fly) flyTo(id);
}
$('#dos-links').addEventListener('click', e => {
const b = e.target.closest('[data-go]'); if(!b) return;
WC.sfx('button.mp3'); selectStation(b.dataset.go, true);
});
$('#dos-x').onclick = () => selectStation(null,false);
$('#dos-route').onclick = () => { if(S.sel) planRoute(S.sel); };
$('#dos-go').onclick = () => { if(S.sel){ planRoute(S.sel); startWalk(); } };

/* ══════════ МАРШРУТ ══════════ */
function bfs(a,b){
const q = [[a]], seen = new Set([a]);
while(q.length){
const path = q.shift(), last = path[path.length-1];
if(last === b) return path;
const node = S.byId.get(last); if(!node) continue;
for(const n of [...(node._adj||[])].sort((x,y)=>(S.byId.get(x).danger||0)-(S.byId.get(y).danger||0))){
if(seen.has(n)) continue; seen.add(n); q.push([...path,n]);
}
}
return [];
}
function planRoute(to){
const from = S.me && S.me.station;
if(!from){ log('Сначала создай персонажа — /start','warn'); return; }
if(from === to){ log('Ты уже на этой станции','warn'); return; }
const path = bfs(from,to);
if (!path.length){ log('Маршрут не найден: станции не связаны переходами','bad'); WC.toast('Маршрут не найден','warn'); return; }
S.route = path; S.walkIdx = 0; S.dirty = true;
const hops = path.length-1;
const risk = path.slice(1).reduce((a,id)=>a+(S.byId.get(id).danger||0),0);
$('#route-title').textContent = `${S.byId.get(from).name} → ${S.byId.get(to).name}`;
$('#route-meta').textContent = `${hops} переход(ов) · риск ${risk.toFixed(0)} · ${path.slice(1).some(id=>S.byId.get(id).surface)?'выход на поверхность':'под землёй'}`;
$('#route-start').disabled = false; $('#route-clear').disabled = false;
renderChips(); log(`Маршрут проложен: ${hops} переход(ов)`,'ok'); WC.sfx('ding.mp3');
}
function renderChips(){
$('#route-chips').innerHTML = S.route.map((id,i) => {
const s = S.byId.get(id); if(!s) return '';
const cls = i < S.walkIdx ? 'done' : (i === S.walkIdx ? 'now' : '');
return `<span class="chip ${cls}" style="${i>S.walkIdx?`color:${stColor(s)}`:''}"><i></i>${WC.esc(s.name)}</span>`;
}).join('');
$('#route-bar').style.width = (S.route.length > 1 ? S.walkIdx/(S.route.length-1)*100 : 0)+'%';
}
function log(text, cls){
const box = $('#route-log'), d = document.createElement('div');
d.className = cls||''; d.textContent = `${new Date().toLocaleTimeString('ru-RU')} · ${text}`;
box.append(d); box.scrollTop = box.scrollHeight;
while(box.children.length > 60) box.firstChild.remove();
}
function stopWalk(reason){
S.walking = false;
$('#route-start').classList.remove('hidden'); $('#route-stop').classList.add('hidden');
$('#route-start').disabled = !S.route.length;
if(reason) log(reason,'warn');
}
WC.on('map_step', d => {
if(!S.pending) return;
const p = S.pending; S.pending = null;
clearTimeout(p.timer); p.resolve(d || { ok:false, reason:'пустой ответ сервера' });
});
function stepTo(id){
return new Promise(resolve => {
if(S.pending){ clearTimeout(S.pending.timer); S.pending.resolve({ ok:false, reason:'переход прерван' }); }
const timer = setTimeout(() => {
if(S.pending && S.pending.resolve === resolve){ S.pending = null; resolve({ ok:false, reason:'таймаут перехода' }); }
}, 25000);
S.pending = { resolve, timer };
if(!WC.send({ type:'map_move', to:id })){ clearTimeout(timer); S.pending = null; resolve({ ok:false, reason:'нет связи' }); }
});
}
async function startWalk(){
if(S.walking || S.route.length < 2) return;
if(!(S.me && S.me.has_character)){ log('Нет персонажа — /start','bad'); return; }
S.walking = true;
$('#route-start').classList.add('hidden'); $('#route-stop').classList.remove('hidden');
log('Выхожу в тоннель…','ok');
while(S.walking && S.walkIdx < S.route.length-1){
const nextId = S.route[S.walkIdx+1], next = S.byId.get(nextId);
log(`Переход → ${next.name}`);
const res = await stepTo(nextId);
if(!S.walking) break;
if(!res || !res.ok || !res.moved){
const why = (res && (res.reason||res.error)) || 'переход не выполнен';
log('Остановка: '+why,'bad');
const chip = $('#route-chips').children[S.walkIdx+1]; if(chip) chip.classList.add('fail');
WC.toast('Переход остановлен: '+why,'warn'); stopWalk(); return;
}
S.walkIdx++;
const at = res.station || resolveByName(res.location) || nextId;
const idx = S.route.indexOf(at);
if(idx >= 0) S.walkIdx = idx; else S.route.splice(S.walkIdx,0,at);
S.me.station = at;
renderChips(); flyTo(at); selectStation(at,false); WC.sfx('button.mp3');
log('Прибыл: '+(S.byId.get(at)?.name || res.location),'ok');
if(res.alive === false){ log('Персонаж погиб в пути','bad'); stopWalk(); return; }
if(S.walkIdx >= S.route.length-1){
log('Маршрут пройден','ok'); WC.sfx('ding.mp3'); WC.toast('Прибыл на станцию назначения','success');
stopWalk(); return;
}
await new Promise(r => setTimeout(r, 620));
}
stopWalk();
}
$('#route-start').onclick = startWalk;
$('#route-stop').onclick = () => stopWalk('Остановлено игроком');
$('#route-clear').onclick = () => {
stopWalk(); S.route = []; S.walkIdx = 0; S.dirty = true;
$('#route-chips').innerHTML = ''; $('#route-bar').style.width = '0%';
$('#route-title').textContent = 'Маршрут не выбран';
$('#route-meta').textContent = 'кликни станцию на схеме';
$('#route-start').disabled = true; $('#route-clear').disabled = true;
};

/* ══════════ ПОИСК ══════════ */
$('#map-q').addEventListener('input', e => {
const q = norm(e.target.value), box = $('#map-ac');
if(!q || !S.data){ box.classList.add('hidden'); return; }
const hits = S.data.stations.filter(s => norm(s.name).includes(q) || norm(s.id).includes(q)).slice(0,8);
if(!hits.length){ box.classList.add('hidden'); return; }
box.innerHTML = hits.map((s,i) => `<div class="${i?'':'on'}" data-id="${WC.esc(s.id)}"><b>${WC.esc(s.name)}</b><span>${WC.esc(stLine(s))}</span></div>`).join('');
box.classList.remove('hidden');
});
$('#map-ac').addEventListener('mousedown', e => {
const d = e.target.closest('[data-id]'); if(!d) return;
e.preventDefault(); selectStation(d.dataset.id, true);
$('#map-ac').classList.add('hidden'); $('#map-q').value = ''; WC.sfx('button.mp3');
});
$('#map-q').addEventListener('keydown', e => {
if(e.key === 'Enter'){
const first = $('#map-ac').querySelector('[data-id]');
if(first){ selectStation(first.dataset.id, true); $('#map-ac').classList.add('hidden'); e.target.value = ''; }
} else if(e.key === 'Escape'){ $('#map-ac').classList.add('hidden'); e.target.blur(); }
});

/* ══════════ КОНТРОЛЫ ══════════ */
function injectControls(){
if($('#m-layout')) return;
const panel = document.querySelector('.mapx-rail .mpanel');
if(!panel) return;
const style = document.createElement('style');
style.textContent = `.mnote{margin-top:8px;font:500 10.5px ui-monospace,monospace;color:var(--mute); border-top:1px dashed var(--edge);padding-top:7px}`;
document.head.append(style);
const l1 = document.createElement('label'); l1.className = 'mrow';
l1.innerHTML = `<span>Раскладка</span><select id="m-layout"><option value="msk">схема Москвы</option><option value="graph">граф игры</option></select>`;
const l2 = document.createElement('label'); l2.className = 'mrow';
l2.innerHTML = `<span>Разнос узлов</span><input id="m-spread" type="range" min="0.4" max="2.4" step="0.05"><b id="m-spread-v">1.00</b>`;
const note = document.createElement('div'); note.className = 'mnote'; note.id = 'm-note';
panel.append(l1, l2, note);
$('#m-layout').onchange = e => { C.layout = e.target.value; save(); applyLayout(); fit(false); };
$('#m-spread').oninput = e => { C.spread = parseFloat(e.target.value); syncControls(); save(); applyLayout(); };
}
function syncControls(){
$('#m-zoom').value = C.zoom; $('#m-zoom-v').textContent = (+C.zoom).toFixed(2);
$('#m-node').value = C.node; $('#m-node-v').textContent = (+C.node).toFixed(2);
$('#m-line').value = C.line; $('#m-line-v').textContent = C.line;
$('#m-glow').value = C.glow; $('#m-glow-v').textContent = C.glow;
$('#m-fog').value = C.fog; $('#m-fog-v').textContent = (+C.fog).toFixed(2);
$('#m-speed').value = C.speed; $('#m-speed-v').textContent = (+C.speed).toFixed(2);
$('#m-labels').value = C.labels; $('#m-theme').value = C.theme;
root.dataset.theme = C.theme;
['terr','rad','tech','surf','danger','grid','players'].forEach(k => { $('#m-'+k).checked = !!C[k]; });
if($('#m-layout')){ $('#m-layout').value = C.layout; $('#m-spread').value = C.spread;
$('#m-spread-v').textContent = (+C.spread).toFixed(2); }
}
function bindRange(id, key, after){
$(id).addEventListener('input', e => { C[key] = parseFloat(e.target.value); syncControls(); save(); S.dirty = true; if(after) after(); });
}
bindRange('#m-zoom','zoom', () => { S.cam.tz = clamp(baseZoom() * C.zoom, .18, 3.2); });
bindRange('#m-node','node'); bindRange('#m-line','line'); bindRange('#m-glow','glow');
bindRange('#m-fog','fog'); bindRange('#m-speed','speed');
$('#m-labels').onchange = e => { C.labels = e.target.value; save(); S.dirty = true; };
$('#m-theme').onchange = e => { C.theme = e.target.value; syncControls(); save(); S.dirty = true; };
['terr','rad','tech','surf','danger','grid','players'].forEach(k => {
$('#m-'+k).onchange = e => { C[k] = e.target.checked; save(); S.dirty = true; };
});
$('#m-reset').onclick = () => {
Object.assign(C, { zoom:1, node:1, line:7, glow:12, fog:.3, speed:1, labels:'smart', theme:'tunnel',
terr:true, rad:true, tech:true, surf:true, danger:true, grid:false, players:true,
layout:'msk', spread:1 });
syncControls(); save(); applyLayout(); fit(false); WC.toast('Вид схемы сброшен','success');
};
$('#m-export').onclick = () => {
try{ draw(); }catch(e){}
const out = document.createElement('canvas');
out.width = cv.width; out.height = cv.height + 60 * S.dpr;
const c2 = out.getContext('2d');
c2.fillStyle = theme().bg; c2.fillRect(0,0,out.width,out.height);
c2.drawImage(cv, 0, 52 * S.dpr);
c2.fillStyle = '#ffd23f'; c2.font = `700 ${18*S.dpr}px ui-monospace, monospace`;
c2.fillText('44 WHITE CURTAIN · СХЕМА ЛИНИИ D6', 18 * S.dpr, 32 * S.dpr);
c2.fillStyle = theme().mute; c2.font = `${12*S.dpr}px ui-monospace, monospace`;
c2.fillText(new Date().toLocaleString('ru-RU')+' · '+(S.data?.stations.length||0)+' станций', 18 * S.dpr, out.height-14 * S.dpr);
const a = document.createElement('a');
a.download = 'metro44-scheme.png'; a.href = out.toDataURL('image/png'); a.click();
WC.toast('Схема сохранена в PNG','success');
};
$('#map-fit').onclick = () => { fit(false); WC.sfx('button.mp3'); };
$('#map-here').onclick = () => { if(S.me && S.me.station){ flyTo(S.me.station, 1.4); selectStation(S.me.station,false); } };
$('#map-reload').onclick = () => load(true);
$('#map-close').onclick = close;

/* ══════════ ОТКРЫТИЕ ══════════ */
function open(){
if(S.open) return;
S.open = true; root.classList.remove('hidden');
document.body.style.overflow = 'hidden';
injectControls(); syncControls();
requestAnimationFrame(() => {
resize(); fit(true);
S.lastTick = performance.now();
if(!S.raf) S.raf = requestAnimationFrame(loop);
if(!S.data) load(false); else { applyLayout(); fit(false); }
});
if(!S.ro && window.ResizeObserver){
S.ro = new ResizeObserver(() => { if(S.open){ resize(); S.dirty = true; } });
S.ro.observe(cv);
}
WC.sfx('ding.mp3');
}
function close(){
if(!S.open) return;
stopWalk(); S.open = false; root.classList.add('hidden');
if(S.raf){ cancelAnimationFrame(S.raf); S.raf = 0; }
hideTip(); document.body.style.overflow = '';
}
$('#map-btn').onclick = () => S.open ? close() : open();
document.querySelectorAll('[data-open-map]').forEach(b => b.onclick = open);
window.addEventListener('resize', () => { if(S.open){ resize(); fit(false); } });
document.addEventListener('keydown', e => {
const typing = ['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName);
if(e.key === 'Escape' && S.open){ close(); return; }
if(!S.open){
if(!typing && !e.ctrlKey && !e.metaKey && ['m','M','ь','Ь'].includes(e.key)){ e.preventDefault(); open(); }
return;
}
if(typing) return;
const pan = 90/S.cam.z;
if(['ArrowLeft','a','ф'].includes(e.key)){ S.cam.tx -= pan;  e.preventDefault(); }
if(['ArrowRight','d','в'].includes(e.key)){ S.cam.tx += pan; e.preventDefault(); }
if(['ArrowUp','w','ц'].includes(e.key)){ S.cam.ty -= pan; e.preventDefault(); }
if(['ArrowDown','s','ы'].includes(e.key)){ S.cam.ty += pan; e.preventDefault(); }
if(e.key === '+' || e.key === '='){ S.cam.tz = clamp(S.cam.tz * 1.15,.18,3.2); }
if(e.key === '-' || e.key === '_'){ S.cam.tz = clamp(S.cam.tz*.87,.18,3.2); }
if(['f','F','а','А'].includes(e.key)) fit(false);
if(['h','H','р','Р'].includes(e.key) && S.me?.station) flyTo(S.me.station, 1.4);
if(e.key === 'Enter' && S.sel) planRoute(S.sel);
S.dirty = true;
});

/* ══════════ СВЯЗЬ С ИГРОЙ ══════════ */
WC.on('world', w => {
S.online = (w.online||[]).map(p => ({ id:p.id, name:p.name, location:p.location,
station:p.station || resolveByName(p.location) }));
const loc = w.me && w.me.location;
if(loc && S.data){
const id = resolveByName(loc);
if(id && (!S.me || S.me.station !== id)){
S.me = Object.assign({}, S.me, { station:id, location:loc, has_character:true });
if(S.open){ flyTo(id); if(S.sel === id) selectStation(id,false); }
}
}
S.dirty = true;
});
WC.on('map_data', d => {
if(d && d.ok && Array.isArray(d.stations)){
S.data = d; S.byId = new Map(d.stations.map(s=>[s.id,s]));
for(const s of S.data.stations) s._adj = (s.links||[]).map(l=>l.to).filter(id=>S.byId.has(id));
applyLayout(); S.dirty = true;
}
});
WC.on('ready', () => { if(S.open) load(false); });
WC.on('close-map', close);
window.WCMAP = { open, close, planRoute, selectStation };
})();