# -*- coding: utf-8 -*-
"""REST /api/event/state — единственный источник правды о глобальных ивентах.
Самодостаточен: не требует хелперов в global_events.py. Отдаёт boot-id процесса,
чтобы клиент детектил перезапуск сервера и не врал "LIVE"."""
from __future__ import annotations

import asyncio
import time

from aiohttp import web

BOOT = time.time()

_ZONE_ATTRS = {
    "frost": ("frost_station", "frost_connections"),
    "chemical_cloud": ("chemical_cloud_station", "chemical_cloud_connections"),
    "heating_failure": ("heating_station", None),
    "raider_raid": (None, "raider_raid_stations"),
    "station_celebration": ("celebration_station", None),
    "stalker_workshop": ("workshop_station", None),
    "mutant_breach": ("breach_station", None),
}


def _zones(gm, eid):
    single, many = _ZONE_ATTRS.get(eid, (None, None))
    out = []
    if single:
        v = getattr(gm, single, None)
        if v:
            out.append(v)
    if many:
        out.extend(list(getattr(gm, many, []) or []))
    return [s for s in out if s]


def _names(ids):
    try:
        from func.map_data import MAP_DATA
        st = MAP_DATA.get("станции", {})
        return [st[s]["name"] for s in ids if s in st]
    except Exception:
        return list(ids)


def install(app):
    async def event_state(request):
        s = request.app["session_of"](request)
        if s is None:
            return web.json_response({"ok": False, "error": "Требуется вход"}, status=401)
        base = {"ok": True, "boot": BOOT, "active": None, "warning": ""}
        try:
            from func import global_events as ge
            from func.game_manager import game_manager
        except Exception as e:
            base["warning"] = f"global_events недоступен: {e}"
            return web.json_response(base)
        st = getattr(ge, "current_event", None)
        ev = getattr(st, "event", None) if st else None
        if not st or not st.active or not ev:
            return web.json_response(base)
        total = int(ev.get("duration", 0)) * 60
        try:
            elapsed = asyncio.get_running_loop().time() - st.start_time
        except Exception:
            elapsed = 0
        left = max(0, total - elapsed)
        zones = _zones(game_manager, ev.get("id", ""))
        base["active"] = {
            "type": "global_event", "action": "state",
            "id": ev.get("id", ""), "kind": ev.get("type", "neutral"),
            "title": str(ev.get("text", "")).split("\n")[0].replace("**", ""),
            "text": ev.get("text", ""), "description": ev.get("description", ""),
            "duration": total, "remaining": round(left),
            "stations": zones, "station_names": _names(zones),
            "ts": time.time() - elapsed,
        }
        return web.json_response(base)

    app.router.add_get("/api/event/state", event_state)