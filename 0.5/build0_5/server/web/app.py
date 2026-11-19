# -*- coding: utf-8 -*-
"""Веб-сервер игры: LAN/Radmin VPN, аккаунты, WS-синхронизация, мессенджер, бригады.

Маршруты модулей (map_api, brigades) регистрируются в make_app():
aiohttp замораживает роутер до on_startup, в bootstrap добавлять роуты нельзя.
"""
from __future__ import annotations

import asyncio
import contextlib
import functools
import hashlib
import json
import logging
import os
import secrets
import signal
import socket
import sqlite3
import sys
import time

from aiohttp import web

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(WEB_DIR))
for _p in (BASE, WEB_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import discord_shim
discord_shim.install()                      # ДО импорта func.*
import compat
compat.install()
from bridge import Hub, READONLY            # noqa: E402
from discord_shim import COMMANDS           # noqa: E402
from messenger import Messenger             # noqa: E402
from sync import World                      # noqa: E402

ACC_DB = os.path.join(WEB_DIR, "accounts.db")
MSG_DB = os.path.join(WEB_DIR, "messenger.db")
LEGACY = os.path.join(BASE, "server", "_legacy", "database.json")

COOKIE = "wc_session"
TOKENS: dict[str, dict] = {}
ATTEMPTS: dict[str, list[float]] = {}
REG_ATTEMPTS: dict[str, list[float]] = {}
SESSION_TTL = 7 * 86400

HOST = os.environ.get("WC_HOST", "0.0.0.0")
PORT = int(os.environ.get("WC_PORT", "8080"))
PIN = os.environ.get("WC_PIN", "").strip()
ADMIN_LOGIN = os.environ.get("WC_ADMIN", "").strip().lower()
DEBUG_ON = os.environ.get("WC_DEBUG", "0") == "1"
ALLOW_TOKEN_QUERY = os.environ.get("WC_TOKEN_QUERY", "0") == "1"

RATE_ACTIONS = float(os.environ.get("WC_RATE", "20"))
RATE_BURST = float(os.environ.get("WC_RATE_BURST", "40"))
WS_MAX_MSG = 64 * 1024
LOGIN_LIMIT = 12
REG_LIMIT = 5
MAX_IDS = 500

log = logging.getLogger("web")
APP_HUB: dict = {}
LOOP: asyncio.AbstractEventLoop | None = None
BG_TASKS: set[asyncio.Task] = set()


def spawn(coro, name="bg"):
    t = asyncio.ensure_future(coro)
    BG_TASKS.add(t)
    t.add_done_callback(BG_TASKS.discard)
    return t


# ---------- аккаунты ----------
@contextlib.contextmanager
def _con(path):
    c = sqlite3.connect(path, timeout=10)
    try:
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        with c:
            yield c
    finally:
        c.close()


def init_accounts():
    with _con(ACC_DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, login TEXT UNIQUE NOT NULL,
            user_id INTEGER UNIQUE NOT NULL, salt TEXT NOT NULL, phash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0, created INTEGER)""")


PBKDF_ROUNDS = 200_000


def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), PBKDF_ROUNDS).hex()


async def _hash_async(pw, salt):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _hash, pw, salt)


_DUMMY_SALT = secrets.token_hex(16)
_DUMMY_HASH = _hash("dummy-password-for-timing", _DUMMY_SALT)


class Accounts:
    def _by(self, sql, arg):
        with _con(ACC_DB) as c:
            r = c.execute(sql, (arg,)).fetchone()
        return dict(r) if r else None

    def by_login(self, login):
        return self._by("SELECT * FROM accounts WHERE login=?", str(login).strip().lower())

    def by_id(self, uid):
        return self._by("SELECT * FROM accounts WHERE user_id=?", uid)

    def all(self):
        with _con(ACC_DB) as c:
            return [dict(r) for r in c.execute("SELECT * FROM accounts ORDER BY login")]

    def directory(self):
        with _con(ACC_DB) as c:
            return [dict(r) for r in c.execute("SELECT user_id, login FROM accounts ORDER BY login")]


ACCOUNTS = Accounts()


async def _db(fn, *a):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *a))


def _throttle(bucket, key, limit, window):
    now = time.time()
    hits = [t for t in bucket.get(key, []) if now - t < window]
    hits.append(now)
    bucket[key] = hits
    return len(hits) > limit


def auth(request):
    tok = request.cookies.get(COOKIE)
    if not tok and ALLOW_TOKEN_QUERY:
        tok = request.query.get("token")
    if not tok:
        return None
    s = TOKENS.get(tok)
    if s is None:
        return None
    if time.time() - s["ts"] >= SESSION_TTL:
        TOKENS.pop(tok, None)
        return None
    s["ts"] = time.time()
    return s


def _session(request):
    a = auth(request)
    return request.app["hub"].session(a["user_id"], a["login"], a["admin"]) if a else None


def _need_auth(handler):
    @functools.wraps(handler)
    async def wrapped(request):
        if auth(request) is None:
            return web.json_response({"error": "Требуется вход"}, status=401)
        return await handler(request)
    return wrapped


async def _json(request):
    try:
        d = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text=json.dumps({"error": "Некорректный JSON"}, ensure_ascii=False),
                                 content_type="application/json")
    if not isinstance(d, dict):
        raise web.HTTPBadRequest(text=json.dumps({"error": "Ожидался объект"}, ensure_ascii=False),
                                 content_type="application/json")
    return d


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _err(text, status=400):
    return web.json_response({"error": text}, status=status)


# ---------- сеть ----------
def lan_addresses():
    ips = set()
    with contextlib.suppress(Exception):
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    with contextlib.suppress(Exception):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
        finally:
            s.close()
    ips.discard("127.0.0.1")

    def rank(ip):
        if ip.startswith("26."):
            return 0
        if ip.startswith(("192.168.", "10.")):
            return 1
        if ip.startswith("172.") and 16 <= _int(ip.split(".")[1], 0) <= 31:
            return 1
        return 2

    return sorted(ips, key=lambda x: (rank(x), x))


def server_info():
    return {"host": HOST, "port": PORT, "addresses": lan_addresses(), "pin": bool(PIN)}


# ---------- auth API ----------
async def api_register(request):
    ip = request.remote or "?"
    if _throttle(REG_ATTEMPTS, ip, REG_LIMIT, 3600):
        return _err("Слишком много регистраций с этого адреса. Попробуй позже.", 429)
    d = await _json(request)
    if PIN and not secrets.compare_digest(str(d.get("pin", "")), PIN):
        return _err("Неверный PIN сервера", 403)
    login = str(d.get("login") or "").strip().lower()
    pw = str(d.get("password") or "")
    if not 3 <= len(login) <= 32 or not 6 <= len(pw) <= 128:
        return _err("Логин 3–32 символа, пароль 6–128")
    if not all(ch.isalnum() or ch in "_-." for ch in login):
        return _err("Логин: буквы, цифры, _ - .")
    salt = secrets.token_hex(16)
    phash = await _hash_async(pw, salt)
    is_admin = int(bool(ADMIN_LOGIN) and login == ADMIN_LOGIN)

    def insert():
        with _con(ACC_DB) as c:
            cur = c.execute(
                "INSERT INTO accounts(login,user_id,salt,phash,is_admin,created) VALUES(?,?,?,?,?,?)",
                (login, 0, salt, phash, is_admin, int(time.time())))
            uid = 900_000_000 + cur.lastrowid
            c.execute("UPDATE accounts SET user_id=? WHERE id=?", (uid, cur.lastrowid))
            return uid

    try:
        uid = await _db(insert)
    except sqlite3.IntegrityError:
        return _err("Логин занят", 409)
    log.info("Новый аккаунт %s (uid=%s, admin=%s)", login, uid, bool(is_admin))
    return web.json_response({"ok": True})


async def api_login(request):
    ip = request.remote or "?"
    if _throttle(ATTEMPTS, ip, LOGIN_LIMIT, 60):
        return _err("Слишком много попыток, подожди минуту", 429)
    d = await _json(request)
    if PIN and not secrets.compare_digest(str(d.get("pin", "")), PIN):
        return _err("Неверный PIN сервера", 403)
    login = str(d.get("login") or "").strip().lower()
    pw = str(d.get("password") or "")
    row = await _db(ACCOUNTS.by_login, login)
    if row:
        ok = secrets.compare_digest(row["phash"], await _hash_async(pw, row["salt"]))
    else:
        await _hash_async(pw, _DUMMY_SALT)
        ok = False
    if not ok:
        return _err("Неверный логин или пароль", 401)
    tok = secrets.token_urlsafe(32)
    TOKENS[tok] = {"user_id": row["user_id"], "login": row["login"],
                   "admin": bool(row["is_admin"]), "ts": time.time()}
    r = web.json_response({"ok": True, "login": row["login"],
                           "admin": bool(row["is_admin"]), "user_id": row["user_id"]})
    r.set_cookie(COOKIE, tok, httponly=True, samesite="lax", max_age=SESSION_TTL,
                 path="/", secure=request.scheme == "https")
    return r


async def api_logout(request):
    a = TOKENS.pop(request.cookies.get(COOKIE), None)
    if a:
        await _drop_session(request.app["hub"], a["user_id"], save=True)
    r = web.json_response({"ok": True})
    r.del_cookie(COOKIE, path="/")
    return r


async def api_me(request):
    a = auth(request)
    if not a:
        return _err("no auth", 401)
    return web.json_response({"login": a["login"], "admin": a["admin"], "user_id": a["user_id"]})


async def api_lan(request):
    info = server_info()
    info["online"] = len(request.app["hub"].online_ids())
    return web.json_response(info)


# ---------- игровой ввод ----------
class Rate:
    __slots__ = ("tokens", "ts", "rate", "burst")

    def __init__(self, rate=RATE_ACTIONS, burst=RATE_BURST):
        self.rate, self.burst, self.tokens, self.ts = rate, burst, burst, time.monotonic()

    def take(self, cost=1.0):
        now = time.monotonic()
        self.tokens = min(self.burst, self.tokens + (now - self.ts) * self.rate)
        self.ts = now
        if self.tokens < cost:
            return False
        self.tokens -= cost
        return True


ADMIN_PREFIXES = ("debug", "admin", "set_channel", "sync", "event_force", "event_toggle")


def _allowed(s, name):
    return not (name.startswith(ADMIN_PREFIXES) and not s.user.guild_permissions.administrator)


def _params(raw):
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        if not isinstance(k, str) or len(k) > 64:
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = str(v)[:512] if isinstance(v, str) else v
    return out


def _values(raw):
    if not isinstance(raw, list):
        return []
    return [str(v)[:512] for v in raw[:25] if isinstance(v, (str, int, float))]


async def _dispatch(s, kind, d):
    if kind == "click":
        await s.click(d.get("view"), d.get("item"), _values(d.get("values")))
    elif kind == "submit":
        vals = d.get("values")
        vals = {str(k): str(v)[:4000] for k, v in vals.items()} if isinstance(vals, dict) else {}
        await s.submit(d.get("modal"), vals)
    elif kind == "refresh":
        await s.refresh()
    elif kind == "command":
        name = str(d.get("name") or "")[:64]
        if not _allowed(s, name):
            await s.toast("Недостаточно прав для этой команды.", "warn")
            await s.flush()
            return
        await s.command(name, **_params(d.get("params")))


async def _rest(request, kind):
    s = _session(request)
    if s is None:
        return _err("no auth", 401)
    rate = getattr(s, "_rate", None)
    if rate is None:
        rate = s._rate = Rate()
    if not rate.take():
        return _err("Слишком часто. Притормози.", 429)
    d = await _json(request)
    s.drain()
    await _dispatch(s, kind, d)
    return web.json_response({"ops": s.drain()})


async def api_click(request): return await _rest(request, "click")
async def api_submit(request): return await _rest(request, "submit")
async def api_command(request): return await _rest(request, "command")
async def api_refresh(request): return await _rest(request, "refresh")


# ---------- мессенджер API ----------
def _msg(request):
    return request.app["messenger"]


@_need_auth
async def msg_overview(request):
    s = _session(request)
    m = _msg(request)
    data = await _db(m.contacts, s.user.id, request.app["world"].online())
    data["unread"] = await _db(m.unread, s.user.id)
    directory = await _db(ACCOUNTS.directory)
    data["directory"] = [{"id": a["user_id"], "login": a["login"]}
                         for a in directory if a["user_id"] != s.user.id]
    data["me"] = {"id": s.user.id, "login": s.user.name}
    return web.json_response(data)


@_need_auth
async def msg_thread(request):
    s = _session(request)
    peer = _int(request.query.get("peer"), 0)
    if peer <= 0:
        return _err("Некорректный собеседник")
    data = await _db(_msg(request).thread, s.user.id, peer)
    await request.app["world"].push(s, force=True)
    return web.json_response(data)


@_need_auth
async def msg_send(request):
    s = _session(request)
    d = await _json(request)
    to = d.get("to")
    if isinstance(to, str):
        acc = await _db(ACCOUNTS.by_login, to)
        to = acc["user_id"] if acc else 0
    to = _int(to, 0)
    if to <= 0:
        return _err("Получатель не найден")
    subject = d.get("subject")
    subject = str(subject)[:120] if subject is not None else None
    res = await _db(_msg(request).send, s.user.id, to, str(d.get("body") or ""), subject, "dm")
    return web.json_response(res, status=200 if res.get("ok") else 400)


@_need_auth
async def msg_mail(request):
    s = _session(request)
    return web.json_response(await _db(_msg(request).mail, s.user.id))


@_need_auth
async def msg_read(request):
    s = _session(request)
    d = await _json(request)
    ids = d.get("ids")
    if ids is not None:
        if not isinstance(ids, list):
            return _err("ids должен быть списком")
        ids = [i for i in (_int(x, 0) for x in ids[:MAX_IDS]) if i > 0]
    peer = _int(d.get("peer"), 0) if d.get("peer") is not None else None
    kind = d.get("kind")
    kind = kind if kind in ("dm", "mail", "system") else None
    res = await _db(_msg(request).mark_read, s.user.id, ids, peer, kind)
    await request.app["world"].push(s, force=True)
    return web.json_response(res)


@_need_auth
async def contact_request(request):
    s = _session(request)
    d = await _json(request)
    res = await _db(_msg(request).request, s.user.id, str(d.get("login") or "")[:32])
    if res.get("ok"):
        hub = request.app["hub"]
        peer = res.get("peer")
        await hub.emit_to(peer, {"type": "contacts"})
        target = hub.sessions.get(peer)
        if target is not None:
            await request.app["world"].push(target, force=True)
    return web.json_response(res, status=200 if res.get("ok") else 400)


def _contact_state(m, owner, peer):
    with m._con() as c:
        return m._state(c, owner, peer)


async def _contact_action(request, action):
    s = _session(request)
    d = await _json(request)
    peer = _int(d.get("id"), 0)
    if peer <= 0 or peer == s.user.id:
        return _err("Некорректный контакт")
    m = _msg(request)
    if action == "accept":
        if await _db(_contact_state, m, s.user.id, peer) != "in":
            return _err("Заявки от этого игрока нет")
        res = await _db(m.accept, s.user.id, peer)
    elif action == "decline":
        res = await _db(m.decline, s.user.id, peer)
    elif action == "block":
        res = await _db(m.block, s.user.id, peer)
    elif action == "rename":
        res = await _db(m.rename, s.user.id, peer, str(d.get("alias") or "")[:40])
    else:
        return _err("Неизвестное действие")
    if res.get("ok"):
        await request.app["hub"].emit_to(peer, {"type": "contacts"})
    await request.app["world"].push(s, force=True)
    return web.json_response(res, status=200 if res.get("ok") else 400)


@_need_auth
async def contact_accept(request): return await _contact_action(request, "accept")
@_need_auth
async def contact_decline(request): return await _contact_action(request, "decline")
@_need_auth
async def contact_block(request): return await _contact_action(request, "block")
@_need_auth
async def contact_rename(request): return await _contact_action(request, "rename")


# ---------- WebSocket ----------
WS_TYPES = {"click", "submit", "command", "refresh", "map_move", "typing", "ping"}


async def ws_handler(request):
    a = auth(request)
    ws = web.WebSocketResponse(heartbeat=25.0, autoping=True,
                               receive_timeout=90.0, max_msg_size=WS_MAX_MSG)
    await ws.prepare(request)
    if a is None:
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "toast", "text": "Не авторизован", "kind": "error"})
            await ws.close(code=4001, message=b"auth required")
        return ws

    hub = request.app["hub"]
    world = request.app["world"]
    s = hub.session(a["user_id"], a["login"], a["admin"])
    lock = asyncio.Lock()
    rate = getattr(s, "_rate", None)
    if rate is None:
        rate = s._rate = Rate()
    typing_ts = 0.0
    map_mod = request.app.get("map_api")
    map_move = getattr(map_mod, "step_move_locked", None) or getattr(map_mod, "ws_map_move_handler", None)

    async def sink(payload):
        async with lock:
            if not ws.closed:
                await ws.send_json(payload)

    try:
        s.add_sink(sink)
        await sink(s.snapshot())
        await world.push(s, force=True)
        await world.touch(s.user.id)

        from func.game_manager import game_manager
        if not s.screens:
            await s.command("menu" if game_manager.get_player(a["user_id"]) else "start")

        async for msg in ws:
            if msg.type == web.WSMsgType.ERROR:
                log.warning("WS error %s: %s", a["login"], ws.exception())
                break
            if msg.type != web.WSMsgType.TEXT:
                continue
            try:
                d = json.loads(msg.data)
            except (ValueError, TypeError):
                continue
            if not isinstance(d, dict):
                continue
            t = d.get("type")
            if t not in WS_TYPES:
                continue
            if t == "ping":
                await sink({"type": "pong", "ts": time.time()})
                continue
            if t == "typing":
                now = time.monotonic()
                if now - typing_ts < 1.5:
                    continue
                typing_ts = now
                peer = _int(d.get("to"), 0)
                if peer > 0 and await _db(_contact_state, _msg(request), s.user.id, peer) == "ok":
                    await hub.emit_to(peer, {"type": "typing", "from": s.user.id, "login": s.user.name})
                continue
            if not rate.take():
                await sink({"type": "toast", "text": "Слишком много действий подряд.", "kind": "warn"})
                continue
            if t == "map_move":
                if callable(map_move):
                    await map_move(s, d)
                continue
            await _dispatch(s, t, d)
    except asyncio.CancelledError:
        raise
    except (ConnectionResetError, RuntimeError):
        log.info("WS оборвался: %s", a["login"])
    except Exception:
        log.exception("ws_handler %s", a["login"])
    finally:
        s.remove_sink(sink)
        with contextlib.suppress(Exception):
            await world.touch(s.user.id)
        if not s.sinks:
            spawn(_drop_session(hub, s.user.id, save=True), "drop-session")
        with contextlib.suppress(Exception):
            await ws.close()
    return ws


async def _drop_session(hub, uid, save=False):
    s = hub.sessions.get(uid)
    if s is None or s.sinks:
        return
    if save:
        with contextlib.suppress(Exception):
            from func.game_manager import game_manager
            from database.db import save_player
            p = game_manager.get_player(uid)
            if p is not None:
                await save_player(p)
    for v in list(s.views.values()):
        with contextlib.suppress(Exception):
            v.stop()
    s.views.clear(); s.modals.clear(); s.screens.clear(); s.order.clear(); s.ops.clear()
    s.combat_view = None
    hub.sessions.pop(uid, None)
    if hub.world is not None:
        hub.world._hash.pop(uid, None)


async def index(request):
    return web.FileResponse(os.path.join(WEB_DIR, "static", "index.html"))


# ---------- доставка сообщений ----------
def on_message(msg):
    hub = APP_HUB.get("hub")
    world = APP_HUB.get("world")
    if hub is None or world is None:
        return

    async def deliver():
        try:
            await hub.emit_to(msg["recipient"], {"type": "msg", "message": msg})
            s = hub.sessions.get(msg["recipient"])
            if s:
                await world.push(s, force=True)
            if msg["sender"]:
                await hub.emit_to(msg["sender"], {"type": "msg_echo", "message": msg})
        except Exception:
            log.exception("deliver message %s", msg.get("id"))

    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is LOOP and LOOP is not None:
        spawn(deliver(), "deliver")
    elif LOOP is not None and LOOP.is_running():
        fut = asyncio.run_coroutine_threadsafe(deliver(), LOOP)
        fut.add_done_callback(lambda f: f.exception() and log.error("deliver: %s", f.exception()))
    else:
        log.warning("Сообщение %s не доставлено: event loop не запущен", msg.get("id"))


# ---------- фоновая уборка ----------
async def janitor(app):
    hub = app["hub"]
    while True:
        try:
            await asyncio.sleep(60)
            now = time.time()
            for tok in [k for k, v in TOKENS.items() if now - v["ts"] >= SESSION_TTL]:
                TOKENS.pop(tok, None)
            for bucket, window in ((ATTEMPTS, 60), (REG_ATTEMPTS, 3600)):
                for ip in list(bucket):
                    hits = [t for t in bucket[ip] if now - t < window]
                    if hits:
                        bucket[ip] = hits
                    else:
                        bucket.pop(ip, None)
            for uid, s in list(hub.sessions.items()):
                if not s.sinks and now - s.last_seen > 300:
                    await _drop_session(hub, uid, save=True)
                if len(s.views) > 64:
                    for vid in [k for k, v in s.views.items() if v.is_finished()]:
                        s.views.pop(vid, None)
                if len(s.modals) > 32:
                    keep = list(s.modals)[-16:]
                    s.modals = {k: v for k, v in s.modals.items() if k in keep}
            with contextlib.suppress(Exception):
                from func.social.brigade_manager import brigade_manager
                brigade_manager._cleanup_expired_invites()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("janitor")


# ---------- жизненный цикл ----------
async def bootstrap(app):
    global LOOP
    LOOP = asyncio.get_running_loop()
    os.chdir(BASE)

    await _db(init_accounts)
    from database.db import init_db
    from func.game_manager import game_manager
    from func.commands import setup_commands
    from func.social_commands import setup_social_commands

    await init_db()
    await game_manager.load_all_players()
    game_manager.game_channel = 0

    hub = app["hub"]
    hub.bot._hub = hub
    hub._app = app

    setup_commands(hub.bot, game_manager)
    setup_social_commands(hub.bot)
    compat.HUB = hub
    compat.bind_loop()

    with contextlib.suppress(Exception):
        from func.social.brigade_manager import brigade_manager
        await brigade_manager.load_all()

    # веб-подмены /brigada * — строго после setup_social_commands
    brig = app.get("brigades")
    if brig is not None:
        try:
            brig.install_commands(app)
        except Exception:
            log.exception("Бригады: веб-команды не применены")
    else:
        log.error("Бригады: модуль не подключён на этапе make_app")

    if DEBUG_ON:
        added = await compat.register_debug(hub.bot, game_manager)
        log.warning("DEBUG включён (WC_DEBUG=1): %s", ", ".join(added) or "нет команд")
    else:
        log.info("Debug-команды отключены. Для включения задай WC_DEBUG=1.")

    messenger = Messenger(MSG_DB, ACCOUNTS, on_message)
    await _db(messenger.init)
    log.info("Мессенджер: %s", await _db(messenger.import_legacy, LEGACY))
    app["messenger"] = messenger
    hub.messenger = messenger

    world = World(hub, messenger, server_info())
    app["world"] = world
    hub.world = world
    APP_HUB["hub"] = hub
    APP_HUB["world"] = world
    APP_HUB["app"] = app
    app["world_task"] = world.start()
    app["janitor_task"] = spawn(janitor(app), "janitor")

    if os.environ.get("WC_EVENTS") == "1":
        from func.global_events import run_global_events
        app["events"] = spawn(run_global_events(hub.bot, game_manager), "global-events")

    if os.environ.get("WC_AUTOSAVE", "1") == "1":
        from utils.autosave import autosaver
        autosaver.start(hub.bot, game_manager)
        app["autosaver"] = autosaver

    try:
        await compat.start_task_board(hub.bot)
    except Exception:
        log.exception("Доска заданий NPC не запущена — квесты у NPC будут недоступны")

    info = server_info()
    print("\n" + "=" * 62)
    print("  44 WHITE CURTAIN — сервер запущен")
    print("=" * 62)
    print(f"  Локально:      http://127.0.0.1:{PORT}")
    for ip in info["addresses"]:
        tag = "Radmin VPN" if ip.startswith("26.") else "локальная сеть"
        print(f"  {tag:<14} http://{ip}:{PORT}")
    print(f"  PIN сервера:   {'включён' if PIN else 'выключен (задай WC_PIN)'}")
    print(f"  Админ:         {ADMIN_LOGIN or 'не задан (задай WC_ADMIN)'}")
    print(f"  Debug:         {'ВКЛЮЧЁН' if DEBUG_ON else 'выключен'}")
    print(f"  Бригады:       {'API активно' if app.get('brigades_ready') else 'НЕ подключены'}")
    print(f"  Команд: {len(COMMANDS)}   БД игры: {os.path.join(BASE, 'metro.db')}")
    print("=" * 62 + "\n")
    if not PIN:
        log.warning("WC_PIN не задан — регистрация открыта всем, кто видит порт.")


async def shutdown(app):
    hub = app.get("hub")
    world = app.get("world")
    if world is not None:
        world.stop()
    for key in ("events", "world_task", "janitor_task"):
        t = app.get(key)
        if t is not None and not t.done():
            t.cancel()
    with contextlib.suppress(Exception):
        from func.task_board_manager import task_board_manager
        t = getattr(task_board_manager, "_refresh_task", None)
        if t is not None and not t.done():
            t.cancel()
    with contextlib.suppress(Exception):
        from func.game_manager import game_manager
        from database.db import save_player
        players = list(getattr(game_manager, "players", {}).values())
        if players:
            log.info("Финальное сохранение: %d персонажей", len(players))
            await asyncio.gather(*(save_player(p) for p in players), return_exceptions=True)
    pending = [t for t in list(BG_TASKS) if not t.done()]
    for t in pending:
        t.cancel()
    if pending:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=5.0)
    BG_TASKS.clear()
    if hub is not None:
        hub.sessions.clear()
    APP_HUB.clear()
    from database.db import close_db
    await close_db()


def make_app():
    app = web.Application(client_max_size=1 * 1024 * 1024)
    app["hub"] = Hub()
    app["session_of"] = _session
    app["accounts"] = ACCOUNTS
    app["hub"]._app = app
    app.on_startup.append(bootstrap)
    app.on_cleanup.append(shutdown)
    app.add_routes([
        web.get("/", index), web.get("/ws", ws_handler),
        web.post("/api/register", api_register), web.post("/api/login", api_login),
        web.post("/api/logout", api_logout), web.get("/api/me", api_me), web.get("/api/lan", api_lan),
        web.post("/api/click", api_click), web.post("/api/submit", api_submit),
        web.post("/api/command", api_command), web.post("/api/refresh", api_refresh),
        web.get("/api/msg/overview", msg_overview), web.get("/api/msg/thread", msg_thread),
        web.post("/api/msg/send", msg_send), web.get("/api/msg/mail", msg_mail),
        web.post("/api/msg/read", msg_read),
        web.post("/api/contacts/request", contact_request),
        web.post("/api/contacts/accept", contact_accept),
        web.post("/api/contacts/decline", contact_decline),
        web.post("/api/contacts/block", contact_block),
        web.post("/api/contacts/rename", contact_rename),
        web.static("/static", os.path.join(WEB_DIR, "static")),
        web.static("/sounds", os.path.join(BASE, "server", "sounds")),
    ])

    # маршруты модулей — только здесь, роутер ещё не заморожен
    try:
        import map_api
        app["map_api"] = map_api
        if hasattr(map_api, "setup"):
            map_api.setup(app)
    except Exception:
        log.exception("Схема метро: маршруты не зарегистрированы")

    try:
        import brigades
        app["brigades"] = brigades
        brigades.setup(app, ACCOUNTS)
    except Exception:
        log.exception("Бригады: маршруты не зарегистрированы")

    return app


async def _serve():
    app = make_app()
    runner = web.AppRunner(app, access_log=None, shutdown_timeout=5.0)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT, reuse_address=True)
    await site.start()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, AttributeError, ValueError):
            loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    except asyncio.CancelledError:
        pass
    finally:
        with contextlib.suppress(Exception):
            await runner.cleanup()


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        print("\nОстановка сервера…")
    print("Сервер остановлен, БД закрыта.")


if __name__ == "__main__":
    main()