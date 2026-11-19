# -*- coding: utf-8 -*-
"""Бригады в вебе: HTTP-API + веб-версии команд /brigada.

Важно: setup(app) вызывается из make_app() — роутер aiohttp замораживается
до on_startup, регистрировать маршруты в bootstrap нельзя.
install_commands(app) вызывается из bootstrap ПОСЛЕ setup_social_commands.
"""
from __future__ import annotations

import asyncio
import logging
import time

from aiohttp import web

log = logging.getLogger("web.brigades")

MAX_NAME = 50
MAX_DESC = 300

FACTION_COLOR = {
    "loners": "#9aa5ad", "bandits": "#ff4d3d", "antiquars": "#ffd23f",
    "gess": "#4aa8ff", "yasenevo": "#66ff99", "gutagi": "#b9a06a",
}


# ---------- доступ к игре ----------
def _gm():
    from func.game_manager import game_manager
    return game_manager


def _bm():
    from func.social.brigade_manager import brigade_manager
    return brigade_manager


def _consts():
    from func.social.brigade import STATE_ACTIVE, STATE_NO_ACTIVE, MAX_BRIGADE_SIZE
    from func.social.brigade_manager import INVITE_TIMEOUT_SECONDS
    return STATE_ACTIVE, STATE_NO_ACTIVE, MAX_BRIGADE_SIZE, INVITE_TIMEOUT_SECONDS


def _player(uid):
    try:
        return _gm().get_player(int(uid))
    except Exception:
        return None


def _pname(uid):
    p = _player(uid)
    return getattr(p, "name", None) or str(uid)


def _loc_name(loc):
    if not loc:
        return "—"
    try:
        from func.map_data import MAP_DATA
        return (MAP_DATA["станции"].get(loc) or {}).get("name", loc)
    except Exception:
        return str(loc)


def _faction_name(fid):
    if not fid:
        return "Одиночки"
    try:
        from func.factions import get_faction_name
        return get_faction_name(fid) or fid
    except Exception:
        return fid


def _in_combat(uid):
    try:
        from func.combat.manager import combat_manager
        if combat_manager.get_combat(uid):
            return True
    except Exception:
        pass
    try:
        from func.combat.pvp_manager import pvp_manager
        if pvp_manager.is_user_in_combat(uid):
            return True
    except Exception:
        pass
    return False


def _login_of(accounts, uid):
    if not accounts:
        return None
    try:
        a = accounts.by_id(uid)
        return a["login"] if a else None
    except Exception:
        return None


def _resolve(accounts, key):
    """Позывной, имя персонажа или числовой id -> uid."""
    if key is None:
        return None
    if isinstance(key, int):
        return key if key > 0 else None
    s = str(key).strip().lstrip("@")
    if not s:
        return None
    if s.isdigit():
        v = int(s)
        return v if v > 0 else None
    if accounts:
        try:
            a = accounts.by_login(s)
            if a:
                return int(a["user_id"])
        except Exception:
            log.debug("by_login", exc_info=True)
    try:
        for p in list(getattr(_gm(), "players", {}).values()):
            if str(getattr(p, "name", "")).strip().lower() == s.lower():
                return int(p.user_id)
    except Exception:
        log.debug("resolve by name", exc_info=True)
    return None


# ---------- сериализация ----------
def _member(m, brigade, accounts, online):
    uid = m.user_id
    p = _player(uid)
    joined = getattr(m, "joined_at", None)
    return {
        "id": uid,
        "name": _pname(uid),
        "login": _login_of(accounts, uid),
        "leader": brigade.is_leader(uid),
        "location": getattr(p, "location", None),
        "location_name": _loc_name(getattr(p, "location", None)),
        "alive": bool(getattr(p, "is_alive", True)) if p else False,
        "sleeping": bool(getattr(p, "is_sleeping", False)) if p else False,
        "exists": p is not None,
        "online": uid in online,
        "joined": joined.isoformat() if hasattr(joined, "isoformat") else None,
    }


def _brigade(b, accounts, online, me_id=None):
    ACTIVE, NO_ACTIVE, MAXSZ, _ttl = _consts()
    fid = getattr(b, "faction_id", "loners") or "loners"
    members = [_member(m, b, accounts, online)
               for m in sorted(b.members, key=lambda x: x.joined_at)]
    created = getattr(b, "created_at", None)
    return {
        "id": b.brigade_id,
        "name": b.name,
        "description": b.description or "",
        "leader_id": b.leader_id,
        "leader_name": _pname(b.leader_id),
        "state": b.state,
        "active": b.is_active(),
        "state_label": "Вместе" if b.is_active() else "Расход",
        "faction": fid,
        "faction_name": _faction_name(fid),
        "faction_color": FACTION_COLOR.get(fid, "#9aa5ad"),
        "size": b.member_count(),
        "max": MAXSZ,
        "full": b.is_full(),
        "members": members,
        "mine": bool(me_id and b.has_member(me_id)),
        "i_lead": bool(me_id and b.is_leader(me_id)),
        "created": created.isoformat() if hasattr(created, "isoformat") else None,
        "states": {"active": ACTIVE, "no_active": NO_ACTIVE},
    }


def _invites_for(uid, accounts):
    bm = _bm()
    _a, _n, _m, ttl = _consts()
    out = []
    for inv in list(bm.invites.values()):
        if inv.invitee_id != uid or inv.resolved or inv.is_expired():
            continue
        b = bm.get_brigade(inv.brigade_id)
        if not b:
            continue
        out.append({
            "id": inv.invite_id,
            "brigade_id": b.brigade_id,
            "brigade_name": b.name,
            "brigade_size": b.member_count(),
            "brigade_full": b.is_full(),
            "inviter_id": inv.inviter_id,
            "inviter_name": _pname(inv.inviter_id),
            "inviter_login": _login_of(accounts, inv.inviter_id),
            "expires_in": max(0, int(ttl - (time.time() - inv.created_at))),
        })
    out.sort(key=lambda x: -x["expires_in"])
    return out


def _candidates(uid, accounts, online):
    p = _player(uid)
    if not p:
        return []
    bm = _bm()
    loc = getattr(p, "location", None)
    if not loc:
        return []
    try:
        pool = _gm().get_players_by_location(loc)
    except Exception:
        pool = [x for x in getattr(_gm(), "players", {}).values()
                if getattr(x, "location", None) == loc]
    out = []
    for other in pool:
        oid = int(other.user_id)
        if oid == uid or not getattr(other, "is_alive", True):
            continue
        if bm.is_user_in_brigade(oid):
            continue
        out.append({
            "id": oid,
            "name": getattr(other, "name", str(oid)),
            "login": _login_of(accounts, oid),
            "online": oid in online,
            "sleeping": bool(getattr(other, "is_sleeping", False)),
            "location_name": _loc_name(loc),
        })
    out.sort(key=lambda x: (not x["online"], x["name"]))
    return out


def _online_ids(app):
    try:
        return set(app["hub"].online_ids())
    except Exception:
        return set()


async def payload(app, uid):
    accounts = app.get("accounts")
    online = _online_ids(app)
    bm = _bm()
    mine = bm.get_user_brigade(uid)
    return {
        "ok": True,
        "me": {"id": uid, "name": _pname(uid), "login": _login_of(accounts, uid),
               "has_character": _player(uid) is not None},
        "mine": _brigade(mine, accounts, online, uid) if mine else None,
        "invites": _invites_for(uid, accounts),
        "candidates": _candidates(uid, accounts, online) if mine and mine.is_leader(uid) else [],
        "brigades": [_brigade(b, accounts, online, uid) for b in bm.get_all_brigades()],
        "location": _loc_name(getattr(_player(uid), "location", None)),
    }


# ---------- рассылка ----------
async def notify(app, uids, kind="changed", text=None):
    hub = app.get("hub")
    if hub is None:
        return
    seen = set()
    targets = [int(u) for u in uids if u]
    try:
        targets += list(hub.online_ids())
    except Exception:
        pass
    for uid in targets:
        if uid in seen:
            continue
        seen.add(uid)
        msg = {"type": "brigade", "kind": kind}
        if text:
            msg["text"] = text
        try:
            await hub.emit_to(uid, msg)
        except Exception:
            log.debug("brigade emit %s", uid, exc_info=True)


async def _notify_brigade(app, brigade, kind="changed", text=None, extra=()):
    await notify(app, list(brigade.get_member_ids()) + list(extra), kind, text)


# ---------- операции ----------
async def op_create(app, uid, name, description=""):
    name = ("" if name is None else str(name)).strip()
    description = ("" if description is None else str(description)).strip()
    if len(name) < 2 or len(name) > MAX_NAME:
        return {"error": f"Название от 2 до {MAX_NAME} символов"}
    if len(description) > MAX_DESC:
        return {"error": f"Описание до {MAX_DESC} символов"}
    p = _player(uid)
    if not p:
        return {"error": "Сначала создай персонажа — /start"}
    bm = _bm()
    if bm.is_user_in_brigade(uid):
        return {"error": "Ты уже в бригаде"}
    fid = "loners"
    try:
        fid = p.get_faction() or "loners"
    except Exception:
        pass
    b = await bm.create_brigade(leader_id=uid, name=name, description=description, faction_id=fid)
    log.info("[web.brigades] %s создал бригаду %s (%s)", uid, b.name, b.brigade_id)
    await _notify_brigade(app, b, "created", f"Бригада «{b.name}» создана")
    return {"ok": True, "brigade_id": b.brigade_id}


async def op_invite(app, uid, target):
    bm = _bm()
    _a, _n, _m, ttl = _consts()
    b = bm.get_user_brigade(uid)
    if not b:
        return {"error": "Ты не в бригаде"}
    if not b.is_leader(uid):
        return {"error": "Приглашать может только лидер"}
    if b.is_full():
        return {"error": "В бригаде уже 3 человека"}
    me = _player(uid)
    if not me:
        return {"error": "Сначала создай персонажа — /start"}
    tid = _resolve(app.get("accounts"), target)
    if not tid:
        return {"error": "Игрок с таким позывным не найден"}
    if tid == uid:
        return {"error": "Нельзя пригласить самого себя"}
    tp = _player(tid)
    if not tp:
        return {"error": "У этого игрока нет персонажа"}
    if not getattr(tp, "is_alive", True):
        return {"error": "Цель мертва"}
    if getattr(me, "is_sleeping", False) or getattr(tp, "is_sleeping", False):
        return {"error": "Кто-то из вас спит — проснитесь через /menu"}
    if getattr(me, "location", None) != getattr(tp, "location", None):
        return {"error": "Вы должны быть на одной станции"}
    if _in_combat(uid) or _in_combat(tid):
        return {"error": "Во время боя приглашать нельзя"}
    if bm.is_user_in_brigade(tid):
        return {"error": "Игрок уже в другой бригаде"}
    inv = bm.create_invite(b.brigade_id, uid, tid)
    if inv is None:
        return {"error": "Не удалось создать приглашение"}
    await notify(app, [tid, uid], "invite", f"{_pname(uid)} зовёт в «{b.name}»")
    return {"ok": True, "invite_id": inv.invite_id, "invitee_id": tid,
            "invitee_name": _pname(tid), "expires_in": ttl}


async def op_accept(app, uid, invite_id):
    bm = _bm()
    inv = bm.get_invite(str(invite_id or ""))
    if not inv or inv.resolved:
        return {"error": "Приглашение недействительно или истекло"}
    if inv.invitee_id != uid:
        return {"error": "Это приглашение не для тебя"}
    if bm.is_user_in_brigade(uid):
        bm.resolve_invite(inv.invite_id)
        return {"error": "Ты уже в бригаде"}
    b = bm.get_brigade(inv.brigade_id)
    if not b or b.is_full():
        bm.resolve_invite(inv.invite_id)
        return {"error": "Бригада уже полная или не существует"}
    if not await bm.add_member(b.brigade_id, uid):
        return {"error": "Не удалось вступить в бригаду"}
    bm.resolve_invite(inv.invite_id)
    log.info("[web.brigades] %s вступил в %s", uid, b.brigade_id)
    await _notify_brigade(app, b, "joined", f"{_pname(uid)} вступил в бригаду", extra=[inv.inviter_id])
    return {"ok": True, "brigade_id": b.brigade_id, "brigade_name": b.name}


async def op_decline(app, uid, invite_id):
    bm = _bm()
    inv = bm.get_invite(str(invite_id or ""))
    if not inv or inv.resolved:
        return {"error": "Приглашение недействительно или истекло"}
    if inv.invitee_id != uid:
        return {"error": "Это приглашение не для тебя"}
    bm.resolve_invite(inv.invite_id)
    b = bm.get_brigade(inv.brigade_id)
    await notify(app, [inv.inviter_id] + (list(b.get_member_ids()) if b else []),
                 "declined", f"{_pname(uid)} отказался вступить")
    return {"ok": True}


async def op_leave(app, uid):
    bm = _bm()
    b = bm.get_user_brigade(uid)
    if not b:
        return {"error": "Ты не в бригаде"}
    bid, name = b.brigade_id, b.name
    was_leader = b.is_leader(uid)
    old = list(b.get_member_ids())
    if was_leader:
        await bm.remove_member(bid, uid)
        new_leader = await bm.handle_leader_left(bid)
        if new_leader is None:
            await notify(app, old, "disbanded", f"Бригада «{name}» распущена")
            return {"ok": True, "disbanded": True}
        await notify(app, old, "leader",
                     f"{_pname(uid)} покинул бригаду. Новый лидер — {_pname(new_leader)}")
        nb = bm.get_brigade(bid)
        if nb:
            await _notify_brigade(app, nb, "changed")
        return {"ok": True, "left": True, "new_leader": new_leader}
    await bm.remove_member(bid, uid)
    await notify(app, old, "left", f"{_pname(uid)} покинул бригаду")
    return {"ok": True, "left": True}


async def op_kick(app, uid, target):
    bm = _bm()
    b = bm.get_user_brigade(uid)
    if not b:
        return {"error": "Ты не в бригаде"}
    if not b.is_leader(uid):
        return {"error": "Исключать может только лидер"}
    tid = _resolve(app.get("accounts"), target)
    if not tid:
        return {"error": "Игрок не найден"}
    if tid == uid:
        return {"error": "Себя исключить нельзя — используй «Покинуть»"}
    if not b.has_member(tid):
        return {"error": "Этого игрока нет в твоей бригаде"}
    if not await bm.remove_member(b.brigade_id, tid):
        return {"error": "Не удалось исключить"}
    await _notify_brigade(app, b, "kicked", f"{_pname(tid)} исключён из бригады", extra=[tid])
    return {"ok": True}


async def op_state(app, uid, state):
    ACTIVE, NO_ACTIVE, _m, _t = _consts()
    state = str(state or "").strip().lower()
    if state in ("active", "вместе", "together"):
        state = ACTIVE
    elif state in ("no_active", "расход", "apart"):
        state = NO_ACTIVE
    else:
        return {"error": "Состояние: «Вместе» или «Расход»"}
    bm = _bm()
    b = bm.get_user_brigade(uid)
    if not b:
        return {"error": "Ты не в бригаде"}
    if not b.is_leader(uid):
        return {"error": "Режим меняет только лидер"}
    if state == ACTIVE and b.is_active():
        return {"error": "Уже режим «Вместе»"}
    if state == NO_ACTIVE and b.is_no_active():
        return {"error": "Уже режим «Расход»"}
    if state == ACTIVE:
        loc = getattr(_player(uid), "location", None)
        for mid in b.get_member_ids():
            if mid == uid:
                continue
            mp = _player(mid)
            if not mp or getattr(mp, "location", None) != loc:
                return {"error": "Не все участники на одной станции с лидером"}
    if not await bm.set_state(b.brigade_id, state):
        return {"error": "Не удалось сменить режим"}
    label = "Вместе" if state == ACTIVE else "Расход"
    await _notify_brigade(app, b, "state", f"Режим бригады: {label}")
    return {"ok": True, "state": state, "label": label}


# ---------- HTTP ----------
def _session_of(request):
    fn = request.app.get("session_of")
    if callable(fn):
        return fn(request)
    from app import _session as fallback
    return fallback(request)


def _need(fn):
    async def wrapped(request):
        s = _session_of(request)
        if s is None:
            return web.json_response({"error": "Требуется вход"}, status=401)
        try:
            return await fn(request, s.user.id)
        except web.HTTPException:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("brigades: %s", request.path)
            return web.json_response({"error": "Внутренняя ошибка бригад"}, status=500)
    wrapped.__name__ = getattr(fn, "__name__", "brigades")
    return wrapped


async def _body(request):
    try:
        d = await request.json()
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def _reply(res):
    return web.json_response(res, status=200 if res.get("ok") else 400)


@_need
async def api_state(request, uid):
    return web.json_response(await payload(request.app, uid))


@_need
async def api_create(request, uid):
    d = await _body(request)
    return _reply(await op_create(request.app, uid, d.get("name"), d.get("description")))


@_need
async def api_invite(request, uid):
    d = await _body(request)
    return _reply(await op_invite(request.app, uid, d.get("target") or d.get("login") or d.get("id")))


@_need
async def api_accept(request, uid):
    d = await _body(request)
    return _reply(await op_accept(request.app, uid, d.get("id") or d.get("invite_id")))


@_need
async def api_decline(request, uid):
    d = await _body(request)
    return _reply(await op_decline(request.app, uid, d.get("id") or d.get("invite_id")))


@_need
async def api_leave(request, uid):
    await _body(request)
    return _reply(await op_leave(request.app, uid))


@_need
async def api_kick(request, uid):
    d = await _body(request)
    return _reply(await op_kick(request.app, uid, d.get("id") or d.get("target")))


@_need
async def api_set_state(request, uid):
    d = await _body(request)
    return _reply(await op_state(request.app, uid, d.get("state")))


ROUTES = (
    ("GET",  "/api/brigada/state",  api_state),
    ("POST", "/api/brigada/create", api_create),
    ("POST", "/api/brigada/invite", api_invite),
    ("POST", "/api/brigada/accept", api_accept),
    ("POST", "/api/brigada/decline", api_decline),
    ("POST", "/api/brigada/leave",  api_leave),
    ("POST", "/api/brigada/kick",   api_kick),
    ("POST", "/api/brigada/state",  api_set_state),
)


def setup(app, accounts=None):
    """Только из make_app(): после старта роутер заморожен."""
    if accounts is not None:
        app["accounts"] = accounts
    hub = app.get("hub")
    if hub is not None:
        hub._app = app
    for method, path, handler in ROUTES:
        app.router.add_route(method, path, handler)
    app["brigades_ready"] = True
    log.info("Бригады: зарегистрировано маршрутов — %d", len(ROUTES))


# ---------- веб-версии команд /brigada ----------
async def _say(it, text):
    try:
        await it.response.send_message(text)
    except Exception:
        try:
            await it.followup.send(text)
        except Exception:
            log.debug("brigada say", exc_info=True)


def _app_of(it):
    hub = getattr(it.session, "hub", None)
    app = getattr(hub, "_app", None)
    if app is not None:
        return app
    from app import APP_HUB
    return APP_HUB.get("app")


async def _render(it, res, ok_text):
    if res.get("ok"):
        await _say(it, "✅ " + (res.get("text") or ok_text))
    else:
        await _say(it, "❌ " + (res.get("error") or "Не получилось"))
    app = _app_of(it)
    if app is not None:
        try:
            await it.session.emit({"type": "brigade", "kind": "changed",
                                   "state": await payload(app, it.user.id)})
        except Exception:
            log.debug("brigade render", exc_info=True)


def install_commands(app=None):
    """Подменяет /brigada * на веб-варианты: позывной вместо discord.Member."""
    from discord_shim import register_command, COMMANDS

    async def cmd_root(interaction, action=None):
        a = _app_of(interaction)
        if a is None:
            await _say(interaction, "❌ Бригады недоступны")
            return
        data = await payload(a, interaction.user.id)
        await interaction.session.emit({"type": "brigade", "kind": "open", "state": data})
        b = data.get("mine")
        if b:
            await _say(interaction, f"🤝 «{b['name']}» — {b['state_label']}, {b['size']}/{b['max']}")
        else:
            await _say(interaction, "Ты не в бригаде. Создай: /brigada new <название> — или открой панель «Бригада» (B).")

    async def cmd_new(interaction, name=None, description=None):
        a = _app_of(interaction)
        if a is None:
            await _say(interaction, "❌ Бригады недоступны")
            return
        if not name:
            await _say(interaction, "Использование: /brigada new <название> [описание]")
            return
        await _render(interaction, await op_create(a, interaction.user.id, name, description or ""),
                      "Бригада создана")

    async def cmd_add(interaction, target=None):
        a = _app_of(interaction)
        if a is None or not target:
            await _say(interaction, "Использование: /brigada add <позывной>")
            return
        res = await op_invite(a, interaction.user.id, target)
        if res.get("ok"):
            res["text"] = f"Приглашение отправлено: {res.get('invitee_name')} ({res.get('expires_in', 60)} сек)"
        await _render(interaction, res, "Приглашение отправлено")

    async def cmd_kick(interaction, target=None):
        a = _app_of(interaction)
        if a is None or not target:
            await _say(interaction, "Использование: /brigada kick <позывной>")
            return
        await _render(interaction, await op_kick(a, interaction.user.id, target), "Игрок исключён")

    async def cmd_leave(interaction):
        a = _app_of(interaction)
        if a is None:
            return
        res = await op_leave(a, interaction.user.id)
        if res.get("ok"):
            res["text"] = "Бригада распущена" if res.get("disbanded") else "Ты покинул бригаду"
        await _render(interaction, res, "Готово")

    async def cmd_active(interaction):
        a = _app_of(interaction)
        if a is None:
            return
        res = await op_state(a, interaction.user.id, "active")
        if res.get("ok"):
            res["text"] = "Режим «Вместе» включён"
        await _render(interaction, res, "Готово")

    async def cmd_no_active(interaction):
        a = _app_of(interaction)
        if a is None:
            return
        res = await op_state(a, interaction.user.id, "no_active")
        if res.get("ok"):
            res["text"] = "Режим «Расход» включён"
        await _render(interaction, res, "Готово")

    async def cmd_view(interaction):
        await cmd_root(interaction)

    pairs = (
        ("brigada", cmd_root, "Бригада: панель и состав"),
        ("brigada new", cmd_new, "Создать бригаду"),
        ("brigada add", cmd_add, "Пригласить игрока по позывному"),
        ("brigada kick", cmd_kick, "Исключить участника"),
        ("brigada leave", cmd_leave, "Покинуть бригаду"),
        ("brigada active", cmd_active, "Режим «Вместе»"),
        ("brigada no_active", cmd_no_active, "Режим «Расход»"),
        ("brigada view", cmd_view, "Все бригады"),
    )
    for name, fn, desc in pairs:
        register_command(name, fn, desc)
    log.info("Бригады: веб-команды применены (%d), всего команд %d", len(pairs), len(COMMANDS))


def install(app, accounts=None):
    """Совместимость: маршруты + команды. Вызывать только до старта приложения."""
    setup(app, accounts)
    install_commands(app)