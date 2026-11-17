# -*- coding: utf-8 -*-
"""Проверка веб-адаптера: сам определяет текущий шаг (ключ / создание / кнопка)."""
import asyncio, os, sys

WEB = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(WEB))
sys.path[:0] = [WEB, BASE]; os.chdir(BASE)

import discord_shim; discord_shim.install()
from bridge import Hub
from database.db import init_db, create_access_key, delete_player, get_db
from func.game_manager import game_manager
from func.commands import setup_commands
from func.social_commands import setup_social_commands

TEST_ID = 999000001
KEEP = "--keep" in sys.argv
FRESH = "--fresh" in sys.argv          # сбросить доступ тестового аккаунта


def dump(out, tag):
    for op in out:
        k = op["op"]
        if k in ("send", "edit"):
            t = [e.get("title") for e in op.get("embeds", [])]
            b = [x["label"] for r in (op.get("view") or {}).get("rows", [])
                 for x in r if x["type"] == "button"]
            print(f"  [{tag}] {k}: {t}" + (f" кнопки={b}" if b else ""))
        elif k == "modal":
            print(f"  [{tag}] МОДАЛКА «{op['title']}» поля={[f['label'] for f in op['fields']]}")
        elif k == "toast":
            print(f"  [{tag}] {op['kind'].upper()}: {op['text']}")


def last_modal(out): return next((o for o in reversed(out) if o["op"] == "modal"), None)
def last_view(out):  return next((o for o in reversed(out) if o.get("view")), None)
def vid(op):         return op.get("view_id") or op["view"]["id"]
def button(op, text):
    if not op: return None
    for row in op["view"]["rows"]:
        for b in row:
            if b["type"] == "button" and text.lower() in (b["label"] or "").lower(): return b
    return None


async def reset_access():
    try:
        db = await get_db()
        cur = await db.execute("PRAGMA table_info(access_keys)")
        cols = [r[1] for r in await cur.fetchall()]
        for c in cols:
            if "user" in c.lower():
                await db.execute(f"DELETE FROM access_keys WHERE {c}=?", (TEST_ID,))
        await db.commit()
        print("   доступ тестового аккаунта сброшен")
    except Exception as e:
        print("   сброс доступа пропущен:", e)


async def ensure_character(s, out):
    """Крутит шаги, пока персонаж не появится: ключ -> кнопка -> анкета."""
    for _ in range(6):
        if game_manager.get_player(TEST_ID): return True
        m = last_modal(out)
        if m:
            title = m["title"].lower()
            if "ключ" in title:
                key = await create_access_key("permanent"); print("   ключ:", key)
                out.clear(); await s.submit(m["id"], {m["fields"][0]["id"]: str(key)})
                dump(out, "key"); continue
            if "создание" in title or "персонаж" in title:
                vals = {m["fields"][0]["id"]: "Тест Сталкер"}
                for f in m["fields"][1:]: vals[f["id"]] = "проверка веб-адаптера"
                out.clear(); await s.submit(m["id"], vals); dump(out, "create"); continue
        v = last_view(out); b = button(v, "создать")
        if b:
            out.clear(); await s.click(vid(v), b["id"]); dump(out, "click"); continue
        return False
    return game_manager.get_player(TEST_ID) is not None


async def main():
    print("Python:", sys.version.split()[0])
    await init_db()
    await delete_player(TEST_ID)
    players = getattr(game_manager, "players", None)
    if isinstance(players, dict): players.pop(TEST_ID, None)
    if FRESH: await reset_access()
    await game_manager.load_all_players()

    hub = Hub(); s = hub.session(TEST_ID, "selftest"); out = []
    async def sink(m): out.extend(m["ops"])
    s.sink = sink
    setup_commands(hub.bot, game_manager); setup_social_commands(hub.bot)
    print("1. Команд:", len(discord_shim.COMMANDS))

    print("2. /start")
    await s.command("start"); dump(out, "start")

    print("3. Доводим до персонажа")
    if not await ensure_character(s, out):
        return print("!! Персонаж не создан — пришли вывод выше")
    print("   персонаж:", game_manager.get_player(TEST_ID).name)

    v = last_view(out); fin = button(v, "завершить")
    if fin:
        print("4. Завершаем распределение навыков")
        out.clear(); await s.click(vid(v), fin["id"]); dump(out, "skills")

    print("5. /menu")
    out.clear(); await s.command("menu"); dump(out, "menu")
    v = last_view(out)
    if not v: return print("!! Меню без кнопок — пришли вывод выше")
    print("\nOK: кнопок в меню:",
          sum(1 for r in v["view"]["rows"] for b in r if b["type"] == "button"))

    if not KEEP:
        await delete_player(TEST_ID)
        if isinstance(players, dict): players.pop(TEST_ID, None)
        print("Тестовый персонаж удалён (--keep чтобы оставить).")

asyncio.run(main())