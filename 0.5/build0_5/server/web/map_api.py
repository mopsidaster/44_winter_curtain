# -*- coding: utf-8 -*-
"""Интерактивная схема метро: читает реальные станции игры, строит граф,
раскладывает его в схему линий и водит игрока через штатное меню перемещения.

Ревизия 0.5:
  * build_graph больше не блокирует event loop (вызов через to_thread);
  * force=1 доступен только админу и не чаще раза в 30 секунд;
  * переходы идут строго через игровые команды/кнопки — обходной fallback убран;
  * весь автопереход выполняется под одним замком сессии;
  * нет циклического импорта app -> map_api -> app.
"""
from __future__ import annotations

import asyncio
import contextlib
import heapq
import importlib
import json
import logging
import math
import os
import random
import re
import time

from aiohttp import web

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
_BUILD_LOCK = asyncio.Lock()
_FORCE_TS = 0.0
FORCE_COOLDOWN = 30.0          # сек между принудительными пересборками
CACHE_TTL = 120.0
LAYOUT_ITERATIONS = int(os.environ.get("WC_MAP_ITER", "160"))


def _norm(s):
    return re.sub(r"[^a-zа-я0-9]+", "", str(s or "").lower().replace("ё", "е"))


def _pick(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return list(v.keys())
    if isinstance(v, (list, tuple, set)):
        return list(v)
    return []


def _num(value, default=0.0):
    try:
        return float(re.sub(r"[^\d.\-]", "", str(value)) or default)
    except (TypeError, ValueError):
        return default


def _raw_stations():
    """Слой 1 — config/stations.json, слой 2 — модули игры со словарём станций."""
    path = os.path.join(BASE, "config", "stations.json")
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for wrap in ("stations", "станции", "data", "map"):
                if wrap in data and isinstance(data[wrap], (dict, list)):
                    data = data[wrap]
                    break
        out = {}
        if isinstance(data, dict):
            for k, v in data.items():
                out[str(k)] = dict(v) if isinstance(v, dict) else {"name": str(v)}
        elif isinstance(data, list):
            for i, v in enumerate(data):
                if isinstance(v, dict):
                    key = str(v.get("id") or v.get("key") or v.get("name") or i)
                    out[key] = dict(v)
        if out:
            return out
    except Exception as e:
        log.info("stations.json не читается (%s), ищу в модулях", e)

    for modname in ("func.map_data", "config.map_config", "func.station_utils", "func"):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        best = None
        for attr in dir(mod):
            if attr.startswith("_"):
                continue
            try:
                val = getattr(mod, attr)
            except Exception:
                continue
            if isinstance(val, dict) and 3 <= len(val) <= 400:
                sample = [v for v in list(val.values())[:6] if isinstance(v, dict)]
                if sample and any(_pick(s, NAME_KEYS + LINE_KEYS + LINK_KEYS + TYPE_KEYS) is not None
                                  for s in sample):
                    if best is None or len(val) > len(best):
                        best = val
        if best:
            log.warning("Станции взяты из %s (%d шт.)", modname, len(best))
            return {str(k): (dict(v) if isinstance(v, dict) else {"name": str(v)})
                    for k, v in best.items()}
    return {}


def _helpers():
    h = {}
    for modname in ("func", "func.station_utils", "func.map_data"):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for fn in ("is_trade_station", "has_station_type", "get_npcs_on_station",
                   "is_start_station", "get_station", "get_station_name",
                   "is_blocked_station"):
            if fn not in h and callable(getattr(mod, fn, None)):
                h[fn] = getattr(mod, fn)
    return h


def _call(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


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
        if any(w in blob for w in words):
            s.add(key)
    if H.get("is_trade_station") and _call(H["is_trade_station"], sid):
        s.add("trader")
    if H.get("is_start_station") and _call(H["is_start_station"], sid):
        s.add("start")
    for t, key in (("торговая", "trader"), ("trade", "trader"), ("медицинская", "doctor"),
                   ("мастерская", "workshop"), ("костёр", "campfire")):
        if H.get("has_station_type") and _call(H["has_station_type"], sid, t):
            s.add(key)
    npcs = _call(H["get_npcs_on_station"], sid) if H.get("get_npcs_on_station") else None
    names = []
    for n in _as_list(npcs):
        if isinstance(n, dict):
            names.append(str(n.get("name") or n.get("имя") or n.get("id") or "NPC"))
        else:
            names.append(str(getattr(n, "name", n)))
    if names:
        s.add("npc")
    return sorted(s), names


def build_graph(force=False):
    """Синхронная сборка. Из event loop вызывать только через graph_async()."""
    now = time.time()
    if not force and _CACHE["graph"] and now - _CACHE["ts"] < CACHE_TTL:
        return _CACHE["graph"]

    raw = _raw_stations()
    H = _helpers()
    stations = {}
    for sid, r in raw.items():
        name = str(_pick(r, NAME_KEYS, sid))
        line = str(_pick(r, LINE_KEYS, "") or "")
        surf = bool(_pick(r, SURF_KEYS, False)) or str(r.get("type", "")) == "на_поверхности"
        if not surf and any(w in (name + " " + line).lower() for w in ("поверхн", "surface", "улица")):
            surf = True
        serv, npcs = _services(sid, r, H)
        blocked = bool(r.get("blocked", False))
        if H.get("is_blocked_station"):
            blocked = bool(_call(H["is_blocked_station"], sid)) or blocked
        stations[sid] = {
            "id": sid, "name": name, "line": line or ("Поверхность" if surf else "Тоннели"),
            "faction": str(_pick(r, FACT_KEYS, "") or ""),
            "danger": _num(_pick(r, DANGER_KEYS, 0)),
            "radiation": _num(_pick(r, RAD_KEYS, 0)),
            "depth": _num(_pick(r, DEPTH_KEYS), None) if _pick(r, DEPTH_KEYS) is not None else None,
            "surface": surf, "services": serv, "npc": npcs,
            "blocked": blocked, "faction_lock": bool(r.get("faction_lock", False)),
            "desc": str(_pick(r, DESC_KEYS, "") or "")[:600], "links": [],
        }

    # связи
    seen = set()
    for sid, r in raw.items():
        if sid not in stations:
            continue
        tech = bool(r.get("technical_tunnel")) or any(
            w in json.dumps(r, ensure_ascii=False).lower() for w in TECH_KEYS)
        for target in _as_list(_pick(r, LINK_KEYS, [])):
            tid = str(target if not isinstance(target, dict)
                      else (target.get("to") or target.get("id") or ""))
            if tid not in stations:
                match = next((k for k in stations
                              if _norm(k) == _norm(tid) or _norm(stations[k]["name"]) == _norm(tid)), None)
                if not match:
                    continue
                tid = match
            if tid == sid:
                continue
            kind = "tech" if tech else "tunnel"
            if stations[sid]["surface"] or stations[tid]["surface"]:
                kind = "surface"
            key = tuple(sorted((sid, tid))) + (kind,)
            if key in seen:
                continue
            seen.add(key)
            stations[sid]["links"].append({"to": tid, "kind": kind})
            stations[tid]["links"].append({"to": sid, "kind": kind})

    if not stations:
        return {"ok": False, "error": "Станции не найдены в config/stations.json",
                "stations": [], "lines": []}

    # линии
    line_names = []
    for s in stations.values():
        if s["line"] not in line_names:
            line_names.append(s["line"])
    lines = [{"id": f"L{i}", "name": n, "color": LINE_PALETTE[i % len(LINE_PALETTE)]}
             for i, n in enumerate(line_names)]
    lid = {n: l["id"] for n, l in zip(line_names, lines)}
    for s in stations.values():
        s["line_id"] = lid[s["line"]]

    _layout(stations, lines)
    graph = {"ok": True, "stations": list(stations.values()), "lines": lines,
             "bounds": {"w": 1000, "h": 700}, "generated": now}
    _CACHE.update(ts=now, graph=graph)
    log.info("Схема собрана: %d станций, %d линий, %d связей",
             len(stations), len(lines), sum(len(s["links"]) for s in stations.values()) // 2)
    return graph


async def graph_async(force=False):
    """Единственная точка входа из корутин: тяжёлая сборка вне event loop."""
    global _FORCE_TS
    if force:
        now = time.time()
        if now - _FORCE_TS < FORCE_COOLDOWN:
            force = False
        else:
            _FORCE_TS = now
    if not force and _CACHE["graph"] and time.time() - _CACHE["ts"] < CACHE_TTL:
        return _CACHE["graph"]
    async with _BUILD_LOCK:
        if not force and _CACHE["graph"] and time.time() - _CACHE["ts"] < CACHE_TTL:
            return _CACHE["graph"]
        return await asyncio.to_thread(build_graph, force)


def _layout(stations, lines):
    ids = list(stations)
    rnd = random.Random(44)
    by_line = {}
    for s in stations.values():
        by_line.setdefault(s["line_id"], []).append(s["id"])
    pos = {}
    for i, l in enumerate(lines):
        ang = (i / max(1, len(lines))) * math.pi * 2
        dx, dy = math.cos(ang), math.sin(ang)
        members = by_line.get(l["id"], [])
        ordered = []
        pool = set(members)
        while pool:
            start = min(pool, key=lambda k: (
                len([x for x in stations[k]["links"] if x["to"] in pool]), k))
            chain = [start]
            pool.discard(start)
            while True:
                nxt = next((x["to"] for x in stations[chain[-1]]["links"] if x["to"] in pool), None)
                if not nxt:
                    break
                chain.append(nxt)
                pool.discard(nxt)
            ordered += chain
        n = len(ordered)
        for j, sid in enumerate(ordered):
            t = (j - (n - 1) / 2) * 92
            pos[sid] = [500 + dx * t + rnd.uniform(-14, 14), 350 + dy * t + rnd.uniform(-14, 14)]

    edges = [(a, b["to"]) for a, s in stations.items() for b in s["links"] if a < b["to"]]
    for _ in range(max(20, LAYOUT_ITERATIONS)):
        force = {k: [0.0, 0.0] for k in ids}
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                d2 = dx * dx + dy * dy + 0.01
                if d2 > 260000:
                    continue
                f = 26000.0 / d2
                d = math.sqrt(d2)
                force[a][0] += dx / d * f
                force[a][1] += dy / d * f
                force[b][0] -= dx / d * f
                force[b][1] -= dy / d * f
        for a, b in edges:
            dx = pos[b][0] - pos[a][0]
            dy = pos[b][1] - pos[a][1]
            d = math.hypot(dx, dy) or 0.01
            f = (d - 105) * 0.045
            force[a][0] += dx / d * f
            force[a][1] += dy / d * f
            force[b][0] -= dx / d * f
            force[b][1] -= dy / d * f
        for l in lines:
            mem = by_line.get(l["id"], [])
            if len(mem) < 3:
                continue
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

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sx = 880 / max(1.0, maxx - minx)
    sy = 580 / max(1.0, maxy - miny)
    for sid, s in stations.items():
        s["x"] = round(60 + (pos[sid][0] - minx) * sx, 2)
        s["y"] = round(60 + (pos[sid][1] - miny) * sy, 2)


def find_station(graph, key):
    if not key or not graph:
        return None
    k = _norm(key)
    if not k:
        return None
    for s in graph.get("stations", []):
        if _norm(s["id"]) == k or _norm(s["name"]) == k:
            return s
    for s in graph.get("stations", []):
        if k in _norm(s["id"]) or k in _norm(s["name"]):
            return s
    return None


def route(graph, a, b):
    ids = {s["id"]: s for s in graph.get("stations", [])}
    if a not in ids or b not in ids:
        return []
    dist = {a: 0.0}
    prev = {}
    q = [(0.0, a)]
    while q:
        d, cur = heapq.heappop(q)
        if cur == b:
            break
        if d > dist.get(cur, 1e9):
            continue
        for l in ids[cur]["links"]:
            t = l["to"]
            if t not in ids:
                continue
            w = 1.0 + ids[t]["danger"] * 0.45 + (1.2 if l["kind"] == "surface" else 0.0)
            nd = d + w
            if nd < dist.get(t, 1e9):
                dist[t] = nd
                prev[t] = cur
                heapq.heappush(q, (nd, t))
    if b not in prev and a != b:
        return []
    path = [b]
    while path[-1] != a:
        path.append(prev[path[-1]])
    return list(reversed(path))


async def payload(session, force=False):
    from func.game_manager import game_manager
    g = await graph_async(force)
    p = game_manager.get_player(session.user.id)
    loc = getattr(p, "location", None)
    here = find_station(g, loc) if loc else None
    online = []
    if session.hub.world:
        for uid, info in session.hub.world.online().items():
            st = find_station(g, info.get("location"))
            online.append({"id": uid, "name": info.get("name"), "login": info.get("login"),
                           "station": st["id"] if st else None,
                           "location": info.get("location"),
                           "alive": info.get("alive", True)})
    return {
        "ok": g.get("ok", False), "error": g.get("error"),
        "stations": g.get("stations", []), "lines": g.get("lines", []),
        "bounds": g.get("bounds", {"w": 1000, "h": 700}),
        "me": {
            "id": session.user.id, "station": here["id"] if here else None,
            "location": loc, "alive": bool(getattr(p, "is_alive", True)) if p else False,
            "has_character": p is not None,
        },
        "online": online,
    }


# ---------- переход ----------
def _unlocked(session, method):
    """Безлоковый вариант ввода: нужен, когда session.lock уже захвачен нами.
    Требует command_unlocked/click_unlocked в bridge.Session."""
    fn = getattr(session, method + "_unlocked", None)
    return fn if callable(fn) else getattr(session, method)


async def step_move(session, target, _locked=False):
    """Один переход — через штатное /move и кнопки игры, без обхода её логики.

    _locked=True означает, что вызывающий уже держит session.lock.
    """
    from func.game_manager import game_manager
    from discord_shim import COMMANDS, Select

    cmd = _unlocked(session, "command")
    click = _unlocked(session, "click")

    g = await graph_async()
    dest = find_station(g, target)
    p = game_manager.get_player(session.user.id)
    if p is None:
        return {"ok": False, "reason": "Нет персонажа — /start"}
    if not getattr(p, "is_alive", True):
        return {"ok": False, "reason": "Персонаж мёртв"}
    if dest is None:
        return {"ok": False, "reason": "Станция не найдена на схеме"}

    before = getattr(p, "location", None)
    here = find_station(g, before)
    if here and here["id"] == dest["id"]:
        return {"ok": True, "moved": False, "arrived": True,
                "station": dest["id"], "reason": "Уже на месте"}
    if here and dest["id"] not in [l["to"] for l in here["links"]]:
        return {"ok": False, "reason": "Нет прямого перехода — иди по маршруту по шагам"}

    # боевые/спящие состояния проверяет сама игра, но незачем слать команду вслепую
    if getattr(p, "is_sleeping", False):
        return {"ok": False, "reason": "Персонаж спит — проснись через /menu"}
    with contextlib.suppress(Exception):
        from func.combat.manager import combat_manager
        from func.combat.pvp_manager import pvp_manager
        if combat_manager.get_combat(session.user.id) or pvp_manager.is_user_in_combat(session.user.id):
            return {"ok": False, "reason": "Персонаж в бою — переход недоступен"}

    names = {dest["name"], dest["id"]}
    meta = COMMANDS.get("move")
    if meta and meta["params"]:
        with contextlib.suppress(Exception):
            await cmd("move", **{meta["params"][0]: dest["id"]})
        if _norm(getattr(p, "location", None)) != _norm(before):
            return _result(g, p, before, dest)

    # открываем меню переходов штатным путём: /menu -> «Переместиться»
    await cmd("menu")
    view = session.active_view()
    if view is not None:
        btn = next((i for i in view.children
                    if "перемест" in _norm(getattr(i, "label", ""))), None)
        if btn is not None and not getattr(btn, "disabled", False):
            await click(view.id, btn.custom_id)

    for _ in range(6):
        view = session.active_view()
        if view is None:
            break
        hit = None
        for item in view.children:
            if getattr(item, "disabled", False):
                continue
            if isinstance(item, Select):
                opt = next((o for o in item.options
                            if any(_norm(n) and _norm(n) in _norm(o.label) for n in names)
                            or any(_norm(n) == _norm(o.value) for n in names)), None)
                if opt:
                    hit = (item, [opt.value])
                    break
            else:
                cid = _norm(getattr(item, "custom_id", ""))
                lbl = _norm(getattr(item, "label", ""))
                if cid == _norm("move_" + dest["id"]) or (
                        lbl and any(_norm(n) in lbl for n in names if _norm(n))):
                    hit = (item, None)
                    break
        if hit:
            item, values = hit
            await click(view.id, item.custom_id, values)
            break
        nxt = next((i for i in view.children
                    if not getattr(i, "disabled", False)
                    and any(w in _norm(getattr(i, "label", ""))
                            for w in ("далее", "ещё", "еще", "вперёд", "вперед", "след"))), None)
        if nxt is None:
            break
        await click(view.id, nxt.custom_id)

    if _norm(getattr(p, "location", None)) == _norm(before):
        return {"ok": False, "moved": False, "station": here["id"] if here else None,
                "reason": "Переход не выполнен: игра не приняла команду "
                          "(выносливость, закрытая станция, событие или бой)"}
    return _result(g, p, before, dest)


def _result(g, p, before, dest):
    now = getattr(p, "location", None)
    st = find_station(g, now)
    return {
        "ok": True, "moved": True, "arrived": bool(st and st["id"] == dest["id"]),
        "from": before, "location": now, "station": st["id"] if st else None,
        "alive": bool(getattr(p, "is_alive", True)),
    }


async def _emit_step(session, res):
    hub = session.hub
    if hub is None:
        return
    await hub.emit_to(session.user.id, {"type": "map_step", **res})
    if hub.world:
        await hub.world.push(session, force=True)


async def step_move_locked(session, target):
    """Вызывается из ws_handler: весь переход под одним замком сессии."""
    if not isinstance(target, str) or not target or len(target) > 128:
        res = {"ok": False, "reason": "Некорректная станция"}
    else:
        try:
            async with session.lock:
                res = await step_move(session, target, _locked=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка в map_move")
            res = {"ok": False, "reason": "Внутренняя ошибка перехода"}
    await _emit_step(session, res)
    return res


# ---------- HTTP / WS ----------
def _session_of(request):
    """Без импорта app: ссылку кладёт make_app(). Фолбэк — на случай старого запуска."""
    fn = request.app.get("session_of")
    if callable(fn):
        return fn(request)
    from app import _session as fallback
    return fallback(request)


async def api_map_handler(request):
    """HTTP GET /api/map — данные схемы для map.js."""
    s = _session_of(request)
    if s is None:
        return web.json_response({"ok": False, "error": "Требуется вход"}, status=401)
    force = request.query.get("force") == "1"
    if force and not s.user.guild_permissions.administrator:
        force = False                      # пересборка графа — только для админа
    try:
        return web.json_response(await payload(s, force=force))
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Ошибка в /api/map")
        return web.json_response({"ok": False, "error": "Не удалось собрать схему метро"}, status=500)


async def ws_map_move_handler(session, data):
    """Совместимость: {type:'map_move', to:'station_id'}."""
    return await step_move_locked(session, (data or {}).get("to"))


def setup(app):
    """Регистрирует маршруты карты в aiohttp приложении."""
    app.router.add_get("/api/map", api_map_handler)