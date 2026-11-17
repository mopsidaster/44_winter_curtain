# -*- coding: utf-8 -*-
"""compat: точечные заплатки адаптера — debug-команды (в т.ч. префиксные),
канал/пользователь/ЛС, bot.loop, tasks.loop. Ничего кроме этих мест не меняет."""
from __future__ import annotations
import asyncio, inspect, logging, sys
import discord_shim as sh

log = logging.getLogger("web.compat")
HUB = None
_BOUND_LOOP = None


def bind_loop():
    global _BOUND_LOOP
    try:
        _BOUND_LOOP = asyncio.get_running_loop()
    except RuntimeError:
        pass


class Ctx:
    """Аналог commands.Context для команд, объявленных через @bot.command()."""
    def __init__(self, interaction):
        self._it = interaction
        self.author = interaction.user
        self.user = interaction.user
        self.bot = interaction.client
        self.client = interaction.client
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.message = interaction.message
        self.prefix = "/"
        self.invoked_with = ""
        self.me = interaction.client.user if interaction.client else None

    async def send(self, content=None, **kw):
        m = await self._it.session.op_send(content, **kw)
        await self._it.session.flush()
        return m

    async def reply(self, content=None, **kw):
        return await self.send(content, **kw)

    def typing(self):
        class _N:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
        return _N()


def _wrap_ctx(f):
    names = list(inspect.signature(f).parameters)[1:]

    async def wrapper(interaction, **params):
        args = [params.get(n) for n in names]
        while args and args[-1] is None:
            args.pop()
        return await f(Ctx(interaction), *args)

    wrapper.__name__ = getattr(f, "__name__", "cmd")
    return wrapper, names


def _register_prefix(name, f, desc):
    wrapper, names = _wrap_ctx(f)
    sh.register_command(name, wrapper, desc)
    sh.COMMANDS[name]["params"] = names
    sh.COMMANDS[name]["choice_params"] = []
    return f


class _PrefixGroup:
    def __init__(self, name):
        self.name = name

    def command(self, *a, **kw):
        sub = kw.get("name") or (a[0] if a and isinstance(a[0], str) else None)

        def deco(f):
            return _register_prefix(f"{self.name} {sub or f.__name__}", f,
                                    kw.get("help") or (f.__doc__ or "").strip().split("\n")[0])
        return deco

    def group(self, *a, **kw):
        sub = kw.get("name") or (a[0] if a and isinstance(a[0], str) else None)

        def deco(f):
            return _PrefixGroup(f"{self.name} {sub or f.__name__}")
        return deco


def _bot_command(self, *a, **kw):
    name = kw.get("name") or (a[0] if a and isinstance(a[0], str) else None)

    def deco(f):
        return _register_prefix(name or f.__name__, f,
                                kw.get("help") or (f.__doc__ or "").strip().split("\n")[0])
    return deco


def _bot_group(self, *a, **kw):
    name = kw.get("name") or (a[0] if a and isinstance(a[0], str) else None)

    def deco(f):
        return _PrefixGroup(name or f.__name__)
    return deco


class _DMChannel:
    def __init__(self, user):
        self.user = user
        self.id = user.id
        self.recipient = user

    async def send(self, content=None, **kw):
        s = HUB.sessions.get(self.user.id) if HUB else None
        if s is None or not s.sinks:
            log.info("ЛС для офлайн-игрока %s пропущены", self.user.id)
            return None
        m = await s.op_send(content, **kw)
        await s.flush()
        if HUB.world:
            await HUB.world.touch(s.user.id)
        return m

    async def fetch_message(self, mid):
        s = HUB.sessions.get(self.user.id) if HUB else None
        return sh.Message(s, mid)


async def _user_send(self, content=None, **kw):
    return await _DMChannel(self).send(content, **kw)


async def _create_dm(self):
    return _DMChannel(self)


def _loop_prop(self):
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return _BOUND_LOOP


def _tasks_loop(**kw):
    period = (kw.get("seconds", 0) + kw.get("minutes", 0) * 60 + kw.get("hours", 0) * 3600) or 60

    def deco(f):
        state = {"task": None}

        async def runner(*a, **k):
            while True:
                try:
                    await f(*a, **k)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("tasks.loop %s", getattr(f, "__name__", "?"))
                await asyncio.sleep(period)

        def start(*a, **k):
            if state["task"] is None or state["task"].done():
                state["task"] = asyncio.ensure_future(runner(*a, **k))
            return state["task"]

        def cancel():
            if state["task"] and not state["task"].done():
                state["task"].cancel()

        def restart(*a, **k):
            cancel()
            return start(*a, **k)

        f.start = start
        f.cancel = cancel
        f.restart = restart
        f.is_running = lambda: bool(state["task"] and not state["task"].done())
        f.before_loop = lambda fn: fn
        f.after_loop = lambda fn: fn
        f.error = lambda fn: fn
        return f
    return deco


def install():
    """Ставится после discord_shim.install() и до импорта func.*."""
    sh.install()
    sh.Client.loop = property(_loop_prop, lambda self, v: None)
    sh.Client.get_all_channels = lambda self: list(self._channels.values())
    sh.Client.get_all_members = lambda self: []
    sh.Client.get_user = lambda self, uid: sh.User(uid, str(uid))
    sh.Client.fetch_user = lambda self, uid: _coro(sh.User(uid, str(uid)))
    sh.Client.get_guild = lambda self, gid: sh.Guild(HUB)
    sh.Client.fetch_guild = lambda self, gid: _coro(sh.Guild(HUB))
    sh.Bot.command = _bot_command
    sh.Bot.group = _bot_group
    sh.User.send = _user_send
    sh.User.create_dm = _create_dm
    sh.User.dm_channel = property(lambda self: _DMChannel(self))
    sh.Member.send = _user_send
    sh.Member.create_dm = _create_dm
    sh.Member.dm_channel = property(lambda self: _DMChannel(self))
    sys.modules["discord.ext.tasks"].loop = _tasks_loop
    return True


async def _coro(value):
    return value


async def register_debug(bot, game_manager):
    """Регистрирует все debug-команды (slash и префиксные) в веб-палитре."""
    from func.debug_tool import setup_debug_commands
    before = set(sh.COMMANDS)
    try:
        res = setup_debug_commands(bot, game_manager)
        if inspect.isawaitable(res):
            await res
    except Exception:
        log.exception("setup_debug_commands упал")
        return []
    added = sorted(set(sh.COMMANDS) - before)
    log.warning("Debug-команды в браузере: %s", ", ".join("/" + n for n in added) or "нет новых")
    return added


async def start_task_board(bot):
    """Доска заданий NPC: ошибки больше не проглатываются молча."""
    from func.task_board_manager import task_board_manager
    res = task_board_manager.start(bot)
    if inspect.isawaitable(res):
        await res
    log.warning("Доска заданий NPC запущена")
    return True