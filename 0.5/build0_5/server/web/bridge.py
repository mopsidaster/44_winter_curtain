# -*- coding: utf-8 -*-
"""bridge: Session (игрок: экраны, View/Modal, очередь операций) + Hub (все игроки).
Поддерживает несколько устройств на аккаунт и синхронизацию между игроками."""
from __future__ import annotations
import asyncio, inspect, logging, time, traceback
from discord_shim import (User, Message, TextChannel, Interaction, Client, Embed, View, Modal,
                          Select, Choice, COMMANDS, nid, GAPS)

log = logging.getLogger("web"); KEEP_SCREENS = 14
READONLY = {"menu", "map", "status", "leaderboard", "faction", "faction_info", "brigada view"}
REFRESH_HOOKS = ("refresh", "update_view", "update_message", "redraw", "rebuild", "_refresh", "_update")

def _embeds(embed, embeds):
    out = []
    if embed is not None: out.append(embed)
    if embeds: out.extend(embeds or [])
    return [e.to_dict() if isinstance(e, Embed) else dict(e) for e in out]

class Session:
    def __init__(self, hub, user_id, username, is_admin=False):
        self.hub = hub; self.user = User(user_id, username, is_admin); self.channel = hub.channel
        self.client = hub.bot; self.views = {}; self.modals = {}; self.screens = {}; self.order = []
        self.ops = []; self.lock = asyncio.Lock(); self.sinks = []; self.last_seen = time.time()
        self.last_cmd = None; self.combat_view = None; self.needs_refresh = False
        self._silent = False; self._last_refresh = 0.0

    # ---------- транспорт ----------
    def add_sink(self, fn):
        if fn not in self.sinks: self.sinks.append(fn)
    def remove_sink(self, fn):
        if fn in self.sinks: self.sinks.remove(fn)
    @property
    def sink(self): return self.sinks[0] if self.sinks else None
    @sink.setter
    def sink(self, fn):
        self.sinks = [fn] if fn else []
    async def emit(self, payload):
        for fn in list(self.sinks):
            try: await fn(payload)
            except Exception: self.remove_sink(fn)
    async def flush(self):
        if self.ops and self.sinks:
            ops, self.ops = self.ops, []
            await self.emit({"type": "ops", "ops": ops})
    def drain(self):
        ops, self.ops = self.ops, []; return ops
    async def push(self, op):
        self.ops.append(op); await self.flush()

    # ---------- экраны ----------
    def last_screen(self):
        for mid in reversed(self.order):
            if mid in self.screens: return mid
        return None
    def screen_of_view(self, vid):
        return next((m for m, s in self.screens.items() if s.get("view_id") == vid), None)
    def active_view(self):
        for mid in reversed(self.order):
            s = self.screens.get(mid)
            if s and s.get("view_id"):
                v = self.views.get(s["view_id"])
                if v is not None and not v.is_finished(): return v
        return None
    def _pack(self, content, embed, embeds, view, ephemeral):
        return {"content": content, "embeds": _embeds(embed, embeds), "ephemeral": bool(ephemeral),
                "view": view.to_dict() if isinstance(view, View) else None, "ts": time.time()}
    def _remember_view(self, view, mid):
        if isinstance(view, View):
            self.views[view.id] = view; view.message = Message(self, mid)
            if any(k in type(view).__name__.lower() for k in ("combat", "pvp")):
                self.combat_view = view
            else:
                self.combat_view = None      # бой закончился — флаг снимаем
            return view.id
        return None
    async def op_send(self, content=None, *, embed=None, embeds=None, view=None, ephemeral=False, **kw):
        mid = nid("m"); d = self._pack(content, embed, embeds, view, ephemeral)
        d["id"] = mid; d["view_id"] = self._remember_view(view, mid)
        self.screens[mid] = d; self.order.append(mid)
        while len(self.order) > KEEP_SCREENS:
            old = self.order.pop(0); self.screens.pop(old, None); self.ops.append({"op": "drop", "id": old})
        self.ops.append({"op": "send", **d}); return Message(self, mid)
    async def op_edit(self, mid, **kw):
        cur = self.screens.get(mid)
        if cur is None:
            return await self.op_send(kw.get("content"), embed=kw.get("embed"),
                                      embeds=kw.get("embeds"), view=kw.get("view"))
        patch = {"op": "edit", "id": mid, "ts": time.time()}
        if "content" in kw: cur["content"] = kw["content"]; patch["content"] = kw["content"]
        if "embed" in kw or "embeds" in kw:
            cur["embeds"] = _embeds(kw.get("embed"), kw.get("embeds")); patch["embeds"] = cur["embeds"]
        if "view" in kw:
            v = kw["view"]; cur["view"] = v.to_dict() if isinstance(v, View) else None
            cur["view_id"] = self._remember_view(v, mid) if v is not None else None
            patch["view"] = cur["view"]; patch["view_id"] = cur["view_id"]
        cur["ts"] = patch["ts"]; self.ops.append(patch); return Message(self, mid)
    async def op_delete(self, mid):
        self.screens.pop(mid, None)
        if mid in self.order: self.order.remove(mid)
        self.ops.append({"op": "delete", "id": mid})
    async def op_modal(self, modal):
        self.modals[modal.custom_id] = modal
        self.ops.append({"op": "modal", **modal.to_dict()})
    async def toast(self, text, kind="info", trace=None):
        op = {"op": "toast", "text": str(text), "kind": kind}
        if trace: op["trace"] = trace
        self.ops.append(op)
    async def fail(self, where, exc):
        tb = traceback.format_exc()
        log.error("%s: %s\n%s", where, exc, tb)
        await self.toast(f"{where}: {type(exc).__name__}: {exc}", "error", tb)
        if GAPS: await self.toast("Не реализовано в адаптере: " + ", ".join(GAPS[-6:]), "warn")

    def snapshot(self):
        return {"type": "snapshot", "user": {"id": self.user.id, "name": self.user.name,
                                             "admin": self.user.guild_permissions.administrator},
                "screens": [self.screens[m] for m in self.order if m in self.screens],
                "commands": [{"name": k, "description": v["description"], "params": v["params"]}
                             for k, v in COMMANDS.items()]}

    # ---------- ввод ----------
    async def _after(self):
        await self.flush()
        if self.hub.world: await self.hub.world.touch(self.user.id, propagate=not self._silent)

    async def click(self, view_id, item_id, values=None):
        async with self.lock:
            self.last_seen = time.time(); view = self.views.get(view_id)
            if view is None:
                await self.toast("Меню устарело. Открой /menu заново.", "warn"); return await self._after()
            if view.is_finished():
                try: await view.on_timeout()
                except Exception as e: await self.fail("on_timeout", e)
                await self.toast("Время меню истекло. Открой /menu заново.", "warn"); return await self._after()
            item = next((i for i in view.children if i.custom_id == item_id), None)
            if item is None or item.disabled:
                await self.toast("Кнопка недоступна.", "warn"); return await self._after()
            mid = self.screen_of_view(view_id) or self.last_screen()
            it = Interaction(self, message_id=mid, client=self.client)
            if isinstance(item, Select):
                item.values = list(values or []); it.data = {"values": item.values, "component_type": 3}
            try:
                if await view.interaction_check(it): await item.callback(it)
            except Exception as e:
                await self.fail("Кнопка «%s»" % (getattr(item, "label", None) or item_id), e)
            await self._after()

    async def submit(self, modal_id, values):
        async with self.lock:
            self.last_seen = time.time()
            modal = self.modals.get(modal_id)
            if modal is None:
                await self.toast("Окно уже закрыто. Повтори действие.", "warn"); return await self._after()
            for f in modal.children:
                v = str(values.get(f.custom_id) or values.get(f.label) or "").strip()
                if f.required and not v:
                    await self.toast(f"Заполни поле «{f.label}».", "warn"); return await self._after()
                if f.min_length and len(v) < f.min_length:
                    await self.toast(f"«{f.label}»: минимум {f.min_length} симв.", "warn"); return await self._after()
                f.value = v[:f.max_length] if f.max_length else v
            self.modals.pop(modal_id, None)
            it = Interaction(self, client=self.client); before = len(self.ops)
            try:
                if await modal.interaction_check(it): await modal.on_submit(it)
            except Exception as e:
                await self.fail("Окно «%s»" % modal.title, e)
            if len(self.ops) == before: self.ops.append({"op": "modal_close", "id": modal_id})
            await self._after()

    async def command(self, name, **params):
        async with self.lock:
            self.last_seen = time.time()
            cmd = COMMANDS.get(name)
            if not cmd:
                await self.toast(f"Нет команды /{name}", "warn"); return await self._after()
            for p in cmd.get("choice_params", []):
                if p in params and not isinstance(params[p], Choice):
                    params[p] = Choice(name=str(params[p]), value=params[p])
            if name in READONLY: self.last_cmd = (name, dict(params))
            it = Interaction(self, client=self.client)
            try:
                await cmd["callback"](it, **params)
            except TypeError as e:
                if "argument" in str(e):
                    await self.toast(f"/{name}: не хватает параметров — {', '.join(cmd['params']) or 'нет'}", "warn")
                else: await self.fail(f"/{name}", e)
            except Exception as e:
                await self.fail(f"/{name}", e)
            await self._after()

    # ---------- безлоковые варианты (замок держит вызывающий) ----------
    async def click_unlocked(self, view_id, item_id, values=None):
        self.last_seen = time.time(); view = self.views.get(view_id)
        if view is None:
            await self.toast("Меню устарело. Открой /menu заново.", "warn"); return await self._after()
        if view.is_finished():
            try: await view.on_timeout()
            except Exception as e: await self.fail("on_timeout", e)
            await self.toast("Время меню истекло. Открой /menu заново.", "warn"); return await self._after()
        item = next((i for i in view.children if i.custom_id == item_id), None)
        if item is None or item.disabled:
            await self.toast("Кнопка недоступна.", "warn"); return await self._after()
        mid = self.screen_of_view(view_id) or self.last_screen()
        it = Interaction(self, message_id=mid, client=self.client)
        if isinstance(item, Select):
            item.values = list(values or []); it.data = {"values": item.values, "component_type": 3}
        try:
            if await view.interaction_check(it): await item.callback(it)
        except Exception as e:
            await self.fail("Кнопка «%s»" % (getattr(item, "label", None) or item_id), e)
        await self._after()

    async def command_unlocked(self, name, **params):
        self.last_seen = time.time()
        cmd = COMMANDS.get(name)
        if not cmd:
            await self.toast(f"Нет команды /{name}", "warn"); return await self._after()
        for p in cmd.get("choice_params", []):
            if p in params and not isinstance(params[p], Choice):
                params[p] = Choice(name=str(params[p]), value=params[p])
        if name in READONLY: self.last_cmd = (name, dict(params))
        it = Interaction(self, client=self.client)
        try:
            await cmd["callback"](it, **params)
        except TypeError as e:
            if "argument" in str(e):
                await self.toast(f"/{name}: не хватает параметров — {', '.join(cmd['params']) or 'нет'}", "warn")
            else: await self.fail(f"/{name}", e)
        except Exception as e:
            await self.fail(f"/{name}", e)
        await self._after()

    async def refresh(self):
        """Тихое обновление после чужого действия. Боевой экран никогда не
        подменяется меню: сначала пробуем хуки самой View, иначе молчим."""
        now = time.time()
        if now - self._last_refresh < 1.5 or not self.sinks: return
        self._last_refresh = now; self._silent = True
        try:
            v = self.active_view()
            in_combat = v is not None and any(k in type(v).__name__.lower() for k in ("combat", "pvp"))
            if v is not None:
                for hook in REFRESH_HOOKS:
                    fn = getattr(v, hook, None)
                    if callable(fn):
                        it = Interaction(self, message_id=self.screen_of_view(v.id), client=self.client)
                        try:
                            res = fn(it)
                            if inspect.isawaitable(res): await res
                            return
                        except Exception:
                            log.debug("refresh hook %s failed", hook, exc_info=True)
            if in_combat:
                return
            if self.last_cmd and time.time() - self.last_seen > 4.0:
                name, params = self.last_cmd
                await self.command(name, **params)
        finally:
            self._silent = False
            await self.flush()

class Hub:
    def __init__(self):
        self.bot = Client(); self.bot._hub = self
        self.channel = TextChannel(self, 0, "game"); self.sessions = {}
        self.world = None; self.messenger = None

    def session(self, user_id, username, is_admin=False):
        s = self.sessions.get(user_id)
        if s is None: s = Session(self, user_id, username, is_admin); self.sessions[user_id] = s
        return s

    def online_ids(self):
        return [uid for uid, s in self.sessions.items() if s.sinks]

    async def emit_to(self, user_id, payload):
        s = self.sessions.get(user_id)
        if s and s.sinks: await s.emit(payload); return True
        return False

    async def broadcast(self, content=None, **kw):
        first = None
        for s in list(self.sessions.values()):
            if not s.sinks: continue
            m = await s.op_send(content, **kw); first = first or m; await s.flush()
        if self.world: await self.world.touch(None)
        return first