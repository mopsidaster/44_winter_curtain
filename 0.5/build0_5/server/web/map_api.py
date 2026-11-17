# -*- coding: utf-8 -*-
"""Интерактивная схема метро: читает реальные станции игры, строит граф,
раскладывает его в схему линий и водит игрока через штатное меню перемещения."""
from __future__ import annotations
import importlib, json, logging, math, os, random, re, time

log = logging.getLogger("web.map")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LINE_PALETTE = ["#ff8a3d", "#4aa8ff", "#66ff99", "#ff5cc8", "#ffd23f", "#9b7bff", "#ff4d3d", "#37d6c8"]
NAME_KEYS = ("name", "название", "title", "имя", "display", "station_name")
LINE_KEYS = ("line", "линия", "ветка", "branch", "metro_line", "line_name")
LINK_KEYS = ("connections", "neighbors", "links", "exits", "переходы", "связи", "соседи",
             "adjacent", "paths", "tunnels", "соединения", "переход")
TYPE_KEYS = ("type", "types", "тип", "station_type", "tags", "типы")
FACT_KEYS = ("faction", "фракция", "owner", "владелец")
DANGER_KEYS = ("danger", "опасность", "threat", "danger_level", "уровень_опасности")
RAD_KEYS = ("radiation", "радиация", "rad", "фон")
DEPTH_KEYS = ("depth", "глубина")
SURF_KEYS = ("surface", "поверхность", "is_surface", "на_поверхности")
DESC_KEYS = ("description", "desc", "описание", "lore", "история")
TECH_KEYS = ("technical", "tech", "техтоннель", "технический", "tunnel_type")

_CACHE = {"ts": 0.0, "graph": None}


def _norm(s):
    return re.sub(r"[^a-zа-я0-9]+", "", str(s or "").lower().replace("ё", "е"))


def _pick(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _as_list(v):
    if v is None: return []
    if isinstance(v, str): return [v]
    if isinstance(v, dict): return list(v.keys())
    if isinstance(v, (list, tuple, set)): return list(v)
    return []


def _raw_stations():
    """Слой 1 — config/stations.json, слой 2 — модули игры со словарём станций."""
    path = os.path.join(BASE, "config", "stations.json")
    try:
        data = json.load(open(path, encoding="utf-8-sig"))
        if isinstance(data, dict):
            for wrap in ("stations", "станции", "data", "map"):
                if wrap in data and isinstance(data[wrap], (dict, list)):
                    data = data[wrap]; break
        out = {}
        if isinstance(data, dict):
            for k, v in data.items():
                out[str(k)] = dict(v) if isinstance(v, dict) else {"name": str(v)}
        elif isinstance(data, list):
            for i, v in enumerate(data):
                if isinstance(v, dict):
                    key = str(v.get("id") or v.get("key") or v.get("name") or i)
                    out[key] = dict(v)
        if out: return out
    except Exception as e:
        log.info("stations.json не читается (%s), ищу в модулях", e)

    for modname in ("func.map_data", "config.map_config", "func.station_utils", "func"):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        best = None
        for attr in dir(mod):
            if attr.startswith("_"): continue
            try: val = getattr(mod, attr)
            except Exception: continue
            if isinstance(val, dict) and 3 <= len(val) <= 400:
                sample = [v for v in list(val.values())[:6] if isinstance(v, dict)]
                if sample and any(_pick(s, NAME_KEYS + LINE_KEYS + LINK_KEYS + TYPE_KEYS) is not None for s in sample):
                    if best is None or len(val) > len(best):
                        best = val
        if best:
            log.warning("Станции взяты из %s (%d шт.)", modname, len(best))
            return {str(k): (dict(v) if isinstance(v, dict) else {"name": str(v)}) for k, v in best.items()}
    return {}


def _helpers():
    h = {}
    for modname in ("func", "func.station_utils", "func.map_data"):
        try: mod = importlib.import_module(modname)
        except Exception: continue
        for fn in ("is_trade_station", "has_station_type", "get_npcs_on_station",
                   "is_start_station", "get_station", "get_station_name"):
            if fn not in h and callable(getattr(mod, fn, None)):
                h[fn] = getattr(mod, fn)
    return h


def _call(fn, *args):
    try: return fn(*args)
    except Exception: return None


def _services(sid, raw, H):
    s = set()
    types = " ".join(str(x).lower() for x in _as_list(_pick(raw, TYPE_KEYS, [])))
    blob = (types + " " + json.dumps(raw, ensure_ascii=False).lower())
    checks = {
        "trader": ("торгов", "trade", "магазин", "лавка", "рынок"),
        "doctor": ("врач", "медик", "doctor", "аптек", "больниц", "медпункт"),
        "workshop": ("мастерск", "workshop", "ремонт", "оружейник"),
        "campfire": ("костёр", "костер", "campfire", "привал", "лагерь"),
        "food": ("еда", "food", "столов", "кухня", "паёк"),
        "faction": ("фракц", "faction", "штаб", "база"),
        "quest": ("квест", "quest", "задани", "доска"),
    }
    for key, words in checks.items():
        if any(w in blob for w in words): s.add(key)
    if H.get("is_trade_station") and _call(H["is_trade_station"], sid): s.add("trader")
    if H.get("is_start_station") and _call(H["is_start_station"], sid): s.add("start")
    for t, key in (("торговая", "trader"), ("trade", "trader"), ("медицинская", "doctor"),
                   ("мастерская", "workshop"), ("костёр", "campfire")):
        if H.get("has_station_type") and _call(H["has_station_type"], sid, t): s.add(key)
    npcs = _call(H["get_npcs_on_station"], sid) if H.get("get_npcs_on_station") else None
    names = []
    for n in _as_list(npcs):
        if isinstance(n, dict):
            names.append(str(n.get("name") or n.get("имя") or n.get("id") or "NPC"))
        else:
            names.append(str(getattr(n, "name", n)))
    if names: s.add("npc")
    return sorted(s), names


def build_graph(force=False):
    now = time.time()
    if not force and _CACHE["graph"] and now - _CACHE["ts"] < 120:
        return _CACHE["graph"]
    raw = _raw_stations()
    H = _helpers()
    stations = {}
    for sid, r in raw.items():
        name = str(_pick(r, NAME_KEYS, sid))
        line = str(_pick(r, LINE_KEYS, "") or "")
        surf = bool(_pick(r, SURF_KEYS, False))
        if not surf and any(w in (name + " " + line).lower() for w in ("поверхн", "surface", "улица")):
            surf = True
        danger = _pick(r, DANGER_KEYS, 0)
        try: danger = float(re.sub(r"[^\d.]", "", str(danger)) or 0)
        except Exception: danger = 0.0
        rad = _pick(r, RAD_KEYS, 0)
        try: rad = float(re.sub(r"[^\d.]", "", str(rad)) or 0)
        except Exception: rad = 0.0
        depth = _pick(r, DEPTH_KEYS, None)
        try: depth = float(re.sub(r"[^\d.\-]", "", str(depth))) if depth is not None else None
        except Exception: depth = None
        serv, npcs = _services(sid, r, H)
        stations[sid] = {
            "id": sid, "name": name, "line": line or ("Поверхность" if surf else "Тоннели"),
            "faction": str(_pick(r, FACT_KEYS, "") or ""), "danger": danger, "radiation": rad,
            "depth": depth, "surface": surf, "services": serv, "npc": npcs,
            "desc": str(_pick(r, DESC_KEYS, "") or "")[:600], "links": [],
        }

    # связи
    seen = set()
    for sid, r in raw.items():
        if sid not in stations: continue
        for target in _as_list(_pick(r, LINK_KEYS, [])):
            tid = str(target if not isinstance(target, dict) else (target.get("to") or target.get("id") or ""))
            if tid not in stations:
                match = next((k for k in stations if _norm(k) == _norm(tid) or _norm(stations[k]["name"]) == _norm(tid)), None)
                if not match: continue
                tid = match
            if tid == sid: continue
            kind = "tech" if any(w in json.dumps(r, ensure_ascii=False).lower() for w in TECH_KEYS) else "tunnel"
            if stations[sid]["surface"] or stations[tid]["surface"]: kind = "surface"
            key = tuple(sorted((sid, tid))) + (kind,)
            if key in seen: continue
            seen.add(key)
            stations[sid]["links"].append({"to": tid, "kind": kind})
            stations[tid]["links"].append({"to": sid, "kind": kind})

    if not stations:
        return {"ok": False, "error": "Станции не найдены в config/stations.json", "stations": [], "lines": []}

    # линии
    line_names = []
    for s in stations.values():
        if s["line"] not in line_names: line_names.append(s["line"])
    lines = [{"id": f"L{i}", "name": n, "color": LINE_PALETTE[i % len(LINE_PALETTE)]}
             for i, n in enumerate(line_names)]
    lid = {n: l["id"] for n, l in zip(line_names, lines)}
    for s in stations.values(): s["line_id"] = lid[s["line"]]

    _layout(stations, lines)
    graph = {"ok": True, "stations": list(stations.values()), "lines": lines,
             "bounds": {"w": 1000, "h": 700}, "generated": now}
    _CACHE.update(ts=now, graph=graph)
    log.warning("Схема собрана: %d станций, %d линий, %d связей",
                len(stations), len(lines), sum(len(s["links"]) for s in stations.values()) // 2)
    return graph


def _layout(stations, lines):
    ids = list(stations)
    rnd = random.Random(44)
    by_line = {}
    for s in stations.values(): by_line.setdefault(s["line_id"], []).append(s["id"])
    pos = {}
    for i, l in enumerate(lines):
        ang = (i / max(1, len(lines))) * math.pi * 2
        dx, dy = math.cos(ang), math.sin(ang)
        members = by_line.get(l["id"], [])
        # порядок вдоль линии — обходом по связям
        ordered = []
        pool = set(members)
        while pool:
            start = min(pool, key=lambda k: (len([x for x in stations[k]["links"] if x["to"] in pool]), k))
            chain = [start]; pool.discard(start)
            while True:
                nxt = next((x["to"] for x in stations[chain[-1]]["links"] if x["to"] in pool), None)
                if not nxt: break
                chain.append(nxt); pool.discard(nxt)
            ordered += chain
        n = len(ordered)
        for j, sid in enumerate(ordered):
            t = (j - (n - 1) / 2) * 92
            pos[sid] = [500 + dx * t + rnd.uniform(-14, 14), 350 + dy * t + rnd.uniform(-14, 14)]

    edges = [(a, b["to"]) for a, s in stations.items() for b in s["links"] if a < b["to"]]
    for _ in range(220):
        force = {k: [0.0, 0.0] for k in ids}
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                dx = pos[a][0] - pos[b][0]; dy = pos[a][1] - pos[b][1]
                d2 = dx * dx + dy * dy + 0.01
                if d2 > 260000: continue
                f = 26000.0 / d2
                d = math.sqrt(d2)
                force[a][0] += dx / d * f; force[a][1] += dy / d * f
                force[b][0] -= dx / d * f; force[b][1] -= dy / d * f
        for a, b in edges:
            dx = pos[b][0] - pos[a][0]; dy = pos[b][1] - pos[a][1]
            d = math.hypot(dx, dy) or 0.01
            f = (d - 105) * 0.045
            force[a][0] += dx / d * f; force[a][1] += dy / d * f
            force[b][0] -= dx / d * f; force[b][1] -= dy / d * f
        for l in lines:
            mem = by_line.get(l["id"], [])
            if len(mem) < 3: continue
            cx = sum(pos[m][0] for m in mem) / len(mem)
            cy = sum(pos[m][1] for m in mem) / len(mem)
            sxx = sum((pos[m][0] - cx) ** 2 for m in mem)
            syy = sum((pos[m][1] - cy) ** 2 for m in mem)
            sxy = sum((pos[m][0] - cx) * (pos[m][1] - cy) for m in mem)
            theta = 0.5 * math.atan2(2 * sxy, sxx - syy + 1e-6)
            ux, uy = math.cos(theta), math.sin(theta)
            for m in mem:
                rx, ry = pos[m][0] - cx, pos[m][1] - cy
                proj = rx * ux + ry * uy
                force[m][0] += (cx + ux * proj - pos[m][0]) * 0.06
                force[m][1] += (cy + uy * proj - pos[m][1]) * 0.06
        for k in ids:
            pos[k][0] += max(-9, min(9, force[k][0]))
            pos[k][1] += max(-9, min(9, force[k][1]))

    xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sx = 880 / max(1.0, maxx - minx); sy = 580 / max(1.0, maxy - miny)
    for sid, s in stations.items():
        s["x"] = round(60 + (pos[sid][0] - minx) * sx, 2)
        s["y"] = round(60 + (pos[sid][1] - miny) * sy, 2)


def find_station(graph, key):
    if not key: return None
    k = _norm(key)
    for s in graph["stations"]:
        if _norm(s["id"]) == k or _norm(s["name"]) == k: return s
    for s in graph["stations"]:
        if k and (k in _norm(s["id"]) or k in _norm(s["name"])): return s
    return None


def route(graph, a, b):
    import heapq
    ids = {s["id"]: s for s in graph["stations"]}
    if a not in ids or b not in ids: return []
    dist = {a: 0.0}; prev = {}; q = [(0.0, a)]
    while q:
        d, cur = heapq.heappop(q)
        if cur == b: break
        if d > dist.get(cur, 1e9): continue
        for l in ids[cur]["links"]:
            t = l["to"]
            if t not in ids: continue
            w = 1.0 + ids[t]["danger"] * 0.45 + (1.2 if l["kind"] == "surface" else 0.0)
            nd = d + w
            if nd < dist.get(t, 1e9):
                dist[t] = nd; prev[t] = cur; heapq.heappush(q, (nd, t))
    if b not in prev and a != b: return []
    path = [b]
    while path[-1] != a: path.append(prev[path[-1]])
    return list(reversed(path))


def payload(session, force=False):
    from func.game_manager import game_manager
    g = build_graph(force)
    p = game_manager.get_player(session.user.id)
    loc = getattr(p, "location", None)
    here = find_station(g, loc) if loc else None
    online = []
    if session.hub.world:
        for uid, info in session.hub.world.online().items():
            st = find_station(g, info.get("location"))
            online.append({"id": uid, "name": info.get("name"), "login": info.get("login"),
                           "station": st["id"] if st else None, "alive": info.get("alive", True)})
    return {
        "ok": g.get("ok", False), "error": g.get("error"), "stations": g["stations"],
        "lines": g["lines"], "bounds": g.get("bounds", {"w": 1000, "h": 700}),
        "me": {
            "id": session.user.id, "station": here["id"] if here else None,
            "location": loc, "alive": bool(getattr(p, "is_alive", True)) if p else False,
            "has_character": p is not None
        },
        "online": online
    }


async def step_move(session, target):
    """Один переход — через штатное /move и кнопки игры, без обхода её логики."""
    from func.game_manager import game_manager
    from discord_shim import COMMANDS, Select

    g = build_graph()
    dest = find_station(g, target)
    p = game_manager.get_player(session.user.id)
    if p is None: return {"ok": False, "reason": "Нет персонажа — /start"}
    if not getattr(p, "is_alive", True): return {"ok": False, "reason": "Персонаж мёртв"}
    if dest is None: return {"ok": False, "reason": "Станция не найдена на схеме"}
    before = getattr(p, "location", None)
    here = find_station(g, before)
    if here and here["id"] == dest["id"]:
        return {"ok": True, "moved": False, "arrived": True, "station": dest["id"], "reason": "Уже на месте"}
    if here and dest["id"] not in [l["to"] for l in here["links"]]:
        return {"ok": False, "reason": "Нет прямого перехода — иди по маршруту по шагам"}

    names = {dest["name"], dest["id"]}
    meta = COMMANDS.get("move")
    if meta and meta["params"]:
        try:
            await session.command("move", **{meta["params"][0]: dest["name"]})
        except Exception:
            log.debug("move с параметром не сработал", exc_info=True)
    if _norm(getattr(p, "location", None)) != _norm(before):
        return _result(g, p, before, dest)

    await session.command("move")
    for _ in range(6):
        view = session.active_view()
        if view is None: break
        hit = None
        for item in view.children:
            if isinstance(item, Select):
                opt = next((o for o in item.options
                            if any(_norm(n) and _norm(n) in _norm(o.label) for n in names)
                            or any(_norm(n) == _norm(o.value) for n in names)), None)
                if opt: hit = (item, [opt.value]); break
            else:
                lbl = _norm(getattr(item, "label", ""))
                if lbl and any(_norm(n) in lbl for n in names if _norm(n)):
                    hit = (item, None); break
        if hit:
            item, values = hit
            await session.click(view.id, item.custom_id, values)
            break
        nxt = next((i for i in view.children
                    if any(w in _norm(getattr(i, "label", "")) for w in ("далее", "ещё", "еще", "вперёд", "вперед", "след"))), None)
        if nxt is None: break
        await session.click(view.id, nxt.custom_id)

    if _norm(getattr(p, "location", None)) == _norm(before):
        for fname in ("move_player", "move_to", "make_move"):
            fn = getattr(game_manager, fname, None)
            if not callable(fn): continue
            try:
                import inspect as _i
                if len(_i.signature(fn).parameters) != 2: continue
                res = fn(p, dest["id"])
                if hasattr(res, "__await__"): await res
                break
            except Exception:
                log.debug("%s не подошёл", fname, exc_info=True)

    if _norm(getattr(p, "location", None)) == _norm(before):
        return {"ok": False, "moved": False, "station": here["id"] if here else None,
                "reason": "Переход не выполнен: игра не приняла команду (проверь выносливость, события или бой)"}
    return _result(g, p, before, dest)


def _result(g, p, before, dest):
    now = getattr(p, "location", None)
    st = find_station(g, now)
    return {
        "ok": True, "moved": True, "arrived": bool(st and st["id"] == dest["id"]),
        "from": before, "location": now, "station": st["id"] if st else None,
        "alive": bool(getattr(p, "is_alive", True))
    }

from aiohttp import web

async def api_map_handler(request):
    """HTTP GET /api/map — отдаёт данные схемы для map.js"""
    from app import _session
    s = _session(request)
    if s is None:
        return web.json_response({"ok": False, "error": "Требуется вход"}, status=401)

    force = request.query.get("force") == "1"
    try:
        data = payload(s, force=force)
        return web.json_response(data)
    except Exception as e:
        log.exception("Ошибка в /api/map")
        return web.json_response({"ok": False, "error": str(e)}, status=500)

async def ws_map_move_handler(session, data):
    """Обработчик WebSocket сообщения {type: 'map_move', to: 'station_id'}"""
    target = data.get("to")
    try:
        res = await step_move(session, target)
    except Exception as e:
        log.exception("Ошибка в map_move")
        res = {"ok": False, "reason": f"Внутренняя ошибка: {e}"}

    if session.hub:
        # Отправляем результат напрямую в WebSocket, чтобы map.js получил map_step
        await session.hub.emit_to(session.user.id, {"type": "map_step", **res})
        if session.hub.world:
            await session.hub.world.push(session, force=True)

def setup(app):
    """Регистрирует маршруты карты в aiohttp приложении"""
    app.router.add_get("/api/map", api_map_handler)