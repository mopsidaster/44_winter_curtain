# -*- coding: utf-8 -*-
"""Схема метро: только чтение. Отдаёт реальные данные станций для справочной карты.
Никаких переходов — перемещение живёт в игре (/move и меню)."""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import math
import os
import re
import time

from aiohttp import web

log = logging.getLogger("web.map")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_CACHE = {"ts": 0.0, "graph": None}
_LOCK = asyncio.Lock()
CACHE_TTL = 300.0

STEP_X, STEP_Y = 164, 196
PAD_X, PAD_T, PAD_B = 120, 76, 92

FACTION_UI = {
    "loners": ("Одиночки", "#9aa5ad"),
    "bandits": ("Бандиты", "#ff4d3d"),
    "antiquars": ("Антиквары", "#ffd23f"),
    "gess": ("Севастопольская ГЭС", "#4aa8ff"),
    "yasenevo": ("Ясеневская Община", "#66ff99"),
    "gutagi": ("Гутаги", "#b9a06a"),
}


def _norm(s):
    return re.sub(r"[^a-zа-я0-9]+", "", str(s or "").lower().replace("ё", "е"))


def _stations_raw():
    path = os.path.join(BASE, "config", "stations.json")
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    for wrap in ("станции", "stations", "data", "map"):
        if isinstance(data, dict) and isinstance(data.get(wrap), dict):
            return data[wrap], data
    return {}, data


def _npc_fn():
    """get_npcs_on_station живёт в func.factions — раньше искали не там."""
    for modname in ("func.factions", "func", "func.station_utils"):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        fn = getattr(mod, "get_npcs_on_station", None)
        if callable(fn):
            return fn
    return None


def _types_of(raw):
    out = []
    for t in (raw.get("types") or []):
        if t not in out:
            out.append(str(t))
    t = raw.get("type")
    if t and t not in out:
        out.append(str(t))
    return out


def build_graph(force=False):
    now = time.time()
    if not force and _CACHE["graph"] and now - _CACHE["ts"] < CACHE_TTL:
        return _CACHE["graph"]

    raw, root = _stations_raw()
    if not raw:
        return {"ok": False, "error": "Станции не найдены в config/stations.json", "stations": [], "lines": []}

    npcs_on = _npc_fn()
    tunnels = root.get("technical_tunnels", {}) or {}
    stations = {}

    for sid, r in raw.items():
        types = _types_of(r)
        surface = ("на_поверхности" in types) or bool(r.get("surface_lock"))
        fid = r.get("faction") or ""
        fname, fcolor = FACTION_UI.get(fid, (fid, ""))
        npc_names = []
        if npcs_on:
            try:
                for n in (npcs_on(sid) or []):
                    npc_names.append(str(n.get("name") or n.get("id") or "NPC"))
            except Exception:
                log.debug("get_npcs_on_station(%s) упал", sid, exc_info=True)
        tt = r.get("technical_tunnel") or ""
        stations[sid] = {
            "id": sid,
            "name": str(r.get("name") or sid),
            "emoji": str(r.get("emoji") or ""),
            "line": str(r.get("line") or "Тоннели"),
            "danger": int(r.get("danger") or 0),
            "types": types,
            "surface": surface,
            "ruined": bool(r.get("ruined")),
            "hostile": bool(r.get("hostile")),
            "blocked": bool(r.get("blocked")),
            "faction_lock": bool(r.get("faction_lock")),
            "faction": fid,
            "faction_name": fname,
            "faction_color": fcolor,
            "transfer": str(r.get("transfer") or ""),
            "tunnel": str(tt),
            "tunnel_name": str((tunnels.get(tt) or {}).get("name") or ""),
            "desc": str(r.get("description") or "")[:600],
            "npc": npc_names,
            "links": [],
        }

    seen = set()
    for sid, r in raw.items():
        for target in (r.get("connections") or []):
            tid = str(target)
            if tid not in stations or tid == sid:
                continue
            key = tuple(sorted((sid, tid)))
            if key in seen:
                continue
            seen.add(key)
            a, b = stations[sid], stations[tid]
            kind = "tunnel"
            if a["surface"] or b["surface"]:
                kind = "surface"
            elif a["tunnel"] and a["tunnel"] == b["tunnel"]:
                kind = "tech"
            a["links"].append({"to": tid, "kind": kind})
            b["links"].append({"to": sid, "kind": kind})

    # порядок внутри линии — обходом по связям от концевого узла
    groups = {}
    for s in stations.values():
        groups.setdefault(s["line"], []).append(s["id"])
    lines = sorted(groups)
    order = {}
    for ln in lines:
        pool = set(groups[ln])
        deg = lambda i: sum(1 for l in stations[i]["links"] if l["to"] in pool)
        ends = sorted(i for i in pool if deg(i) <= 1)
        start = ends[0] if ends else sorted(pool)[0]
        chain = [start]
        pool.discard(start)
        while pool:
            nxt = sorted(l["to"] for l in stations[chain[-1]]["links"] if l["to"] in pool)
            pick = nxt[0] if nxt else sorted(pool)[0]
            chain.append(pick)
            pool.discard(pick)
        order[ln] = chain

    graph = {
        "ok": True,
        "stations": list(stations.values()),
        "lines": [{"name": ln, "ids": order[ln]} for ln in lines],
        "grid": {"stepX": STEP_X, "stepY": STEP_Y, "padX": PAD_X, "padT": PAD_T, "padB": PAD_B},
        "generated": now,
    }
    _CACHE.update(ts=now, graph=graph)
    log.info("Схема собрана: %d станций, %d линий", len(stations), len(lines))
    return graph


async def graph_async(force=False):
    if not force and _CACHE["graph"] and time.time() - _CACHE["ts"] < CACHE_TTL:
        return _CACHE["graph"]
    async with _LOCK:
        if not force and _CACHE["graph"] and time.time() - _CACHE["ts"] < CACHE_TTL:
            return _CACHE["graph"]
        return await asyncio.to_thread(build_graph, force)


def find_station(graph, key):
    if not key:
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


async def payload(session):
    from func.game_manager import game_manager
    g = await graph_async()
    p = game_manager.get_player(session.user.id)
    loc = getattr(p, "location", None)
    here = find_station(g, loc) if loc else None
    online = []
    if session.hub.world:
        for uid, info in session.hub.world.online().items():
            st = find_station(g, info.get("location"))
            online.append({"id": uid, "name": info.get("name"),
                           "station": st["id"] if st else None,
                           "location": info.get("location"),
                           "alive": info.get("alive", True)})
    return {
        "ok": g.get("ok", False), "error": g.get("error"),
        "stations": g.get("stations", []), "lines": g.get("lines", []),
        "grid": g.get("grid", {}),
        "me": {"id": session.user.id, "station": here["id"] if here else None,
               "location": loc, "has_character": p is not None,
               "alive": bool(getattr(p, "is_alive", True)) if p else False},
        "online": online,
    }


async def api_map_handler(request):
    fn = request.app.get("session_of")
    s = fn(request) if callable(fn) else None
    if s is None:
        return web.json_response({"ok": False, "error": "Требуется вход"}, status=401)
    try:
        return web.json_response(await payload(s))
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Ошибка в /api/map")
        return web.json_response({"ok": False, "error": "Не удалось собрать схему метро"}, status=500)


def setup(app):
    app.router.add_get("/api/map", api_map_handler)