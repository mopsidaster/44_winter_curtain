# -*- coding: utf-8 -*-
"""Веб-сервер игры: LAN/Radmin VPN, аккаунты, WS-синхронизация, мессенджер."""
from __future__ import annotations
import asyncio, hashlib, json, logging, os, secrets, socket, sqlite3, sys, time
from aiohttp import web

import discord_shim
discord_shim.install()                      # ДО импорта func.*
import compat
compat.install()
from bridge import Hub, READONLY
from discord_shim import COMMANDS
from messenger import Messenger
from sync import World
import map_api  # <--- ДОБАВЛЕНО: импорт модуля карты

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(WEB_DIR))
sys.path.insert(0, BASE); sys.path.insert(0, WEB_DIR)
os.chdir(BASE)

ACC_DB = os.path.join(WEB_DIR, "accounts.db")
MSG_DB = os.path.join(WEB_DIR, "messenger.db")
LEGACY = os.path.join(BASE, "server", "_legacy", "database.json")
COOKIE = "wc_session"; TOKENS = {}; ATTEMPTS = {}
HOST = os.environ.get("WC_HOST", "0.0.0.0")
PORT = int(os.environ.get("WC_PORT", "8080"))
PIN = os.environ.get("WC_PIN", "").strip()
log = logging.getLogger("web")

# ---------- аккаунты ----------
def _con(path):
    c = sqlite3.connect(path, timeout=10); c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); return c

def init_accounts():
    with _con(ACC_DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, login TEXT UNIQUE NOT NULL,
            user_id INTEGER UNIQUE NOT NULL, salt TEXT NOT NULL, phash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0, created INTEGER)""")

def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()

class Accounts:
    def by_login(self, login):
        with _con(ACC_DB) as c:
            r = c.execute("SELECT * FROM accounts WHERE login=?", (str(login).strip().lower(),)).fetchone()
        return dict(r) if r else None
    def by_id(self, uid):
        with _con(ACC_DB) as c:
            r = c.execute("SELECT * FROM accounts WHERE user_id=?", (uid,)).fetchone()
        return dict(r) if r else None
    def all(self):
        with _con(ACC_DB) as c:
            return [dict(r) for r in c.execute("SELECT * FROM accounts ORDER BY login")]

ACCOUNTS = Accounts()

def _throttle(ip):
    now = time.time(); hits = [t for t in ATTEMPTS.get(ip, []) if now - t < 60]
    ATTEMPTS[ip] = hits + [now]; return len(hits) >= 12

def auth(request):
    tok = request.cookies.get(COOKIE) or request.query.get("token")
    s = TOKENS.get(tok)
    if s and time.time() - s["ts"] < 7 * 86400:
        s["ts"] = time.time(); return s
    return None

def _session(request):
    a = auth(request)
    return request.app["hub"].session(a["user_id"], a["login"], a["admin"]) if a else None

def _need_auth(handler):
    async def wrapped(request):
        if auth(request) is None:
            return web.json_response({"error": "Требуется вход"}, status=401)
        return await handler(request)
    return wrapped

# ---------- сеть ----------
def lan_addresses():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ips.add(s.getsockname()[0]); s.close()
    except Exception:
        pass
    ips.discard("127.0.0.1")
    def rank(ip):
        if ip.startswith("26."): return 0          # Radmin VPN
        if ip.startswith(("192.168.", "10.", "172.")): return 1
        return 2
    return sorted(ips, key=lambda x: (rank(x), x))

def server_info():
    return {"host": HOST, "port": PORT, "addresses": lan_addresses(), "pin": bool(PIN)}

# ---------- auth API ----------
async def api_register(request):
    d = await request.json()
    if PIN and str(d.get("pin", "")) != PIN:
        return web.json_response({"error": "Неверный PIN сервера"}, status=403)
    login = (d.get("login") or "").strip().lower(); pw = d.get("password") or ""
    if len(login) < 3 or len(pw) < 6:
        return web.json_response({"error": "Логин от 3 символов, пароль от 6"}, status=400)
    if not all(ch.isalnum() or ch in "_-." for ch in login):
        return web.json_response({"error": "Логин: буквы, цифры, _ - ."}, status=400)
    salt = secrets.token_hex(16)
    try:
        with _con(ACC_DB) as c:
            first = c.execute("SELECT COUNT(*) n FROM accounts").fetchone()["n"] == 0
            cur = c.execute("INSERT INTO accounts(login,user_id,salt,phash,is_admin,created) VALUES(?,?,?,?,?,?)",
                            (login, 0, salt, _hash(pw, salt),
                             int(first or login == os.environ.get("WC_ADMIN", "")), int(time.time())))
            uid = 900_000_000 + cur.lastrowid
            c.execute("UPDATE accounts SET user_id=? WHERE id=?", (uid, cur.lastrowid))
    except sqlite3.IntegrityError:
        return web.json_response({"error": "Логин занят"}, status=409)
    return web.json_response({"ok": True})

async def api_login(request):
    ip = request.remote or "?"
    if _throttle(ip): return web.json_response({"error": "Слишком много попыток, подожди минуту"}, status=429)
    d = await request.json()
    if PIN and str(d.get("pin", "")) != PIN:
        return web.json_response({"error": "Неверный PIN сервера"}, status=403)
    login = (d.get("login") or "").strip().lower(); pw = d.get("password") or ""
    row = ACCOUNTS.by_login(login)
    if not row or not secrets.compare_digest(row["phash"], _hash(pw, row["salt"])):
        return web.json_response({"error": "Неверный логин или пароль"}, status=401)
    tok = secrets.token_urlsafe(32)
    TOKENS[tok] = {"user_id": row["user_id"], "login": row["login"], "admin": bool(row["is_admin"]), "ts": time.time()}
    r = web.json_response({"ok": True, "login": row["login"], "admin": bool(row["is_admin"]),
                           "user_id": row["user_id"]})
    r.set_cookie(COOKIE, tok, httponly=True, samesite="lax", max_age=7 * 86400)
    return r

async def api_logout(request):
    TOKENS.pop(request.cookies.get(COOKIE), None)
    r = web.json_response({"ok": True}); r.del_cookie(COOKIE); return r

async def api_me(request):
    a = auth(request)
    if not a: return web.json_response({"error": "no auth"}, status=401)
    return web.json_response({"login": a["login"], "admin": a["admin"], "user_id": a["user_id"]})

async def api_lan(request):
    info = server_info()
    info["online"] = len(request.app["hub"].online_ids())
    return web.json_response(info)

# ---------- игровой ввод ----------
async def _rest(request, kind):
    s = _session(request)
    if s is None: return web.json_response({"error": "no auth"}, status=401)
    d = await request.json()
    if kind == "click": await s.click(d.get("view"), d.get("item"), d.get("values"))
    elif kind == "submit": await s.submit(d.get("modal"), d.get("values") or {})
    elif kind == "refresh": await s.refresh()
    else: await s.command(d.get("name"), **(d.get("params") or {}))
    return web.json_response({"ops": s.drain()})

async def api_click(request): return await _rest(request, "click")
async def api_submit(request): return await _rest(request, "submit")
async def api_command(request): return await _rest(request, "command")
async def api_refresh(request): return await _rest(request, "refresh")

# ---------- мессенджер API ----------
def _msg(request): return request.app["messenger"]

@_need_auth
async def msg_overview(request):
    s = _session(request); m = _msg(request)
    data = m.contacts(s.user.id, request.app["world"].online())
    data["unread"] = m.unread(s.user.id)
    data["directory"] = [{"id": a["user_id"], "login": a["login"]} for a in ACCOUNTS.all()
                         if a["user_id"] != s.user.id]
    data["me"] = {"id": s.user.id, "login": s.user.name}
    return web.json_response(data)

@_need_auth
async def msg_thread(request):
    s = _session(request); peer = int(request.query.get("peer", "0"))
    data = _msg(request).thread(s.user.id, peer)
    await request.app["world"].push(s, force=True)
    return web.json_response(data)

@_need_auth
async def msg_send(request):
    s = _session(request); d = await request.json()
    kind = d.get("kind") or "dm"
    if kind not in ("dm", "mail"): kind = "dm"
    to = d.get("to")
    if isinstance(to, str):
        acc = ACCOUNTS.by_login(to); to = acc["user_id"] if acc else 0
    res = _msg(request).send(s.user.id, int(to or 0), d.get("body", ""), d.get("subject"), kind)
    return web.json_response(res, status=200 if res.get("ok") else 400)

@_need_auth
async def msg_mail(request):
    s = _session(request)
    return web.json_response(_msg(request).mail(s.user.id))

@_need_auth
async def msg_read(request):
    s = _session(request); d = await request.json()
    res = _msg(request).mark_read(s.user.id, d.get("ids"), d.get("peer"), d.get("kind"))
    await request.app["world"].push(s, force=True)
    return web.json_response(res)

@_need_auth
async def contact_request(request):
    s = _session(request); d = await request.json()
    res = _msg(request).request(s.user.id, d.get("login", ""))
    if res.get("ok"):
        hub = request.app["hub"]
        await hub.emit_to(res["peer"], {"type": "contacts"})
        await request.app["world"].push(hub.sessions[res["peer"]], force=True) if res["peer"] in hub.sessions else None
    return web.json_response(res, status=200 if res.get("ok") else 400)

async def _contact_action(request, action):
    s = _session(request); d = await request.json(); peer = int(d.get("id") or 0)
    m = _msg(request)
    res = {"accept": m.accept, "decline": m.decline, "block": m.block,
           "rename": lambda a, b: m.rename(a, b, d.get("alias", ""))}[action](s.user.id, peer)
    await request.app["hub"].emit_to(peer, {"type": "contacts"})
    await request.app["world"].push(s, force=True)
    return web.json_response(res)

@_need_auth
async def contact_accept(request): return await _contact_action(request, "accept")
@_need_auth
async def contact_decline(request): return await _contact_action(request, "decline")
@_need_auth
async def contact_block(request): return await _contact_action(request, "block")
@_need_auth
async def contact_rename(request): return await _contact_action(request, "rename")

# ---------- WebSocket ----------
async def ws_handler(request):
    a = auth(request)
    ws = web.WebSocketResponse(heartbeat=25, autoping=True)
    await ws.prepare(request)
    if a is None:
        await ws.send_json({"type": "toast", "text": "Не авторизован", "kind": "error"})
        await ws.close(); return ws
    hub = request.app["hub"]; world = request.app["world"]
    s = hub.session(a["user_id"], a["login"], a["admin"])
    lock = asyncio.Lock()
    async def sink(payload):
        async with lock:
            if not ws.closed: await ws.send_json(payload)
    s.add_sink(sink)
    await ws.send_json(s.snapshot())
    await world.push(s, force=True)
    await world.touch(s.user.id)
    from func.game_manager import game_manager
    if not s.screens:
        await s.command("menu" if game_manager.get_player(a["user_id"]) else "start")
    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT: continue
            try: d = json.loads(msg.data)
            except Exception: continue
            t = d.get("type")
            if t == "click": await s.click(d.get("view"), d.get("item"), d.get("values"))
            elif t == "submit": await s.submit(d.get("modal"), d.get("values") or {})
            elif t == "command": await s.command(d.get("name"), **(d.get("params") or {}))
            elif t == "refresh": await s.refresh()
            elif t == "map_move": await map_api.ws_map_move_handler(s, d)  # <--- ДОБАВЛЕНО: обработка перехода по карте
            elif t == "typing":
                await hub.emit_to(int(d.get("to") or 0),
                                  {"type": "typing", "from": s.user.id, "login": s.user.name})
            elif t == "ping": await sink({"type": "pong", "ts": time.time()})
    finally:
        s.remove_sink(sink)
        await world.touch(s.user.id)
    return ws

async def index(request):
    return web.FileResponse(os.path.join(WEB_DIR, "static", "index.html"))

# ---------- жизненный цикл ----------
def on_message(msg):
    hub = APP_HUB["hub"]; world = APP_HUB["world"]
    async def deliver():
        await hub.emit_to(msg["recipient"], {"type": "msg", "message": msg})
        s = hub.sessions.get(msg["recipient"])
        if s: await world.push(s, force=True)
        if msg["sender"]:
            await hub.emit_to(msg["sender"], {"type": "msg_echo", "message": msg})
    try:
        asyncio.get_running_loop().create_task(deliver())
    except RuntimeError:
        pass

APP_HUB = {}

async def bootstrap(app):
    init_accounts()
    from database.db import init_db
    from func.game_manager import game_manager
    from func.commands import setup_commands
    from func.social_commands import setup_social_commands
    await init_db(); await game_manager.load_all_players()
    game_manager.game_channel = 0
    hub = app["hub"]; hub.bot._hub = hub
    setup_commands(hub.bot, game_manager); setup_social_commands(hub.bot)
    compat.HUB = hub
    compat.bind_loop()
    await compat.register_debug(hub.bot, game_manager)

    messenger = Messenger(MSG_DB, ACCOUNTS, on_message)
    messenger.init()
    summary = messenger.import_legacy(LEGACY)
    log.warning("Мессенджер: %s", summary)
    app["messenger"] = messenger; hub.messenger = messenger

    world = World(hub, messenger, server_info())
    app["world"] = world; hub.world = world
    APP_HUB["hub"] = hub; APP_HUB["world"] = world
    app["world_task"] = world.start()

    if os.environ.get("WC_EVENTS") == "1":
        from func.global_events import run_global_events
        app["events"] = asyncio.create_task(run_global_events(hub.bot, game_manager))
    if os.environ.get("WC_AUTOSAVE", "1") == "1":
        from utils.autosave import autosaver
        autosaver.start(hub.bot, game_manager)
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
    print(f"  PIN сервера:   {'включён' if PIN else 'выключен (задай WC_PIN для защиты)'}")
    print(f"  Команд: {len(COMMANDS)}   БД игры: {os.path.join(BASE, 'metro.db')}")
    print("=" * 62 + "\n")

async def shutdown(app):
    for key in ("events", "world_task"):
        t = app.get(key)
        if t: t.cancel()
    from database.db import close_db
    await close_db()

def make_app():
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app["hub"] = Hub()
    app.on_startup.append(bootstrap); app.on_cleanup.append(shutdown)
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
    map_api.setup(app)  # <--- ДОБАВЛЕНО: регистрация роутов карты
    return app

async def _serve():
    import contextlib
    app = make_app()
    runner = web.AppRunner(app, access_log=None, shutdown_timeout=3.0)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT, reuse_address=True)
    await site.start()
    stop = asyncio.Event()
    try:
        await stop.wait()
    except asyncio.CancelledError:
        pass
    finally:
        with contextlib.suppress(Exception):
            await runner.cleanup()                      # on_cleanup -> close_db()
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in pending:
            t.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*pending, return_exceptions=True)

if __name__ == "__main__":
    import contextlib
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(_serve())
    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        print("\nОстановка сервера…")
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            loop.run_until_complete(task)
    finally:
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()
    print("Сервер остановлен, БД закрыта.")