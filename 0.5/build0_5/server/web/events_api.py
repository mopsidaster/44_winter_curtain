# -*- coding: utf-8 -*-
"""REST для панели глобальных ивентов: текущее состояние (для зашедших в середине)."""
from __future__ import annotations

import asyncio
from aiohttp import web


def install(app):
    async def event_state(request):
        s = request.app["session_of"](request)
        if s is None:
            return web.json_response({"ok": False, "error": "Требуется вход"}, status=401)
        try:
            from func import global_events as ge
            from func.game_manager import game_manager
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Ивенты недоступны: {e}"}, status=500)

        st = ge.current_event
        if not st.active or not st.event:
            return web.json_response({"ok": True, "active": None})

        ev = st.event
        total = ev["duration"] * 60
        left = max(0, total - (asyncio.get_running_loop().time() - st.start_time))
        return web.json_response({"ok": True, "active": ge.event_payload(game_manager, ev, "state", remaining=left)})

    app.router.add_get("/api/event/state", event_state)