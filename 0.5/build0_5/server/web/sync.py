# -*- coding: utf-8 -*-
"""Синхронизация мира между игроками: присутствие, соседи по станции, непрочитанное,
автообновление экранов у тех, кого затронуло чужое действие."""
from __future__ import annotations
import asyncio, hashlib, json, logging, time

log = logging.getLogger("web.sync")
TICK = 2.0

def _pinfo(uid, session=None):
    from func.game_manager import game_manager
    p = game_manager.get_player(uid)
    name = getattr(p, "name", None) or (session.user.name if session else str(uid))
    return {"id": uid, "name": name,
            "login": session.user.name if session else name,
            "location": getattr(p, "location", None) or "—",
            "alive": bool(getattr(p, "is_alive", True)),
            "admin": bool(session.user.guild_permissions.administrator) if session else False,
            "exists": p is not None}

class World:
    def __init__(self, hub, messenger=None, server_info=None):
        self.hub = hub; self.messenger = messenger; self.server_info = server_info or {}
        self._hash = {}; self._task = None

    def online(self):
        out = {}
        for uid, s in self.hub.sessions.items():
            if s.sinks: out[uid] = _pinfo(uid, s)
        return out

    def snapshot(self, session):
        on = self.online()
        me = on.get(session.user.id) or _pinfo(session.user.id, session)
        nearby = [v for k, v in on.items()
                  if k != session.user.id and v["location"] == me["location"] and v["location"] != "—"]
        unread = self.messenger.unread(session.user.id) if self.messenger else {"dm": 0, "mail": 0, "requests": 0}
        return {"type": "world", "me": me, "online": list(on.values()), "nearby": nearby,
                "unread": unread, "server": self.server_info, "ts": time.time()}

    async def push(self, session, force=False):
        if not session.sinks: return
        snap = self.snapshot(session)
        key = json.dumps({k: v for k, v in snap.items() if k != "ts"}, sort_keys=True, ensure_ascii=False)
        h = hashlib.md5(key.encode()).hexdigest()
        if not force and self._hash.get(session.user.id) == h: return
        self._hash[session.user.id] = h
        await session.emit(snap)

    async def touch(self, actor_id=None, propagate=True):
        """Присутствие обновляем всем. Экран трогаем только у противника в PvP:
        рассылки в канал (actor_id=None) и бой с мутантами не вызывают обновлений."""
        on = self.online()
        actor = self.hub.sessions.get(actor_id) if actor_id is not None else None
        aloc = (on.get(actor_id) or {}).get("location")
        actor_combat = bool(actor and actor.combat_view is not None)
        for uid, s in list(self.hub.sessions.items()):
            if not s.sinks: continue
            await self.push(s)
            if not propagate or actor is None or uid == actor_id: continue
            if not actor_combat or s.combat_view is None: continue
            if aloc is None or (on.get(uid) or {}).get("location") != aloc: continue
            s.needs_refresh = True

    async def loop(self):
        while True:
            try:
                await asyncio.sleep(TICK)
                for uid, s in list(self.hub.sessions.items()):
                    if not s.sinks: continue
                    await self.push(s)
                    if s.needs_refresh and time.time() - s.last_seen > 0.7:
                        s.needs_refresh = False
                        try: await s.refresh()
                        except Exception: log.exception("refresh %s", uid)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("world loop")

    def start(self):
        self._task = asyncio.ensure_future(self.loop()); return self._task

    def stop(self):
        if self._task: self._task.cancel()