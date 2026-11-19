/* 44 WHITE CURTAIN — СХЕМА МЕТРО · справочник линии D6
   Разметка: реальная сетка Московского метрополитена, южный сектор, конец 2015.
   Параметры станций: живые данные игры (/api/map). Переходов нет — только справка. */
(() => {
'use strict';
if (window.__WCMAP__) return;
const WC = window.WC; if (!WC) { console.warn('[map] нет шины WC'); return; }
window.__WCMAP__ = true;

/* ═══════════ ЛИНИИ ═══════════ */
const L = {
  '6':  { num:'6',   name:'Калужско-Рижская',           color:'#ff8a1f', north:'12 станций до Медведково' },
  '9':  { num:'9',   name:'Серпуховско-Тимирязевская',  color:'#9aa5ad', north:'13 станций до Алтуфьево' },
  '2':  { num:'2',   name:'Замоскворецкая',             color:'#2fbf4f', north:'11 станций до Речного вокзала' },
  '5':  { num:'5',   name:'Кольцевая',                  color:'#a1662f', north:'' },
  '11A':{ num:'11А', name:'Каховская',                  color:'#37d6c8', north:'' },
  '12': { num:'12',  name:'Бутовская',                  color:'#7fa8c9', north:'' }
};
const SLUG = {'калужско-рижская':'6','серпуховско-тимирязевская':'9','замоскворецкая':'2',
  'кольцевая':'5','каховская':'11A','бутовская':'12'};

/* ═══════════ СХЕМА: колонки, ряды, дуга кольца ═══════════ */
const COLX = {A:150, B:560, C:1060, K1:690, K2:820, K3:950};
const ROW0 = 260, ROWH = 70;
const ARC = {x0:40, y0:112, cx:610, cy:212, x1:1180, y1:112};
const MAPW = 1280, MAPH = 1660;
const arcY = x => { const t=(x-ARC.x0)/(ARC.x1-ARC.x0), u=1-t;
  return u*u*ARC.y0 + 2*t*u*ARC.cy + t*t*ARC.y1; };
const rowY = r => ROW0 + r*ROWH;
const colX = (c,r) => c==='A' ? (r==='ring'?COLX.A:(r<=14?COLX.A:COLX.A-(r-14)*22)) : COLX[c];

const TOPO = [
  ['октябрьская_кольцо','Октябрьская','5','A','ring'],
  ['добрынинская','Добрынинская','5','B','ring'],
  ['павелецкая_кольцо','Павелецкая','5','C','ring'],

  ['октябрьская_рыжая','Октябрьская','6','A',0],
  ['шаболовская','Шаболовская','6','A',1],
  ['ленинский_проспект','Ленинский проспект','6','A',2],
  ['академическая','Академическая','6','A',3],
  ['профсоюзная','Профсоюзная','6','A',4],
  ['новые_черемушки','Новые Черёмушки','6','A',5],
  ['калужская','Калужская','6','A',6],
  ['беляево','Беляево','6','A',7],
  ['коньково','Коньково','6','A',8],
  ['теплый_стан','Тёплый Стан','6','A',9],
  ['ясенево','Ясенево','6','A',10],
  ['новоясеневская','Новоясеневская','6','A',11],

  ['битцевский_парк','Битцевский парк','12','A',12],
  ['лесопарковая','Лесопарковая','12','A',13],
  ['улица_старокачаловская','Улица Старокачаловская','12','A',14],
  ['скобелевская','Улица Скобелевская','12','A',15],
  ['бульвар_адмирала_ушакова','Бульвар Адмирала Ушакова','12','A',16],
  ['улица_горчакова','Улица Горчакова','12','A',17],
  ['бунинская_аллея','Бунинская аллея','12','A',18],

  ['серпуховская','Серпуховская','9','B',0],
  ['тульская','Тульская','9','B',1],
  ['нагатинская','Нагатинская','9','B',3],
  ['нагорная','Нагорная','9','B',4],
  ['нахимовский_проспект','Нахимовский проспект','9','B',5],
  ['севастопольская','Севастопольская','9','B',6],
  ['чертановская','Чертановская','9','B',7],
  ['южная','Южная','9','B',8],
  ['пражская','Пражская','9','B',9],
  ['ул_янгеля','Ул. Академика Янгеля','9','B',10],
  ['аннино','Аннино','9','B',11],
  ['бульвар_дмитрия_донского','Бульвар Дмитрия Донского','9','B',14],

  ['павелецкая_зеленая','Павелецкая','2','C',0],
  ['автозаводская','Автозаводская','2','C',1],
  ['технопарк','Технопарк','2','C',2],
  ['коломенская','Коломенская','2','C',3],
  ['каширская_зеленая','Каширская','2','C',6],
  ['кантемировская','Кантемировская','2','C',7],
  ['царицыно','Царицыно','2','C',8],
  ['орехово','Орехово','2','C',9],
  ['домодедовская','Домодедовская','2','C',10],

  ['каховская','Каховская','11A','K1',6],
  ['варшавская','Варшавская','11A','K2',6],
  ['каширская_бирюза','Каширская','11A','K3',6]
];
const CHAINS = {
  '6':['октябрьская_рыжая','шаболовская','ленинский_проспект','академическая','профсоюзная','новые_черемушки',
       'калужская','беляево','коньково','теплый_стан','ясенево','новоясеневская'],
  '9':['серпуховская','тульская','нагатинская','нагорная','нахимовский_проспект','севастопольская',
       'чертановская','южная','пражская','ул_янгеля','аннино','бульвар_дмитрия_донского'],
  '2':['павелецкая_зеленая','автозаводская','технопарк','коломенская','каширская_зеленая',
       'кантемировская','царицыно','орехово','домодедовская'],
  '5':['октябрьская_кольцо','добрынинская','павелецкая_кольцо'],
  '11A':['каховская','варшавская','каширская_бирюза'],
  '12':['битцевский_парк','лесопарковая','улица_старокачаловская','скобелевская',
        'бульвар_адмирала_ушакова','улица_горчакова','бунинская_аллея']
};
const XF = [
  ['октябрьская_кольцо','октябрьская_рыжая'], ['добрынинская','серпуховская'],
  ['павелецкая_кольцо','павелецкая_зеленая'], ['севастопольская','каховская'],
  ['каширская_бирюза','каширская_зеленая'], ['новоясеневская','битцевский_парк'],
  ['бульвар_дмитрия_донского','улица_старокачаловская']
];
const OPENED = {'битцевский_парк':'27.02.2014','лесопарковая':'27.02.2014','технопарк':'28.12.2015'};
const GHOST = {'улица_старокачаловская':'Реальный пересадочный узел между Бульваром Дмитрия Донского и бутовской линией. В игре станции нет — её роль отдана Бульвару Дмитрия Донского.'};
const TC = {'стартовая':'#66ff99','торговая':'#ffd23f','жилая':'#7fa8c9','обычная':'#a8bac6',
  'опасная':'#ff8a3d','разрушенная':'#ff6b5c','на_поверхности':'#ff7ad3'};
const TL = {'на_поверхности':'поверхность','разрушенная':'разрушена'};
const DL = ['безопасно','небольшая','опасно','очень опасно','смертельно','экстремально'];
const FILTERS = [['торговая','Торговля'],['жилая','Жилые'],['опасная','Опасные'],['разрушенная','Разрушенные'],
  ['на_поверхности','Поверхность'],['blocked','Закрытые'],['hostile','Враждебные'],['npc','С NPC']];

const NODES = TOPO.map(([id,name,lk,c,r])=>({
  id,name,lk,col:c,row:r,x:colX(c,r),y:r==='ring'?arcY(colX(c,r)):rowY(r),
  d:null,ghost:!!GHOST[id],inGame:!GHOST[id]
}));
const BY = new Map(NODES.map(n=>[n.id,n]));
const ADJ = new Map(NODES.map(n=>[n.id,new Set()]));
for(const k in CHAINS){const a=CHAINS[k];for(let i=0;i<a.length-1;i++){ADJ.get(a[i]).add(a[i+1]);ADJ.get(a[i+1]).add(a[i]);}}
for(const [a,b] of XF){ADJ.get(a).add(b);ADJ.get(b).add(a);}

/* ═══════════ КОНТРАСТ ═══════════ */
function lum(hex){
  const v=hex.replace('#',''); const c=[0,2,4].map(i=>parseInt(v.substr(i,2),16)/255)
    .map(x=>x<=.03928?x/12.92:Math.pow((x+.055)/1.055,2.4));
  return .2126*c[0]+.7152*c[1]+.0722*c[2];
}
const onColor = hex => lum(hex) > .34 ? '#0a1016' : '#fff3e2';
const INK='#ece4d3', MUTE='#a8bac6', DIM='#8b9daa', VOID='#07090b';

/* ═══════════ СТИЛИ ═══════════ */
const CSS = `
#wcmap.wcm{position:fixed!important;inset:0!important;z-index:9000!important;display:flex!important;
 align-items:center;justify-content:center;padding:clamp(12px,2.2vh,28px) clamp(12px,2.2vw,32px);margin:0;
 width:100vw;height:100vh;overflow:hidden;font:14px/1.5 "Segoe UI",Roboto,Inter,system-ui,sans-serif;
 --void:#07090b;--surf:#10151a;--panel:#161d24;--over:#1c252e;--edge:#2b3844;--edge2:#202b36;
 --ink:#ece4d3;--mute:#a8bac6;--dim:#8b9daa;--amber:#ffb02e;--amber-d:#c97f10;--gold:#ffd23f;
 --rad:#66ff99;--rust:#ff6b5c;--steel:#6cb8ff;--anom:#ff7ad3;--track:#0a0e12}
#wcmap.wcm[data-theme=radio]{--void:#050b07;--surf:#0c1610;--panel:#122019;--over:#182b21;--edge:#254034;--edge2:#1b3126;
 --ink:#e4f6d8;--mute:#a9cdb4;--dim:#8fb49b;--amber:#9dff3d;--amber-d:#4f8f3a;--gold:#d4ff4d;--steel:#8fe0ad;--track:#08120c}
#wcmap.wcm[data-theme=night]{--void:#05070d;--surf:#0c1119;--panel:#141c29;--over:#1b2536;--edge:#26334c;--edge2:#1c2536;
 --ink:#e4eaf7;--mute:#a7b4cd;--dim:#8d9bb5;--amber:#7aa2ff;--amber-d:#3f5a9a;--gold:#6fe3ff;--steel:#9dc0ff;--track:#080c14}
#wcmap.wcm.hidden{display:none!important}
#wcmap.wcm *{box-sizing:border-box}
#wcmap .scrim{position:absolute;inset:0;background:rgba(7,11,16,.32);
 backdrop-filter:blur(2px) saturate(1.05);-webkit-backdrop-filter:blur(2px) saturate(1.05)}
#wcmap .win{position:relative;display:flex;flex-direction:column;overflow:hidden;width:min(1600px,100%);height:min(920px,100%);
 border-radius:16px;border:1px solid #35495c;background:linear-gradient(180deg,var(--surf),var(--void) 72%);color:var(--ink);
 box-shadow:0 40px 110px rgba(0,0,0,.74),inset 0 0 0 1px rgba(255,255,255,.05),inset 0 1px 0 rgba(255,255,255,.1)}
#wcmap .win::before{content:"";position:absolute;inset:0 0 auto;height:2px;z-index:12;
 background:linear-gradient(90deg,#a1662f,#ff8a1f,#ffd23f,#2fbf4f,#37d6c8,#7fa8c9)}

#wcmap .head{flex:0 0 auto;display:flex;align-items:center;gap:15px;padding:12px 17px;position:relative;z-index:10;
 background:linear-gradient(180deg,var(--over),var(--surf));border-bottom:1px solid var(--edge)}
#wcmap .mark{flex:0 0 auto;width:42px;height:42px;display:grid;place-items:center;border-radius:11px;
 font:800 16px/1 ui-monospace,"Cascadia Mono",Consolas,monospace;color:#14100a;
 background:linear-gradient(145deg,#ffe27a,var(--amber));box-shadow:0 5px 16px rgba(255,176,46,.32),inset 0 0 0 1px rgba(255,255,255,.26)}
#wcmap .ttl{flex:0 0 auto;display:flex;flex-direction:column;justify-content:center;min-width:0}
#wcmap .ttl b{display:block;font:800 15px/1.1 ui-monospace,"Cascadia Mono",Consolas,monospace;letter-spacing:2.6px;color:#fff;white-space:nowrap}
#wcmap .ttl span{display:block;margin-top:5px;font-size:11px;line-height:1.2;color:var(--dim);white-space:nowrap}
#wcmap .vr{flex:0 0 auto;width:1px;height:34px;background:linear-gradient(180deg,transparent,var(--edge),transparent)}
#wcmap .stats{flex:0 0 auto;display:flex;gap:7px}
#wcmap .stats div{display:flex;flex-direction:column;align-items:center;min-width:58px;padding:5px 11px;border-radius:9px;
 background:var(--void);border:1px solid var(--edge2)}
#wcmap .stats b{font:800 16px/1 ui-monospace,monospace;color:var(--gold)}
#wcmap .stats span{margin-top:4px;font-size:9px;letter-spacing:.9px;text-transform:uppercase;color:var(--dim)}
#wcmap .find{position:relative;flex:1 1 auto;max-width:300px;min-width:110px}
#wcmap .find input{width:100%;padding:9px 12px 9px 33px;border-radius:9px;border:1px solid var(--edge);
 background:var(--void);color:var(--ink);font:inherit}
#wcmap .find input::placeholder{color:var(--dim)}
#wcmap .find input:focus{outline:none;border-color:var(--amber);box-shadow:0 0 0 3px rgba(255,176,46,.16)}
#wcmap .find>svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);opacity:.6;pointer-events:none}
#wcmap .ac{position:absolute;top:calc(100% + 6px);left:0;right:0;max-height:274px;overflow:auto;z-index:40;
 background:var(--panel);border:1px solid var(--edge);border-radius:9px;box-shadow:0 18px 42px rgba(0,0,0,.7)}
#wcmap .ac.hidden{display:none}
#wcmap .ac button{display:flex;width:100%;gap:9px;align-items:center;padding:8px 12px;background:none;border:0;
 border-bottom:1px solid var(--edge2);color:var(--ink);font:inherit;text-align:left;cursor:pointer}
#wcmap .ac button:last-child{border-bottom:0}
#wcmap .ac button:hover,#wcmap .ac button:focus{background:var(--over);outline:none}
#wcmap .ac i{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
#wcmap .ac b{font-weight:600}
#wcmap .ac em{margin-left:auto;font-size:10.5px;color:var(--dim);font-style:normal}
#wcmap .tools{flex:0 0 auto;margin-left:auto;display:flex;gap:6px;align-items:center}

#wcmap .b{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:9px 13px;border-radius:9px;
 border:1px solid #3d5266;cursor:pointer;color:var(--ink);background:linear-gradient(180deg,var(--over),var(--panel));
 font:600 12px/1 inherit;white-space:nowrap;transition:border-color .14s,background .14s,color .14s;
 box-shadow:0 2px 0 rgba(4,7,10,.8),inset 0 1px 0 rgba(255,255,255,.08)}
#wcmap .b:hover:not(:disabled){border-color:var(--amber);color:#fff;background:linear-gradient(180deg,#26333f,var(--over))}
#wcmap .b:active:not(:disabled){box-shadow:0 1px 0 rgba(4,7,10,.8)}
#wcmap .b:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
#wcmap .b:disabled{opacity:.42;cursor:not-allowed}
#wcmap .b.on{border-color:var(--amber);color:var(--amber);background:linear-gradient(180deg,#33240f,#211705)}
#wcmap .b.sm{padding:6px 9px;font-size:11px}
#wcmap .b.ico{padding:8px 12px;font-size:15px;font-weight:700}
#wcmap .x{flex:0 0 auto;width:38px;height:38px;display:grid;place-items:center;border-radius:9px;border:1px solid #3d5266;
 background:linear-gradient(180deg,var(--over),var(--panel));color:var(--mute);cursor:pointer;font-size:18px;line-height:1;
 transition:.14s;box-shadow:0 2px 0 rgba(4,7,10,.8)}
#wcmap .x:hover{border-color:var(--rust);color:#fff;background:linear-gradient(180deg,#a3453a,#662721)}
#wcmap .x:focus-visible{outline:2px solid var(--gold);outline-offset:2px}

#wcmap .chips{flex:0 0 auto;display:flex;align-items:center;gap:6px;padding:8px 17px;overflow-x:auto;position:relative;z-index:9;
 background:var(--void);border-bottom:1px solid var(--edge2)}
#wcmap .chips>b{flex:0 0 auto;margin-right:3px;font:700 9.5px ui-monospace,monospace;letter-spacing:1.4px;color:var(--dim);text-transform:uppercase}
#wcmap .chip{display:inline-flex;align-items:center;gap:6px;flex:0 0 auto;padding:6px 11px;border-radius:99px;border:1px solid #3d5266;
 background:linear-gradient(180deg,var(--panel),var(--surf));color:var(--mute);font:600 11px/1 inherit;cursor:pointer;transition:.14s}
#wcmap .chip i{width:8px;height:8px;border-radius:50%;flex:0 0 auto}
#wcmap .chip:hover{border-color:var(--amber);color:var(--ink)}
#wcmap .chip.on{border-color:var(--amber);color:var(--amber);background:linear-gradient(180deg,#33240f,#211705)}
#wcmap .chip:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
#wcmap .csep{flex:0 0 auto;width:1px;height:19px;background:var(--edge);margin:0 3px}

#wcmap .body{flex:1 1 auto;display:flex;min-height:0}
#wcmap .rail{flex:0 0 300px;width:300px;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;
 background:linear-gradient(180deg,var(--surf),var(--void));border-right:1px solid var(--edge)}
#wcmap .card{background:var(--panel);border:1px solid var(--edge);border-radius:11px;padding:11px;box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
#wcmap .card>h4{display:flex;align-items:center;gap:7px;margin:0 0 10px;font:700 10px ui-monospace,monospace;letter-spacing:1.5px;
 color:var(--dim);text-transform:uppercase}
#wcmap .card>h4 em{margin-left:auto;font-style:normal;font-size:10px;color:var(--amber);font-weight:700}
#wcmap .ctl{display:flex;align-items:center;gap:9px;margin-bottom:9px;font-size:11.5px;color:var(--mute)}
#wcmap .ctl>span{flex:0 0 76px}
#wcmap .ctl>b{flex:0 0 36px;text-align:right;font:700 11px ui-monospace,monospace;color:var(--gold)}
#wcmap input[type=range]{flex:1 1 auto;-webkit-appearance:none;appearance:none;height:5px;border-radius:3px;outline:none;cursor:pointer;
 background:linear-gradient(90deg,var(--amber),var(--amber-d))}
#wcmap input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:15px;height:15px;border-radius:50%;background:var(--gold);
 border:2px solid var(--void);cursor:pointer}
#wcmap input[type=range]::-moz-range-thumb{width:13px;height:13px;border-radius:50%;background:var(--gold);border:2px solid var(--void);cursor:pointer}
#wcmap input[type=range]:focus-visible{outline:2px solid var(--gold);outline-offset:3px}
#wcmap select{flex:1 1 auto;padding:5px 8px;border-radius:7px;border:1px solid var(--edge);background:var(--void);color:var(--ink);
 font:inherit;font-size:11.5px;cursor:pointer}
#wcmap select:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
#wcmap select option{background:#161d24;color:#ece4d3}
#wcmap .sw{display:flex;align-items:center;gap:8px;padding:5px 0;font-size:11.5px;color:var(--mute);cursor:pointer}
#wcmap .sw input{position:absolute;opacity:0;width:0;height:0}
#wcmap .sw i{flex:0 0 auto;width:33px;height:18px;border-radius:99px;background:var(--void);border:1px solid var(--edge);position:relative;transition:.16s}
#wcmap .sw i::after{content:"";position:absolute;left:2px;top:2px;width:12px;height:12px;border-radius:50%;background:var(--dim);transition:.16s}
#wcmap .sw input:checked+i{background:rgba(255,176,46,.22);border-color:var(--amber)}
#wcmap .sw input:checked+i::after{left:17px;background:var(--amber)}
#wcmap .sw input:focus-visible+i{outline:2px solid var(--gold);outline-offset:2px}
#wcmap .g2{display:grid;grid-template-columns:1fr 1fr;gap:6px}
#wcmap .g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;margin-top:8px}
#wcmap .mini{width:100%;height:250px;border-radius:9px;border:1px solid var(--edge);background:var(--void);overflow:hidden;cursor:crosshair;display:block}
#wcmap .mini svg{width:100%;height:100%;display:block}
#wcmap .lrow{display:flex;align-items:center;gap:9px;padding:6px 7px;margin:0 -7px;border-radius:8px;font-size:12px;color:var(--ink);
 cursor:pointer;border:1px solid transparent;transition:.14s}
#wcmap .lrow:hover{background:var(--over);border-color:var(--edge)}
#wcmap .lrow.on{background:var(--over);border-color:var(--amber)}
#wcmap .lrow.off{opacity:.45}
#wcmap .lrow u{flex:0 0 auto;min-width:30px;height:20px;padding:0 6px;border-radius:6px;text-decoration:none;display:grid;place-items:center;
 font:800 10.5px ui-monospace,monospace}
#wcmap .lrow span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#wcmap .lrow em{margin-left:auto;font:600 11px ui-monospace,monospace;color:var(--dim);font-style:normal}
#wcmap .keys{display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:11px;color:var(--mute)}
#wcmap .keys span{display:flex;align-items:center;gap:7px}
#wcmap .keys b{flex:0 0 auto;width:11px;height:11px;border-radius:50%;background:#2a3a48}
#wcmap .note{font-size:11px;color:var(--dim);line-height:1.55}
#wcmap .note b{color:var(--gold)}

#wcmap .stage{flex:1 1 auto;position:relative;min-width:0;overflow:hidden;background:var(--void)}
#wcmap .atmo{position:absolute;inset:0;pointer-events:none;
 background:radial-gradient(78% 52% at 50% -6%,rgba(255,176,46,.12),transparent 62%),
 radial-gradient(60% 46% at 10% 106%,rgba(127,168,201,.09),transparent 62%),
 radial-gradient(56% 44% at 94% 98%,rgba(47,191,79,.07),transparent 62%)}
#wcmap .grain{position:absolute;inset:0;pointer-events:none;mix-blend-mode:overlay;
 background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3'/></filter><rect width='150' height='150' filter='url(%23n)' opacity='.5'/></svg>")}
#wcmap .scan{position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(0,0,0,.26) 0 1px,transparent 1px 3px)}
#wcmap .vig{position:absolute;inset:0;pointer-events:none;background:radial-gradient(126% 96% at 50% 44%,transparent 48%,rgba(0,0,0,.66))}
#wcmap .svg{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab;touch-action:none}
#wcmap .svg.drag{cursor:grabbing}
#wcmap .svg text{user-select:none;pointer-events:none}
#wcmap .svg g[data-id]{cursor:pointer;outline:none}
#wcmap .svg g[data-id] .halo{opacity:0;transition:opacity .14s}
#wcmap .svg g[data-id]:hover .halo{opacity:.26}
#wcmap .svg g[data-id] .core{transition:stroke-width .14s}
#wcmap .svg g[data-id]:hover .core{stroke-width:3.6}
#wcmap .svg g[data-id]:focus-visible .hit{stroke:#ffd23f;stroke-width:2;stroke-dasharray:3 3}

#wcmap .dock{position:absolute;z-index:50;width:288px;max-height:min(492px,80%);overflow-y:auto;padding:13px;border-radius:12px;
 border:1px solid #445d72;background:linear-gradient(180deg,var(--over),var(--surf));
 box-shadow:0 26px 66px rgba(0,0,0,.82),inset 0 1px 0 rgba(255,255,255,.09)}
#wcmap .dock.hidden{display:none}
#wcmap .dh{display:flex;align-items:flex-start;gap:9px;margin-bottom:5px}
#wcmap .dh i{flex:0 0 auto;width:13px;height:13px;border-radius:50%;margin-top:4px}
#wcmap .dh h3{flex:1 1 auto;min-width:0;margin:0;font:800 15px/1.25 ui-monospace,monospace;color:#fff}
#wcmap .dh button{flex:0 0 auto;width:22px;height:22px;border-radius:6px;border:1px solid var(--edge);background:var(--surf);
 color:var(--mute);cursor:pointer;font-size:12px;line-height:1}
#wcmap .dh button:hover{color:#fff;border-color:var(--rust);background:#5c2620}
#wcmap .dl{display:flex;align-items:center;gap:7px;margin:0 0 9px;padding-left:22px;font:600 10.5px ui-monospace,monospace;color:var(--mute)}
#wcmap .dl u{min-width:26px;height:17px;padding:0 5px;border-radius:5px;text-decoration:none;display:inline-grid;place-items:center;
 font:800 9.5px ui-monospace,monospace}
#wcmap .warn{margin:0 0 9px;padding:7px 9px;border-radius:8px;border:1px solid rgba(255,176,46,.45);background:rgba(255,176,46,.1);
 font-size:10.5px;line-height:1.5;color:#ffcb6b}
#wcmap .tags{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:9px}
#wcmap .tags span{padding:3px 8px;border-radius:99px;border:1px solid var(--edge);background:var(--void);font:600 9.5px ui-monospace,monospace;color:var(--mute)}
#wcmap .desc{margin:0 0 9px;padding-left:9px;border-left:2px solid var(--edge);font-size:11.5px;color:#c2cfd8}
#wcmap .meter{display:grid;grid-template-columns:1fr auto;gap:3px 8px;margin-bottom:8px;font-size:10.5px;color:var(--mute)}
#wcmap .meter div{grid-column:1/-1;height:6px;border-radius:3px;background:var(--void);border:1px solid var(--edge);overflow:hidden}
#wcmap .meter i{display:block;height:100%;background:linear-gradient(90deg,#66ff99,#ffd23f,#ff6b5c)}
#wcmap .kv{margin:0;font-size:11.5px}
#wcmap .kv div{display:flex;justify-content:space-between;gap:10px;padding:4px 0;border-top:1px dashed var(--edge)}
#wcmap .kv dt{color:var(--mute)}
#wcmap .kv dd{margin:0;font:600 11.5px ui-monospace,monospace;text-align:right;color:var(--ink)}
#wcmap .sec{margin:10px 0 5px;font:700 9.5px ui-monospace,monospace;letter-spacing:1.3px;color:var(--dim);text-transform:uppercase}
#wcmap .links{display:flex;flex-direction:column;gap:4px}
#wcmap .links button{display:flex;align-items:center;gap:7px;padding:6px 9px;border-radius:7px;border:1px solid var(--edge);
 background:var(--void);color:var(--ink);font:600 11.5px inherit;text-align:left;cursor:pointer;transition:.14s}
#wcmap .links button:hover{border-color:var(--amber);background:var(--over)}
#wcmap .links i{flex:0 0 auto;width:8px;height:8px;border-radius:50%}
#wcmap .links em{margin-left:auto;font:500 9.5px ui-monospace,monospace;color:var(--dim);font-style:normal}
#wcmap .npc{display:flex;flex-direction:column;gap:3px}
#wcmap .npc span{display:flex;align-items:center;gap:7px;padding:5px 9px;border-radius:7px;background:var(--void);
 border:1px solid var(--edge2);font-size:11.5px;color:var(--ink)}
#wcmap .npc span::before{content:"◈";color:var(--steel);font-size:10px}
#wcmap .empty{font-size:11.5px;color:var(--dim)}

#wcmap .foot{flex:0 0 auto;display:flex;align-items:center;gap:12px;padding:9px 17px;position:relative;z-index:10;
 background:linear-gradient(180deg,var(--surf),var(--over));border-top:1px solid var(--edge)}
#wcmap .foot>span{font-size:11px;color:var(--dim);flex:0 0 auto}
#wcmap .foot>b{font:700 12px ui-monospace,monospace;color:var(--gold);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#wcmap .log{margin-left:auto;max-width:44%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:500 11px ui-monospace,monospace;color:var(--dim)}
#wcmap .log.ok{color:var(--rad)}#wcmap .log.bad{color:var(--rust)}#wcmap .log.warn{color:var(--amber)}
#wcmap .hint{position:absolute;left:14px;bottom:12px;z-index:6;padding:5px 10px;border-radius:8px;border:1px solid var(--edge);
 background:rgba(8,13,19,.9);font:500 10.5px ui-monospace,monospace;color:var(--mute);pointer-events:none}
#wcmap .zoom{position:absolute;right:14px;bottom:12px;z-index:6;display:flex;gap:5px}
#wcmap .banner{position:absolute;left:14px;top:14px;z-index:7;padding:7px 11px;border-radius:9px;border:1px solid rgba(255,107,92,.5);
 background:rgba(30,15,13,.94);font:600 11px ui-monospace,monospace;color:#ffb3aa}
#wcmap .banner.hidden{display:none}
#wcmap .over{position:absolute;inset:0;z-index:60;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:13px;
 padding:24px;background:rgba(6,10,14,.93);color:var(--mute);font:600 12px ui-monospace,monospace;text-align:center}
#wcmap .over.hidden{display:none}
#wcmap .dots{display:flex;gap:6px}
#wcmap .dots i{width:9px;height:9px;border-radius:50%;background:var(--amber);opacity:.55}
#wcmap .dots i:nth-child(2){opacity:.8}#wcmap .dots i:nth-child(3){opacity:1}

#wcmap .rail,#wcmap .dock,#wcmap .ac,#wcmap .chips{scrollbar-width:thin;scrollbar-color:var(--amber-d) var(--track)}
#wcmap .rail::-webkit-scrollbar,#wcmap .dock::-webkit-scrollbar,#wcmap .ac::-webkit-scrollbar,#wcmap .chips::-webkit-scrollbar{width:10px;height:10px}
#wcmap .rail::-webkit-scrollbar-track,#wcmap .dock::-webkit-scrollbar-track,#wcmap .ac::-webkit-scrollbar-track,#wcmap .chips::-webkit-scrollbar-track{
 background:var(--track);border-left:1px solid var(--edge2)}
#wcmap .rail::-webkit-scrollbar-thumb,#wcmap .dock::-webkit-scrollbar-thumb,#wcmap .ac::-webkit-scrollbar-thumb,#wcmap .chips::-webkit-scrollbar-thumb{
 border:2px solid var(--track);border-radius:6px;background:linear-gradient(180deg,var(--amber),var(--amber-d))}
#wcmap .rail::-webkit-scrollbar-thumb:hover,#wcmap .dock::-webkit-scrollbar-thumb:hover,#wcmap .ac::-webkit-scrollbar-thumb:hover{
 background:linear-gradient(180deg,var(--gold),var(--amber))}
@media(max-width:1400px){#wcmap .stats{display:none}}
@media(max-width:1040px){
 #wcmap.wcm{padding:6px}
 #wcmap .win{width:100%;height:100%;border-radius:12px}
 #wcmap .body{flex-direction:column-reverse}
 #wcmap .rail{flex:0 0 auto;width:auto;max-height:42vh;border-right:0;border-top:1px solid var(--edge)}
 #wcmap .find{max-width:none}#wcmap .hint,#wcmap .vr,#wcmap .mini{display:none}
 #wcmap .ttl span{display:none}#wcmap .log{display:none}
}
`;
(function(){ let s=document.getElementById('wcm-css');
  if(!s){ s=document.createElement('style'); s.id='wcm-css'; document.head.appendChild(s); } s.textContent=CSS; })();

/* ═══════════ УТИЛИТЫ ═══════════ */
const NS='http://www.w3.org/2000/svg';
const sv=(t,a)=>{const n=document.createElementNS(NS,t);for(const k in a)n.setAttribute(k,a[k]);return n;};
const el=(t,c,x)=>{const n=document.createElement(t);if(c)n.className=c;if(x!=null)n.innerHTML=x;return n;};
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const nz=s=>String(s||'').toLowerCase().replace(/ё/g,'е').replace(/[^a-zа-я0-9]+/g,'');
const cl=(v,a,b)=>Math.max(a,Math.min(b,v));
const sfx=f=>{try{WC.sfx&&WC.sfx(f);}catch(_){}};
const toast=(t,k)=>{try{WC.toast&&WC.toast(t,k);}catch(_){}};

/* ═══════════ КАРКАС ═══════════ */
let HOST=document.getElementById('wcmap');
if(!HOST){HOST=el('div');HOST.id='wcmap';document.body.appendChild(HOST);}
HOST.className='wcm hidden';HOST.setAttribute('aria-hidden','true');
HOST.innerHTML=`
<div class="scrim"></div>
<div class="win" role="dialog" aria-modal="true" aria-label="Схема метро">
 <header class="head">
  <div class="mark">D6</div>
  <div class="ttl"><b>СХЕМА МЕТРО</b><span data-r="sub">справочник · реальная сетка, конец 2015</span></div>
  <div class="vr"></div>
  <div class="stats">
   <div><b data-r="sN">45</b><span>станций</span></div>
   <div><b data-r="sL">6</b><span>линий</span></div>
   <div><b data-r="sO">0</b><span>в сети</span></div>
  </div>
  <div class="find">
   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a8bac6" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>
   <input data-r="q" type="text" placeholder="Поиск станции…" autocomplete="off" aria-label="Поиск станции">
   <div class="ac hidden" data-r="ac"></div>
  </div>
  <div class="tools">
   <button class="b" data-r="here" type="button">⌖ Я здесь</button>
   <button class="b" data-r="fit" type="button">⤢ Вписать</button>
   <button class="b" data-r="reload" type="button">⟳ Данные</button>
   <button class="b on" data-r="mute" type="button" aria-pressed="true">🔊</button>
   <button class="x" data-r="close" type="button" aria-label="Закрыть">✕</button>
  </div>
 </header>
 <div class="chips" data-r="chips"><b>Показать</b></div>
 <div class="body">
  <aside class="rail">
   <div class="card"><h4>Пульт схемы <em data-r="zv">100%</em></h4>
    <label class="ctl"><span>Масштаб</span><input data-r="kZoom" type="range" min="30" max="360" step="1"><b data-r="vZoom">1.00</b></label>
    <label class="ctl"><span>Узлы</span><input data-r="kNode" type="range" min="0.6" max="1.9" step="0.05"><b data-r="vNode">1.00</b></label>
    <label class="ctl"><span>Линии</span><input data-r="kLine" type="range" min="3" max="15" step="1"><b data-r="vLine">7</b></label>
    <label class="ctl"><span>Свечение</span><input data-r="kGlow" type="range" min="0" max="22" step="1"><b data-r="vGlow">10</b></label>
    <label class="ctl"><span>Атмосфера</span><input data-r="kAtmo" type="range" min="0" max="100" step="1"><b data-r="vAtmo">65</b></label>
    <label class="ctl"><span>Подписи</span><select data-r="kLbl"><option value="all">все</option><option value="key">ключевые</option><option value="none">нет</option></select></label>
    <label class="ctl"><span>Тема</span><select data-r="kTheme"><option value="tunnel">тоннель</option><option value="radio">радио</option><option value="night">ночь</option></select></label>
    <div class="g2">
     <label class="sw"><input data-r="kPlayers" type="checkbox"><i></i>Игроки</label>
     <label class="sw"><input data-r="kDanger" type="checkbox"><i></i>Опасность</label>
     <label class="sw"><input data-r="kGuides" type="checkbox"><i></i>Направляющие</label>
     <label class="sw"><input data-r="kGame" type="checkbox"><i></i>Связи игры</label>
     <label class="sw"><input data-r="kFocus" type="checkbox"><i></i>Фокус</label>
     <label class="sw"><input data-r="kGrain" type="checkbox"><i></i>Зерно</label>
    </div>
    <div class="g3">
     <button class="b sm" data-r="kReset" type="button">Сброс</button>
     <button class="b sm" data-r="kRand" type="button">Случайно</button>
     <button class="b sm" data-r="kPng" type="button">PNG</button>
    </div>
    <div class="g2" style="margin-top:5px">
     <button class="b sm" data-r="kSvg" type="button">Скачать SVG</button>
     <button class="b sm" data-r="kCopy" type="button">Копировать</button>
    </div>
   </div>
   <div class="card"><h4>Обзор <em data-r="mp">100%</em></h4>
    <div class="mini" data-r="mini"><svg data-r="miniSvg" xmlns="${NS}"></svg></div>
    <div class="g2" style="margin-top:8px">
     <button class="b sm" data-r="jTop" type="button">↑ Кольцо</button>
     <button class="b sm" data-r="jEnd" type="button">↓ Бутово</button>
    </div>
   </div>
   <div class="card"><h4>Линии <em>клик — изолировать</em></h4><div data-r="legend"></div></div>
   <div class="card"><h4>Обозначения</h4><div class="keys" data-r="keys"></div></div>
   <div class="card"><h4>Как ходить</h4><div class="note">Схема справочная. Переходы — в терминале:
    <b>/move</b> или меню → «Переместиться». Выносливость, события и доступ считает игра.</div></div>
  </aside>
  <div class="stage" data-r="stage">
   <div class="atmo" data-r="atmo"></div>
   <svg class="svg" data-r="svg" xmlns="${NS}"></svg>
   <div class="grain" data-r="grain"></div><div class="scan" data-r="scan"></div><div class="vig" data-r="vig"></div>
   <div class="banner hidden" data-r="banner"></div>
   <div class="hint">колесо — масштаб · тяни — обзор · клик по станции — справка</div>
   <div class="zoom"><button class="b ico" data-r="zin" type="button" aria-label="Приблизить">+</button>
    <button class="b ico" data-r="zout" type="button" aria-label="Отдалить">−</button></div>
   <div class="dock hidden" data-r="dock"></div>
   <div class="over hidden" data-r="over"></div>
  </div>
 </div>
 <footer class="foot"><span>Ты на станции:</span><b data-r="at">—</b><span class="log" data-r="log"></span></footer>
</div>`;
const R={};HOST.querySelectorAll('[data-r]').forEach(n=>R[n.dataset.r]=n);
const WIN=HOST.querySelector('.win');

FILTERS.forEach(([k,t])=>{
  const c=TC[k]||(k==='blocked'?'#6b7a87':k==='hostile'?'#ff6b5c':'#6cb8ff');
  const b=el('button','chip',`<i style="background:${c}"></i>${t}`);b.type='button';b.dataset.f=k;
  b.onclick=()=>{S.filters.has(k)?S.filters.delete(k):S.filters.add(k);b.classList.toggle('on',S.filters.has(k));draw();};
  R.chips.append(b);
});
R.chips.append(el('div','csep'));
const clr=el('button','chip','✕ Сбросить');clr.type='button';
clr.onclick=()=>{S.filters.clear();S.query='';S.iso=null;R.q.value='';
  R.chips.querySelectorAll('[data-f]').forEach(b=>b.classList.remove('on'));legend();draw();};
R.chips.append(clr);

/* ═══════════ СОСТОЯНИЕ ═══════════ */
const DEF={node:1,line:7,glow:10,atmo:65,lbl:'all',theme:'tunnel',
  players:true,danger:true,guides:false,game:false,focus:true,grain:true};
const S={open:false,loaded:false,loading:false,offline:false,me:null,online:[],sel:null,iso:null,
  filters:new Set(),query:'',drag:null,cfg:Object.assign({},DEF)};
try{Object.assign(S.cfg,JSON.parse(localStorage.getItem('wc.map.v4')||'{}'));}catch(_){}
const save=()=>{try{localStorage.setItem('wc.map.v4',JSON.stringify(S.cfg));}catch(_){}};
const cam={x:MAPW/2,y:420,z:1}, goal=Object.assign({},cam);
let easeRaf=0, ro=null, miniDown=false;

/* ═══════════ КАМЕРА ═══════════ */
function clampGoal(){
  goal.z=cl(goal.z,.3,3.6);
  const w=MAPW/goal.z,hh=MAPH/goal.z;
  goal.x=cl(goal.x,w/2-MAPW*.18,MAPW-w/2+MAPW*.18);
  goal.y=cl(goal.y,hh/2-MAPH*.08,MAPH-hh/2+MAPH*.08);
}
function view(){
  const w=MAPW/cam.z,hh=MAPH/cam.z;
  R.svg.setAttribute('viewBox',`${cam.x-w/2} ${cam.y-hh/2} ${w} ${hh}`);
  R.svg.setAttribute('preserveAspectRatio','xMidYMid meet');
  const p=Math.round(cam.z*100)+'%';R.zv.textContent=p;R.mp.textContent=p;R.vZoom.textContent=cam.z.toFixed(2);
  if(document.activeElement!==R.kZoom)R.kZoom.value=String(Math.round(cam.z*100));
  miniFrame();
}
function stopEase(){if(easeRaf){cancelAnimationFrame(easeRaf);easeRaf=0;}}
function ease(){
  cam.x+=(goal.x-cam.x)*.26;cam.y+=(goal.y-cam.y)*.26;cam.z+=(goal.z-cam.z)*.26;
  if(Math.abs(goal.x-cam.x)<.5&&Math.abs(goal.y-cam.y)<.5&&Math.abs(goal.z-cam.z)<.002){
    cam.x=goal.x;cam.y=goal.y;cam.z=goal.z;view();easeRaf=0;return;}
  view();easeRaf=requestAnimationFrame(ease);
}
function setCam(x,y,z,now){
  goal.x=x;goal.y=y;goal.z=z;clampGoal();
  if(now){stopEase();cam.x=goal.x;cam.y=goal.y;cam.z=goal.z;view();}
  else if(!easeRaf)easeRaf=requestAnimationFrame(ease);
}
function fitWidth(now){
  const r=R.stage.getBoundingClientRect();
  const z=cl((r.width||MAPW)/MAPW*.97,.3,3.6), hh=MAPH/z;
  setCam(MAPW/2,Math.min(hh/2,430),z,now);
}
function fitAll(){
  const r=R.stage.getBoundingClientRect();
  const z=cl(Math.min((r.width||MAPW)/MAPW,(r.height||MAPH)/MAPH)*.97,.3,3.6);
  setCam(MAPW/2,MAPH/2,z,false);
}
function fly(id,now){const n=BY.get(id);if(n)setCam(n.x,n.y,Math.max(goal.z,1.35),now);}
function resolve(loc){if(!loc)return null;const k=nz(loc);
  let f=NODES.find(n=>nz(n.id)===k||nz(n.name)===k);
  if(!f&&k.length>3)f=NODES.find(n=>nz(n.name).includes(k));return f?f.id:null;}
function ptr(e){const r=R.svg.getBoundingClientRect(),vb=R.svg.viewBox.baseVal;
  const s=Math.max(vb.width/r.width,vb.height/r.height);
  return {s,x:vb.x+(e.clientX-r.left)*s-(r.width*s-vb.width)/2,y:vb.y+(e.clientY-r.top)*s-(r.height*s-vb.height)/2};}

/* ═══════════ ДАННЫЕ ═══════════ */
async function load(){
  if(S.loading)return;S.loading=true;
  R.over.innerHTML='<div class="dots"><i></i><i></i><i></i></div><span>Читаю станции метро…</span>';
  R.over.classList.remove('hidden');
  let r;try{r=await WC.api('/api/map');}catch(e){r={ok:false,status:0,d:{error:String(e&&e.message||e)}};}
  S.loading=false;
  const d=r&&r.d, ok=!!(r&&r.ok&&d&&d.ok&&Array.isArray(d.stations)&&d.stations.length);
  if(ok){
    const ix=new Map(d.stations.map(s=>[s.id,s]));
    for(const n of NODES){const f=ix.get(n.id);n.d=f||null;if(f)n.inGame=true;}
    S.me=d.me||null;S.online=(d.online||[]).map(p=>({id:p.id,name:p.name,station:p.station,location:p.location}));
    S.offline=false;R.banner.classList.add('hidden');
    R.sN.textContent=String(NODES.filter(n=>n.d).length);
    log('Параметры загружены: '+NODES.filter(n=>n.d).length+' станций','ok');
  }else{
    S.offline=true;
    const e=(d&&(d.error||d.reason))||(r&&r.status===401?'требуется вход в терминал':'сервер недоступен');
    R.banner.textContent='⚠ '+e+' — показана только разметка';R.banner.classList.remove('hidden');
    log('Параметры недоступны: '+e,'bad');
  }
  R.sO.textContent=String(S.online.length);
  R.at.textContent=S.me&&S.me.station?(BY.get(S.me.station)||{}).name||S.me.location||'—':'персонаж не создан';
  R.over.classList.add('hidden');S.loaded=true;legend();draw();mini();fitWidth(true);
}
const types=n=>(n.d&&(n.d.types||(n.d.type?[n.d.type]:[])))||[];
const dang=n=>cl(Number(n.d&&n.d.danger)||0,0,5);
const surf=n=>!!(n.d&&(n.d.surface||types(n).includes('на_поверхности')));
const shut=n=>!!(n.d&&n.d.blocked);
const npcs=n=>(n.d&&n.d.npc)||[];
const tcol=n=>{for(const t of types(n))if(TC[t])return TC[t];return '#0a1016';};
const gline=n=>n.d?(SLUG[String(n.d.line||'').toLowerCase()]||null):null;
const isKey=n=>n.lk==='5'||n.id===S.sel||(S.me&&n.id===S.me.station)||XF.some(p=>p.includes(n.id))||!n.inGame||dang(n)>=4||shut(n);
function pass(n){
  if(S.iso&&n.lk!==S.iso)return false;
  if(!n.inGame)return S.filters.size===0&&!S.query;
  if(S.query&&!(nz(n.name).includes(S.query)||nz(n.id).includes(S.query)))return false;
  for(const f of S.filters){
    if(f==='blocked'){if(!shut(n))return false;}
    else if(f==='hostile'){if(!(n.d&&n.d.hostile))return false;}
    else if(f==='npc'){if(!npcs(n).length)return false;}
    else if(!types(n).includes(f))return false;
  }
  return true;
}
function alpha(n){
  if(!pass(n))return .12;
  if(S.cfg.focus&&S.sel&&S.sel!==n.id&&!ADJ.get(S.sel).has(n.id))return .45;
  return 1;
}
function wrap(t){
  const W=150,words=String(t||'').split(/\s+/),out=[];let cur='';
  for(const w of words){const s=(cur?cur+' ':'')+w;
    if(s.length*6.9<=W||!cur)cur=s;else{out.push(cur);cur=w;}}
  if(cur)out.push(cur);return out.slice(0,3);
}

/* ═══════════ ОТРИСОВКА ═══════════ */
function draw(){
  const g=R.svg;while(g.firstChild)g.removeChild(g.firstChild);
  const C=S.cfg,NW=+C.line,NR=10*+C.node,GL=+C.glow;
  const defs=sv('defs',{});
  if(GL>0){const f=sv('filter',{id:'wgl',x:'-70%',y:'-70%',width:'240%',height:'240%'});
    f.appendChild(sv('feGaussianBlur',{stdDeviation:(GL/3).toFixed(2),result:'b'}));
    const m=sv('feMerge',{});m.append(sv('feMergeNode',{in:'b'}),sv('feMergeNode',{in:'SourceGraphic'}));
    f.appendChild(m);defs.appendChild(f);}
  for(const k in L){
    const rg=sv('radialGradient',{id:'nd'+k,cx:'34%',cy:'27%',r:'80%'});
    rg.append(sv('stop',{offset:'0%','stop-color':'#ffffff','stop-opacity':'.8'}),
      sv('stop',{offset:'44%','stop-color':L[k].color}),
      sv('stop',{offset:'100%','stop-color':L[k].color,'stop-opacity':'.74'}));defs.appendChild(rg);
  }
  g.appendChild(defs);
  const lay={};for(const k of ['guide','seg','xf','game','ann','node','ppl','lbl']){lay[k]=sv('g',{});g.appendChild(lay[k]);}
  const glow=GL>0?'url(#wgl)':'';

  if(C.guides){
    for(let r=0;r<=18;r++)lay.guide.appendChild(sv('line',{x1:24,y1:rowY(r),x2:MAPW-24,y2:rowY(r),
      stroke:'#ffffff','stroke-width':.6,opacity:.055}));
    for(const [c,k] of [['A','6'],['B','9'],['C','2']])
      lay.guide.appendChild(sv('line',{x1:COLX[c],y1:100,x2:COLX[c],y2:MAPH-60,stroke:L[k].color,
        'stroke-width':.9,opacity:.12,'stroke-dasharray':'2 10'}));
  }

  /* кольцо */
  lay.seg.appendChild(sv('path',{d:`M${ARC.x0},${ARC.y0} Q${ARC.cx},${ARC.cy} ${ARC.x1},${ARC.y1}`,fill:'none',
    stroke:L['5'].color,'stroke-width':NW,'stroke-linecap':'round',opacity:.24}));
  const r5=CHAINS['5'];
  for(let i=0;i<r5.length-1;i++){
    const a=BY.get(r5[i]),b=BY.get(r5[i+1]),al=Math.min(alpha(a),alpha(b));
    const mx=(a.x+b.x)/2,my=arcY(mx)+4;
    lay.seg.appendChild(sv('path',{d:`M${a.x},${a.y} Q${mx},${my} ${b.x},${b.y}`,fill:'none',
      stroke:L['5'].color,'stroke-width':NW,'stroke-linecap':'round',opacity:al*.95,filter:glow}));
  }
  for(const d of ['M40,112 q-24,-28 -20,-58','M1180,112 q24,-28 20,-58'])
    lay.seg.appendChild(sv('path',{d,fill:'none',stroke:L['5'].color,'stroke-width':Math.max(2,NW-2),
      'stroke-linecap':'round',opacity:.32,'stroke-dasharray':'8 8'}));

  /* перегоны */
  for(const lk in CHAINS){
    if(lk==='5')continue;
    const ids=CHAINS[lk];
    for(let i=0;i<ids.length-1;i++){
      const a=BY.get(ids[i]),b=BY.get(ids[i+1]),al=Math.min(alpha(a),alpha(b));
      lay.seg.appendChild(sv('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:L[lk].color,'stroke-width':NW+6,
        'stroke-linecap':'round',opacity:al*.12}));
      lay.seg.appendChild(sv('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:L[lk].color,'stroke-width':NW,
        'stroke-linecap':'round',opacity:al*.95,filter:glow}));
    }
  }
  /* переходы */
  for(const [ai,bi] of XF){
    const a=BY.get(ai),b=BY.get(bi),al=Math.min(alpha(a),alpha(b));
    lay.xf.appendChild(sv('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:'#dbe4ea','stroke-width':NW+4,'stroke-linecap':'round',opacity:al*.92}));
    lay.xf.appendChild(sv('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:'#0a1017','stroke-width':Math.max(1.4,NW-3.2),'stroke-linecap':'round',opacity:al}));
  }
  /* связи игры, которых нет в реальной сетке */
  if(C.game){
    for(const n of NODES){
      if(!n.d||!Array.isArray(n.d.connections))continue;
      for(const cid of n.d.connections){
        const o=BY.get(cid);if(!o||n.id>=cid||ADJ.get(n.id).has(cid))continue;
        const mx=(n.x+o.x)/2+110,my=(n.y+o.y)/2-30;
        lay.game.appendChild(sv('path',{d:`M${n.x},${n.y} Q${mx},${my} ${o.x},${o.y}`,fill:'none',stroke:'#ffb02e',
          'stroke-width':3,'stroke-dasharray':'11 8','stroke-linecap':'round',opacity:.9}));
        const t=sv('text',{x:mx-52,y:my-6,'font-size':'11','font-family':'ui-monospace, monospace',fill:'#ffcb6b','font-weight':'700',
          'paint-order':'stroke',stroke:VOID,'stroke-width':3.2,'stroke-linejoin':'round'});
        t.textContent='связь игры';lay.game.appendChild(t);
      }
    }
  }

  /* аннотации */
  const ann=(x,y,txt,col,size,anchor,weight)=>{
    const t=sv('text',{x,y,fill:col,'font-size':size||11,'font-family':'ui-monospace, monospace',
      'font-weight':weight||600,'text-anchor':anchor||'start','letter-spacing':'.5',
      'paint-order':'stroke',stroke:VOID,'stroke-width':3,'stroke-linejoin':'round'});
    t.textContent=txt;lay.ann.appendChild(t);return t;};
  for(const [lk,c] of [['6','A'],['9','B'],['2','C']]){
    const x=COLX[c],ln=L[lk],bw=Math.max(28,ln.num.length*10+14),ry=arcY(x);
    lay.ann.appendChild(sv('line',{x1:x,y1:ry-14,x2:x,y2:96,stroke:ln.color,'stroke-width':3,opacity:.34,
      'stroke-dasharray':'7 7','stroke-linecap':'round'}));
    lay.ann.appendChild(sv('rect',{x:x-bw/2,y:26,width:bw,height:21,rx:6,fill:ln.color}));
    const nt=sv('text',{x,y:41.5,'text-anchor':'middle',fill:onColor(ln.color),'font-size':'12','font-weight':'800',
      'font-family':'ui-monospace, monospace'});nt.textContent=ln.num;lay.ann.appendChild(nt);
    ann(x,64,ln.name.toUpperCase(),ln.color,11,'middle',700);
    ann(x,80,'↑ '+ln.north+' — вне игры',DIM,9.5,'middle',500);
  }
  ann(700,206,'⑤ КОЛЬЦЕВАЯ · ЮЖНАЯ ДУГА','#d9a066',11.5,'start',700);
  ann(700,224,'3 из 12 станций · остальные 9 севернее',DIM,9.5,'start',500);
  ann(820,rowY(6)-42,'⑪А КАХОВСКАЯ · ЧЕЛНОК',L['11A'].color,11,'middle',700);
  const bp=BY.get('битцевский_парк');
  lay.ann.appendChild(sv('rect',{x:210,y:bp.y-46,width:32,height:20,rx:6,fill:L['12'].color}));
  const b12=sv('text',{x:226,y:bp.y-31.5,'text-anchor':'middle',fill:onColor(L['12'].color),'font-size':'11','font-weight':'800',
    'font-family':'ui-monospace, monospace'});b12.textContent='12';lay.ann.appendChild(b12);
  ann(250,bp.y-31.5,'БУТОВСКАЯ',L['12'].color,11,'start',700);
  ann(210,bp.y-13,'переход открыт 27.02.2014',DIM,9.5,'start',500);
  const tp=BY.get('технопарк');ann(tp.x+26,tp.y+4,'открыт 28.12.2015',DIM,9.5,'start',500);
  const dm=BY.get('домодедовская');
  lay.ann.appendChild(sv('line',{x1:dm.x,y1:dm.y+56,x2:dm.x,y2:dm.y+100,stroke:L['2'].color,'stroke-width':3,
    opacity:.3,'stroke-dasharray':'7 7','stroke-linecap':'round'}));
  ann(dm.x,dm.y+116,'↓ дальше вне игры',DIM,9.5,'middle',500);
  const ba=BY.get('бунинская_аллея');ann(ba.x,ba.y+62,'ЮЗ · ЮЖНОЕ БУТОВО',DIM,9.5,'middle',500);

  /* узлы */
  const here=S.me&&S.me.station;
  for(const n of NODES){
    const al=alpha(n),me=n.id===here,sel=n.id===S.sel,dg=dang(n),ln=L[n.lk];
    const gg=sv('g',{tabindex:'0',role:'button','aria-label':n.name+' — '+ln.name,opacity:al});
    gg.dataset.id=n.id;
    gg.appendChild(sv('circle',{class:'halo',cx:n.x,cy:n.y,r:NR+12,fill:ln.color}));
    gg.appendChild(sv('circle',{class:'hit',cx:n.x,cy:n.y,r:NR+14,fill:'transparent'}));
    if(S.cfg.danger&&dg>=1&&n.inGame)
      gg.appendChild(sv('circle',{cx:n.x,cy:n.y,r:NR+10+dg*5.5,fill:'#ff4d3d',opacity:.035+dg*.02}));
    if(dg>=3&&n.inGame)gg.appendChild(sv('circle',{cx:n.x,cy:n.y,r:NR+7.5,fill:'none',stroke:'#ff6b5c','stroke-width':1.6,opacity:.5,'stroke-dasharray':'3 4'}));
    if(surf(n))gg.appendChild(sv('circle',{cx:n.x,cy:n.y,r:NR+4.5,fill:'none',stroke:'#ff7ad3','stroke-width':1.7,opacity:.92}));
    if(sel)gg.appendChild(sv('circle',{cx:n.x,cy:n.y,r:NR+12,fill:'none',stroke:'#ffb02e','stroke-width':2,'stroke-dasharray':'5 5'}));
    if(me)gg.appendChild(sv('circle',{cx:n.x,cy:n.y,r:NR+9.5,fill:'none',stroke:'#ffd23f','stroke-width':2.6,filter:glow}));
    gg.appendChild(sv('circle',{cx:n.x,cy:n.y,r:NR+3.5,fill:'#060a0e',opacity:.94}));
    if(n.ghost){
      gg.appendChild(sv('circle',{class:'core',cx:n.x,cy:n.y,r:NR,fill:'#1a242e',stroke:'#9fb0bc','stroke-width':2.2,'stroke-dasharray':'4 3'}));
    }else{
      gg.appendChild(sv('circle',{class:'core',cx:n.x,cy:n.y,r:NR,fill:shut(n)?'#55636f':'url(#nd'+n.lk+')',
        stroke:shut(n)?'#8b9aa6':(S.offline?'#0a1016':tcol(n)),'stroke-width':2.5}));
      if(!shut(n))gg.appendChild(sv('circle',{cx:n.x-NR*.3,cy:n.y-NR*.34,r:NR*.28,fill:'#ffffff',opacity:.38}));
    }
    if(shut(n)){const t=sv('text',{x:n.x,y:n.y+4.5,'text-anchor':'middle',fill:'#f2f6f9','font-size':'13','font-weight':'800',
      'font-family':'ui-monospace, monospace'});t.textContent='×';gg.appendChild(t);}
    else if(npcs(n).length){const t=sv('text',{x:n.x,y:n.y+4,'text-anchor':'middle',fill:'#0a1016','font-size':'10','font-weight':'800',
      'font-family':'ui-monospace, monospace'});t.textContent='◈';gg.appendChild(t);}
    lay.node.appendChild(gg);

    const show=C.lbl==='all'||(C.lbl==='key'&&isKey(n));
    if(show){
      const lines=wrap(n.name);
      const t=sv('text',{x:n.x,y:n.y+NR+16,'text-anchor':'middle',
        fill:n.ghost?'#b7c5cf':(me?'#ffd23f':(sel?'#ffb02e':'#dbe5ec')),
        'font-size':'14','font-weight':me||sel?'700':'600',
        'font-family':'ui-monospace, "Cascadia Mono", Consolas, monospace',opacity:al,
        'paint-order':'stroke',stroke:VOID,'stroke-width':3.4,'stroke-linejoin':'round'});
      lines.forEach((s,i)=>{const ts=sv('tspan',{x:n.x,dy:i===0?0:14});ts.textContent=s;t.appendChild(ts);});
      lay.lbl.appendChild(t);
      if(n.ghost){
        const u=sv('text',{x:n.x,y:n.y+NR+16+lines.length*14,'text-anchor':'middle',fill:'#ffcb6b','font-size':'9.5',
          'font-weight':'700','font-family':'ui-monospace, monospace',opacity:al,
          'paint-order':'stroke',stroke:VOID,'stroke-width':3,'stroke-linejoin':'round'});
        u.textContent='нет в игре';lay.lbl.appendChild(u);
      }
    }
  }
  /* игроки */
  if(C.players){
    const at=new Map();
    for(const p of S.online){if(S.me&&p.id===S.me.id)continue;
      const sid=p.station||resolve(p.location);if(sid&&BY.has(sid))at.set(sid,(at.get(sid)||0)+1);}
    for(const [sid,c] of at){const n=BY.get(sid);
      lay.ppl.appendChild(sv('circle',{cx:n.x+NR+5,cy:n.y-NR-5,r:9,fill:'#4aa8ff',stroke:'#05080b','stroke-width':2}));
      const t=sv('text',{x:n.x+NR+5,y:n.y-NR-1.2,'text-anchor':'middle',fill:'#04121c','font-size':'10.5','font-weight':'800',
        'font-family':'ui-monospace, monospace'});t.textContent=String(c);lay.ppl.appendChild(t);}
  }
  view();
}

/* ═══════════ МИНИ-КАРТА ═══════════ */
function mini(){
  const m=R.miniSvg;while(m.firstChild)m.removeChild(m.firstChild);
  m.setAttribute('viewBox',`0 0 ${MAPW} ${MAPH}`);
  m.appendChild(sv('rect',{x:0,y:0,width:MAPW,height:MAPH,fill:'#070d12'}));
  m.appendChild(sv('path',{d:`M${ARC.x0},${ARC.y0} Q${ARC.cx},${ARC.cy} ${ARC.x1},${ARC.y1}`,fill:'none',
    stroke:L['5'].color,'stroke-width':13,opacity:.7}));
  for(const lk in CHAINS){
    if(lk==='5')continue;
    const pts=CHAINS[lk].map(i=>{const n=BY.get(i);return n.x+','+n.y;}).join(' ');
    m.appendChild(sv('polyline',{points:pts,fill:'none',stroke:L[lk].color,'stroke-width':13,opacity:.8,
      'stroke-linecap':'round','stroke-linejoin':'round'}));
  }
  for(const [a,b] of XF){const p=BY.get(a),q=BY.get(b);
    m.appendChild(sv('line',{x1:p.x,y1:p.y,x2:q.x,y2:q.y,stroke:'#dbe4ea','stroke-width':9,opacity:.6}));}
  const here=S.me&&S.me.station;
  if(here&&BY.has(here)){const n=BY.get(here);m.appendChild(sv('circle',{cx:n.x,cy:n.y,r:28,fill:'#ffd23f'}));}
  m.appendChild(sv('rect',{id:'wmf',fill:'rgba(255,255,255,.08)',stroke:'#ffffff','stroke-width':9,opacity:.9}));
  miniFrame();
}
function miniFrame(){const f=R.miniSvg.querySelector('#wmf');if(!f)return;
  const w=MAPW/cam.z,hh=MAPH/cam.z;
  f.setAttribute('x',cam.x-w/2);f.setAttribute('y',cam.y-hh/2);f.setAttribute('width',w);f.setAttribute('height',hh);}
function miniAt(e){const r=R.mini.getBoundingClientRect();if(!r.width||!r.height)return;
  const s=Math.max(MAPW/r.width,MAPH/r.height);
  setCam((e.clientX-r.left)*s-(r.width*s-MAPW)/2,(e.clientY-r.top)*s-(r.height*s-MAPH)/2,goal.z,true);}
R.mini.addEventListener('pointerdown',e=>{miniDown=true;miniAt(e);try{R.mini.setPointerCapture(e.pointerId);}catch(_){}});
R.mini.addEventListener('pointermove',e=>{if(miniDown)miniAt(e);});
const mUp=e=>{miniDown=false;try{R.mini.releasePointerCapture(e.pointerId);}catch(_){}};
R.mini.addEventListener('pointerup',mUp);R.mini.addEventListener('pointercancel',mUp);

/* ═══════════ ЛЕГЕНДА ═══════════ */
function legend(){
  R.legend.innerHTML='';
  for(const k of ['5','6','9','2','11A','12']){
    const c=NODES.filter(n=>n.lk===k&&n.inGame).length;
    const row=el('div','lrow'+(S.iso===k?' on':(S.iso?' off':'')),
      `<u style="background:${L[k].color};color:${onColor(L[k].color)}">${esc(L[k].num)}</u>`+
      `<span>${esc(L[k].name)}</span><em>${c}</em>`);
    row.onclick=()=>{S.iso=S.iso===k?null:k;legend();draw();sfx('button.mp3');};
    R.legend.append(row);
  }
  R.keys.innerHTML=Object.keys(TC).map(k=>`<span><b style="box-shadow:0 0 0 2.2px ${TC[k]}"></b>${esc(TL[k]||k)}</span>`).join('')
    +'<span><b style="background:#55636f"></b>закрыта</span><span><b style="box-shadow:0 0 0 2.2px #ffd23f"></b>ты здесь</span>'
    +'<span><b style="background:#4aa8ff"></b>игроки</span><span><b style="box-shadow:0 0 0 2.2px #6cb8ff"></b>◈ NPC</span>'
    +'<span><b style="background:#1a242e;box-shadow:0 0 0 2px #9fb0bc"></b>нет в игре</span>';
}

/* ═══════════ СПРАВКА ═══════════ */
function neighbors(n){
  const out=[];
  for(const lk in CHAINS){const a=CHAINS[lk],i=a.indexOf(n.id);if(i<0)continue;
    if(i>0)out.push({n:BY.get(a[i-1]),k:'перегон'});
    if(i<a.length-1)out.push({n:BY.get(a[i+1]),k:'перегон'});}
  for(const [a,b] of XF){if(a===n.id)out.push({n:BY.get(b),k:'переход'});else if(b===n.id)out.push({n:BY.get(a),k:'переход'});}
  return out.filter(x=>x.n);
}
function openDock(id,ev){
  const n=BY.get(id);if(!n)return;S.sel=id;draw();
  const ln=L[n.lk],d=n.d,gl=gline(n),me=S.me&&S.me.station===n.id;
  const tags=types(n).map(t=>{const c=TC[t]||'#a8bac6';return `<span style="border-color:${c}80;color:${c}">${esc(TL[t]||t)}</span>`;});
  if(d){if(d.blocked)tags.push('<span style="border-color:#ff6b5c80;color:#ff9d92">закрыта</span>');
    if(d.faction_lock)tags.push('<span style="border-color:#ff6b5c80;color:#ff9d92">территория фракции</span>');
    if(d.hostile)tags.push('<span style="border-color:#ff6b5c80;color:#ff9d92">враждебная</span>');
    if(d.ruined)tags.push('<span style="border-color:#ff8a3d80;color:#ffb066">разрушена</span>');}
  if(n.ghost)tags.push('<span style="border-color:#ffb02e80;color:#ffcb6b">нет в игре</span>');
  if(me)tags.push('<span style="border-color:#ffd23f;color:#ffd23f">ты здесь</span>');
  const ppl=S.online.filter(p=>(p.station||resolve(p.location))===n.id&&(!S.me||p.id!==S.me.id));
  const rows=[];
  if(d&&d.faction)rows.push(['Фракция',d.faction_name||d.faction]);
  rows.push(['Соседей',String(neighbors(n).length)]);
  if(d&&d.transfer){const t=BY.get(d.transfer);rows.push(['Переход на',t?t.name:d.transfer]);}
  if(d&&d.tunnel)rows.push(['Техтоннель',d.tunnel_name||d.tunnel]);
  if(OPENED[n.id])rows.push(['Открыта',OPENED[n.id]]);
  if(ppl.length)rows.push(['Игроки',ppl.map(p=>p.name).join(', ')]);
  const dg=dang(n),nb=neighbors(n);
  R.dock.innerHTML=`
   <div class="dh"><i style="background:${ln.color}"></i><h3>${esc(n.name)}</h3>
    <button type="button" data-a="x" aria-label="Закрыть">✕</button></div>
   <div class="dl"><u style="background:${ln.color};color:${onColor(ln.color)}">${esc(ln.num)}</u>${esc(ln.name)}</div>
   ${gl&&gl!==n.lk?`<div class="warn">На схеме — линия ${esc(ln.num)}. В данных игры записана в ${esc(L[gl].num)} «${esc(L[gl].name)}».</div>`:''}
   ${n.ghost?`<div class="warn">${esc(GHOST[n.id])}</div>`:''}
   <div class="tags">${tags.join('')||'<span>тип не задан</span>'}</div>
   ${d&&d.desc?`<p class="desc">${esc(d.desc)}</p>`:''}
   ${d?`<div class="meter"><b>Опасность</b><span>${dg} / 5 · ${esc(DL[dg]||'')}</span><div><i style="width:${dg/5*100}%"></i></div></div>`
     :`<div class="empty">Параметры станции недоступны${S.offline?' — нет связи с сервером':''}.</div>`}
   <dl class="kv">${rows.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
   ${npcs(n).length?`<div class="sec">NPC на станции</div><div class="npc">${npcs(n).map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}
   <div class="sec">Соседи по схеме</div>
   <div class="links">${nb.map(x=>`<button type="button" data-go="${esc(x.n.id)}"><i style="background:${L[x.n.lk].color}"></i>${esc(x.n.name)}<em>${x.k}</em></button>`).join('')||'<div class="empty">Соседей нет</div>'}</div>
   <div class="g2" style="margin-top:11px"><button class="b sm" data-a="copy" type="button">⧉ Название</button>
    <button class="b sm" data-a="center" type="button">⌖ В центр</button></div>`;
  R.dock.classList.remove('hidden');
  R.dock.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>{sfx('button.mp3');fly(b.dataset.go);setTimeout(()=>openDock(b.dataset.go),230);});
  const q=a=>R.dock.querySelector(`[data-a="${a}"]`);
  q('x').onclick=closeDock;
  q('center').onclick=()=>{fly(n.id);setTimeout(placeDock,250);sfx('button.mp3');};
  q('copy').onclick=async()=>{try{await navigator.clipboard.writeText(n.name);toast('Название скопировано','success');}catch(_){toast('Буфер недоступен','warn');}};
  placeDock(ev);
}
function placeDock(ev){
  if(R.dock.classList.contains('hidden'))return;
  const st=R.stage.getBoundingClientRect();if(!st.width||!st.height)return;
  const w=R.dock.offsetWidth,hh=R.dock.offsetHeight;let x,y;
  if(ev){x=ev.clientX-st.left+16;y=ev.clientY-st.top+16;}
  else if(S.sel&&BY.has(S.sel)){const n=BY.get(S.sel),p=ptr({clientX:st.left,clientY:st.top});
    const r=R.svg.getBoundingClientRect();
    x=(n.x-p.x)/p.s+18;y=(n.y-p.y)/p.s+18;void r;}
  else{x=18;y=18;}
  if(x+w>st.width-10)x=Math.max(10,x-w-38);
  if(y+hh>st.height-10)y=Math.max(10,st.height-hh-10);
  R.dock.style.left=cl(x,10,Math.max(10,st.width-w-10))+'px';
  R.dock.style.top=cl(y,10,Math.max(10,st.height-hh-10))+'px';
}
function closeDock(){R.dock.classList.add('hidden');if(S.sel){S.sel=null;draw();}}
function log(t,c){R.log.textContent=t;R.log.className='log '+(c||'');}

/* ═══════════ ЭКСПОРТ ═══════════ */
function serialize(){
  const vb=R.svg.viewBox.baseVal,c=R.svg.cloneNode(true);
  c.setAttribute('xmlns',NS);c.setAttribute('width',Math.round(vb.width));c.setAttribute('height',Math.round(vb.height));
  c.removeAttribute('class');c.removeAttribute('style');
  c.insertBefore(sv('rect',{x:vb.x,y:vb.y,width:vb.width,height:vb.height,fill:'#07090b'}),c.firstChild);
  const t=sv('text',{x:vb.x+20,y:vb.y+28,fill:'#ffb02e','font-size':'16','font-weight':'800',
    'font-family':'ui-monospace, monospace','letter-spacing':'2.4'});
  t.textContent='44 WHITE CURTAIN · СХЕМА МЕТРО · СЕТКА 2015';c.appendChild(t);
  return '<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(c);
}
function dl(b,name){const u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=name;
  document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),4000);}
function expSVG(){try{dl(new Blob([serialize()],{type:'image/svg+xml;charset=utf-8'}),'metro44-2015.svg');
  toast('SVG сохранён','success');log('SVG выгружен','ok');}catch(_){toast('Не удалось сохранить SVG','warn');}}
function expPNG(){
  const vb=R.svg.viewBox.baseVal,u=URL.createObjectURL(new Blob([serialize()],{type:'image/svg+xml;charset=utf-8'}));
  const img=new Image();
  img.onload=()=>{try{
    const cv=document.createElement('canvas');cv.width=Math.round(vb.width*2);cv.height=Math.round(vb.height*2);
    const c=cv.getContext('2d');c.fillStyle='#07090b';c.fillRect(0,0,cv.width,cv.height);c.drawImage(img,0,0,cv.width,cv.height);
    cv.toBlob(b=>{if(b){dl(b,'metro44-2015.png');toast('PNG сохранён','success');log('PNG выгружен','ok');}else toast('PNG не собрался','warn');},'image/png');
  }catch(_){toast('Браузер запретил PNG — возьми SVG','warn');}URL.revokeObjectURL(u);};
  img.onerror=()=>{URL.revokeObjectURL(u);toast('Не удалось отрисовать PNG — возьми SVG','warn');};
  img.src=u;
}
async function copySVG(){try{await navigator.clipboard.writeText(serialize());toast('SVG в буфере','success');log('SVG скопирован','ok');}
  catch(_){toast('Буфер недоступен — «Скачать SVG»','warn');}}

/* ═══════════ ПУЛЬТ ═══════════ */
function atmo(){
  const a=+S.cfg.atmo/100;
  R.atmo.style.opacity=String(.2+a*.95);
  R.vig.style.opacity=String(.3+a*.7);
  R.scan.style.opacity=String(a*.5);
  R.grain.style.opacity=String(S.cfg.grain?a*.32:0);
}
function sync(){
  R.kZoom.value=String(Math.round(cam.z*100));R.vZoom.textContent=cam.z.toFixed(2);
  R.kNode.value=S.cfg.node;R.vNode.textContent=(+S.cfg.node).toFixed(2);
  R.kLine.value=S.cfg.line;R.vLine.textContent=S.cfg.line;
  R.kGlow.value=S.cfg.glow;R.vGlow.textContent=S.cfg.glow;
  R.kAtmo.value=S.cfg.atmo;R.vAtmo.textContent=S.cfg.atmo;
  R.kLbl.value=S.cfg.lbl;R.kTheme.value=S.cfg.theme;HOST.dataset.theme=S.cfg.theme;
  R.kPlayers.checked=S.cfg.players;R.kDanger.checked=S.cfg.danger;R.kGuides.checked=S.cfg.guides;
  R.kGame.checked=S.cfg.game;R.kFocus.checked=S.cfg.focus;R.kGrain.checked=S.cfg.grain;
  atmo();
}
R.kZoom.addEventListener('input',e=>setCam(goal.x,goal.y,+e.target.value/100,true));
R.kNode.addEventListener('input',e=>{S.cfg.node=+e.target.value;R.vNode.textContent=S.cfg.node.toFixed(2);save();draw();});
R.kLine.addEventListener('input',e=>{S.cfg.line=+e.target.value;R.vLine.textContent=S.cfg.line;save();draw();});
R.kGlow.addEventListener('input',e=>{S.cfg.glow=+e.target.value;R.vGlow.textContent=S.cfg.glow;save();draw();});
R.kAtmo.addEventListener('input',e=>{S.cfg.atmo=+e.target.value;R.vAtmo.textContent=S.cfg.atmo;save();atmo();});
R.kLbl.addEventListener('change',e=>{S.cfg.lbl=e.target.value;save();draw();});
R.kTheme.addEventListener('change',e=>{S.cfg.theme=e.target.value;HOST.dataset.theme=S.cfg.theme;save();draw();mini();});
[['kPlayers','players'],['kDanger','danger'],['kGuides','guides'],['kGame','game'],['kFocus','focus'],['kGrain','grain']]
  .forEach(([r,k])=>R[r].addEventListener('change',e=>{S.cfg[k]=e.target.checked;save();atmo();draw();}));
R.kReset.onclick=()=>{Object.assign(S.cfg,DEF);save();sync();draw();mini();fitWidth();sfx('button.mp3');log('Вид сброшен','ok');};
R.kRand.onclick=()=>{const th=['tunnel','radio','night'];
  S.cfg.node=+(.75+Math.random()*.95).toFixed(2);S.cfg.line=4+Math.floor(Math.random()*10);
  S.cfg.glow=Math.floor(Math.random()*23);S.cfg.atmo=25+Math.floor(Math.random()*76);
  S.cfg.theme=th[Math.floor(Math.random()*3)];S.cfg.guides=Math.random()<.4;S.cfg.danger=Math.random()<.6;
  save();sync();draw();mini();sfx('ding.mp3');log('Случайный вид применён','ok');};
R.kPng.onclick=expPNG;R.kSvg.onclick=expSVG;R.kCopy.onclick=copySVG;
R.jTop.onclick=()=>{setCam(MAPW/2,300,Math.max(goal.z,1.05));sfx('button.mp3');};
R.jEnd.onclick=()=>{const n=BY.get('бунинская_аллея');setCam(n.x+200,n.y-140,Math.max(goal.z,1.15));sfx('button.mp3');};

/* ═══════════ ЗВУК ═══════════ */
function soundOn(){const b=document.getElementById('sound');
  if(b)return b.classList.contains('on')||b.getAttribute('aria-pressed')==='true';return true;}
function paintSound(){const on=soundOn();R.mute.textContent=on?'🔊':'🔇';
  R.mute.classList.toggle('on',on);R.mute.setAttribute('aria-pressed',String(on));
  R.mute.title=on?'Звук терминала включён — выключить':'Звук выключен — включить';}
R.mute.onclick=()=>{const b=document.getElementById('sound');if(b)b.click();setTimeout(paintSound,30);};

/* ═══════════ ВВОД ═══════════ */
R.svg.addEventListener('click',e=>{const g=e.target.closest('g[data-id]');
  if(!g){closeDock();return;}sfx('button.mp3');openDock(g.dataset.id,e);});
R.svg.addEventListener('contextmenu',e=>{const g=e.target.closest('g[data-id]');if(!g)return;e.preventDefault();openDock(g.dataset.id,e);});
R.svg.addEventListener('keydown',e=>{
  const g=e.target.closest('g[data-id]');
  if(g&&(e.key==='Enter'||e.key===' ')){e.preventDefault();openDock(g.dataset.id);return;}
  const s=110/cam.z;
  if(e.key==='ArrowUp'){e.preventDefault();setCam(goal.x,goal.y-s,goal.z,true);}
  else if(e.key==='ArrowDown'){e.preventDefault();setCam(goal.x,goal.y+s,goal.z,true);}
  else if(e.key==='ArrowLeft'){e.preventDefault();setCam(goal.x-s,goal.y,goal.z,true);}
  else if(e.key==='ArrowRight'){e.preventDefault();setCam(goal.x+s,goal.y,goal.z,true);}
});
R.svg.addEventListener('wheel',e=>{e.preventDefault();const p=ptr(e);
  const nz2=cl(goal.z*(e.deltaY<0?1.15:1/1.15),.3,3.6),k=1-goal.z/nz2;
  setCam(goal.x+(p.x-goal.x)*k,goal.y+(p.y-goal.y)*k,nz2,true);},{passive:false});
R.svg.addEventListener('pointerdown',e=>{if(e.target.closest('g[data-id]'))return;
  stopEase();cam.x=goal.x;cam.y=goal.y;cam.z=goal.z;
  S.drag={x:e.clientX,y:e.clientY,cx:cam.x,cy:cam.y,moved:false};
  R.svg.classList.add('drag');try{R.svg.setPointerCapture(e.pointerId);}catch(_){}});
R.svg.addEventListener('pointermove',e=>{if(!S.drag)return;
  const dx=e.clientX-S.drag.x,dy=e.clientY-S.drag.y;
  if(Math.abs(dx)+Math.abs(dy)>4)S.drag.moved=true;
  const p=ptr(e);setCam(S.drag.cx-dx*p.s,S.drag.cy-dy*p.s,cam.z,true);});
const up=e=>{if(!S.drag)return;if(!S.drag.moved)closeDock();else placeDock();
  S.drag=null;R.svg.classList.remove('drag');try{R.svg.releasePointerCapture(e.pointerId);}catch(_){}};
R.svg.addEventListener('pointerup',up);R.svg.addEventListener('pointercancel',up);
R.q.addEventListener('input',()=>{S.query=nz(R.q.value);draw();
  if(!S.query){R.ac.classList.add('hidden');return;}
  const hits=NODES.filter(n=>nz(n.name).includes(S.query)||nz(n.id).includes(S.query)).slice(0,8);
  if(!hits.length){R.ac.classList.add('hidden');return;}
  R.ac.innerHTML=hits.map(n=>`<button type="button" data-id="${esc(n.id)}"><i style="background:${L[n.lk].color}"></i><b>${esc(n.name)}</b><em>${esc(L[n.lk].num)}${n.inGame?'':' · нет в игре'}</em></button>`).join('');
  R.ac.classList.remove('hidden');});
R.ac.addEventListener('click',e=>{const b=e.target.closest('[data-id]');if(!b)return;
  fly(b.dataset.id);setTimeout(()=>openDock(b.dataset.id),230);
  R.ac.classList.add('hidden');R.q.value='';S.query='';draw();sfx('button.mp3');});
R.q.addEventListener('keydown',e=>{
  if(e.key==='Enter'){const f=R.ac.querySelector('[data-id]');
    if(f){fly(f.dataset.id);setTimeout(()=>openDock(f.dataset.id),230);R.ac.classList.add('hidden');R.q.value='';S.query='';draw();}}
  else if(e.key==='Escape'){R.ac.classList.add('hidden');R.q.blur();}});
R.fit.onclick=()=>{fitAll();sfx('button.mp3');};
R.here.onclick=()=>{if(S.me&&S.me.station&&BY.has(S.me.station)){fly(S.me.station);setTimeout(()=>openDock(S.me.station),230);sfx('button.mp3');}
  else log('Персонаж не создан — /start','warn');};
R.reload.onclick=()=>{sfx('button.mp3');load();};
R.close.onclick=close;
R.zin.onclick=()=>setCam(goal.x,goal.y,goal.z*1.28,true);
R.zout.onclick=()=>setCam(goal.x,goal.y,goal.z/1.28,true);

/* ═══════════ ОКНО ═══════════ */
let prevFocus=null;
function open(){
  if(S.open)return;S.open=true;prevFocus=document.activeElement;
  HOST.classList.remove('hidden');HOST.setAttribute('aria-hidden','false');
  sync();paintSound();legend();draw();mini();
  if(!S.loaded)load();else fitWidth(true);
  sfx('ding.mp3');
  if(!ro&&window.ResizeObserver){ro=new ResizeObserver(()=>{if(S.open){view();placeDock();}});ro.observe(R.stage);}
  setTimeout(()=>{try{R.q.focus();}catch(_){}},120);
}
function close(){
  if(!S.open)return;closeDock();S.open=false;stopEase();miniDown=false;S.drag=null;R.svg.classList.remove('drag');
  HOST.classList.add('hidden');HOST.setAttribute('aria-hidden','true');
  if(prevFocus&&prevFocus.focus)try{prevFocus.focus();}catch(_){}
}
function toggle(){S.open?close():open();}
HOST.addEventListener('mousedown',e=>{if(e.target===HOST||e.target.classList.contains('scrim'))close();});
window.addEventListener('resize',()=>{if(S.open){view();placeDock();}});
document.addEventListener('keydown',e=>{
  const tag=document.activeElement&&document.activeElement.tagName;
  const typing=['INPUT','TEXTAREA','SELECT'].includes(tag);
  if(e.key==='Escape'&&S.open){
    if(!R.dock.classList.contains('hidden')){closeDock();return;}
    if(!R.ac.classList.contains('hidden')){R.ac.classList.add('hidden');return;}
    close();return;}
  if(S.open&&e.key==='Tab'){
    const f=[...WIN.querySelectorAll('button,input,select,[tabindex="0"]')].filter(n=>n.offsetParent!==null||n.ownerSVGElement);
    if(!f.length)return;const a=f[0],b=f[f.length-1];
    if(e.shiftKey&&document.activeElement===a){e.preventDefault();b.focus();}
    else if(!e.shiftKey&&document.activeElement===b){e.preventDefault();a.focus();}return;}
  if(!S.open&&!typing&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&['m','M','ь','Ь'].includes(e.key)){e.preventDefault();open();}
});
const mb=document.getElementById('map-btn');if(mb)mb.onclick=toggle;
document.querySelectorAll('[data-open-map]').forEach(b=>b.onclick=open);

/* ═══════════ СВЯЗЬ С ИГРОЙ ═══════════ */
WC.on('world',w=>{
  if(!w)return;
  S.online=(w.online||[]).map(p=>({id:p.id,name:p.name,station:p.station,location:p.location}));
  R.sO.textContent=String(S.online.length);
  const loc=w.me&&w.me.location;
  if(loc){const id=resolve(loc);
    if(id){const changed=!S.me||S.me.station!==id;
      S.me=Object.assign({},S.me,{station:id,location:loc,has_character:true});
      R.at.textContent=(BY.get(id)||{}).name||loc;
      if(changed&&S.open){fly(id);placeDock();mini();}}}
  if(S.open){draw();mini();}
});
WC.on('ready',()=>{if(S.open&&!S.loaded)load();});

sync();legend();draw();mini();
window.WCMAP={open,close,toggle,info:openDock,reload:load,exportPNG:expPNG,exportSVG:expSVG};
})();