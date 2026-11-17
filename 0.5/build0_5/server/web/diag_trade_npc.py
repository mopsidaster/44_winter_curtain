# -*- coding: utf-8 -*-
"""Проход по торговле и NPC на тестовом персонаже: печатает каждый экран и полный
трейсбек любой ошибки. Запуск: python server\web\diag_trade_npc.py"""
import asyncio, os, sys, logging

WEB = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(WEB))
sys.path[:0] = [WEB, BASE]; os.chdir(BASE)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

import discord_shim; discord_shim.install()
import compat; compat.install()
from bridge import Hub
from database.db import init_db, create_access_key, delete_player
from func.game_manager import game_manager
from func.commands import setup_commands
from func.social_commands import setup_social_commands

TEST_ID = 999000002
SKIP = ("вайп", "удалить", "сброс", "возрод")
FAILS = []


def buttons(op):
    return [b for r in (op.get("view") or {}).get("rows", []) for b in r if b["type"] == "button"]


def selects(op):
    return [c for r in (op.get("view") or {}).get("rows", []) for c in r if c["type"] == "select"]


def last_view(out):
    return next((o for o in reversed(out) if o.get("view")), None)


def last_modal(out):
    return next((o for o in reversed(out) if o["op"] == "modal"), None)


def vid(op):
    return op.get("view_id") or op["view"]["id"]


def dump(out, tag):
    for op in out:
        if op["op"] in ("send", "edit"):
            titles = [e.get("title") for e in op.get("embeds", [])]
            print(f"  [{tag}] {op['op']}: {titles}")
            for b in buttons(op):
                print(f"        · {b['label']}")
            for s in selects(op):
                print(f"        ▾ {s.get('placeholder')} ({len(s['options'])} опций)")
        elif op["op"] == "modal":
            print(f"  [{tag}] МОДАЛКА «{op['title']}» {[f['label'] for f in op['fields']]}")
        elif op["op"] == "toast":
            print(f"  [{tag}] {op['kind'].upper()}: {op['text']}")
            if op.get("trace"):
                print(op["trace"])
                FAILS.append((tag, op["text"], op["trace"]))


async def ensure_character(s, out):
    for _ in range(6):
        if game_manager.get_player(TEST_ID):
            return True
        m = last_modal(out)
        if m:
            t = m["title"].lower()
            if "ключ" in t:
                key = await create_access_key("permanent")
                out.clear(); await s.submit(m["id"], {m["fields"][0]["id"]: str(key)})
                dump(out, "key"); continue
            if "создание" in t or "персонаж" in t:
                vals = {m["fields"][0]["id"]: "Диаг Тест"}
                for f in m["fields"][1:]:
                    vals[f["id"]] = "диагностика"
                out.clear(); await s.submit(m["id"], vals); dump(out, "create"); continue
        v = last_view(out)
        b = next((x for x in buttons(v) if "создать" in (x["label"] or "").lower()), None) if v else None
        if b:
            out.clear(); await s.click(vid(v), b["id"]); dump(out, "click"); continue
        return False
    return game_manager.get_player(TEST_ID) is not None


async def press(s, out, label, tag):
    v = last_view(out)
    if not v:
        print(f"  [{tag}] нет активного экрана"); return False
    b = next((x for x in buttons(v) if label.lower() in (x["label"] or "").lower()
              and not any(k in (x["label"] or "").lower() for k in SKIP)), None)
    if not b:
        print(f"  [{tag}] кнопка «{label}» не найдена"); return False
    out.clear(); await s.click(vid(v), b["id"]); dump(out, tag)
    return True


async def explore(s, out, tag, depth=2):
    """Прожимает верхний ряд кнопок и первый пункт селекта, собирая ошибки."""
    v = last_view(out)
    if not v:
        return
    for sel in selects(v)[:1]:
        if sel["options"]:
            out.clear()
            await s.click(vid(v), sel["id"], [sel["options"][0]["value"]])
            dump(out, tag + "/select")
            v = last_view(out) or v
    for b in buttons(v)[:4]:
        lbl = (b["label"] or "").lower()
        if any(k in lbl for k in SKIP) or "назад" in lbl:
            continue
        cur = last_view(out)
        if not cur:
            break
        target = next((x for x in buttons(cur) if x["id"] == b["id"]), None)
        if not target:
            continue
        out.clear(); await s.click(vid(cur), target["id"]); dump(out, f"{tag}/{b['label']}")
        m = last_modal(out)
        if m:
            vals = {}
            for f in m["fields"]:
                vals[f["id"]] = "1" if not f["multiline"] else "тест"
            out.clear(); await s.submit(m["id"], vals); dump(out, f"{tag}/{b['label']}/modal")
        if depth > 1:
            await explore(s, out, tag + "/" + (b["label"] or ""), depth - 1)
        await s.command("menu"); out.clear()
        await press(s, out, tag.split("/")[0], tag)


async def main():
    await init_db()
    await delete_player(TEST_ID)
    players = getattr(game_manager, "players", None)
    if isinstance(players, dict): players.pop(TEST_ID, None)
    await game_manager.load_all_players()

    hub = Hub(); s = hub.session(TEST_ID, "diag"); out = []
    async def sink(m): out.extend(m["ops"])
    s.add_sink(sink)
    compat.HUB = hub; compat.bind_loop()
    setup_commands(hub.bot, game_manager); setup_social_commands(hub.bot)
    debug = await compat.register_debug(hub.bot, game_manager)
    print("DEBUG-команды:", ["/" + d for d in debug] or "нет")
    try:
        await compat.start_task_board(hub.bot)
    except Exception as e:
        print("Доска заданий:", type(e).__name__, e)

    await s.command("start"); dump(out, "start")
    if not await ensure_character(s, out):
        return print("!! Персонаж не создан")
    v = last_view(out)
    fin = next((x for x in buttons(v) if "заверш" in (x["label"] or "").lower()), None) if v else None
    if fin:
        out.clear(); await s.click(vid(v), fin["id"]); dump(out, "skills")

    print("\n=== ТОРГОВЛЯ ===")
    out.clear(); await s.command("menu"); dump(out, "menu")
    if await press(s, out, "торговл", "Торговля"):
        await explore(s, out, "Торговля", depth=2)

    print("\n=== НЕЗАВИСИМЫЕ ТОРГОВЦЫ ===")
    out.clear(); await s.command("menu")
    if await press(s, out, "торговец", "Торговец"):
        await explore(s, out, "Торговец", depth=2)

    print("\n=== NPC ===")
    out.clear(); await s.command("menu"); dump(out, "menu")
    if await press(s, out, "npc", "NPC"):
        await explore(s, out, "NPC", depth=3)

    print("\n=== DEBUG ===")
    for name in debug[:6]:
        out.clear()
        await s.command(name.split(" ")[0] if " " not in name else name)
        dump(out, "debug:" + name)
        m = last_modal(out)
        if m:
            out.clear()
            await s.submit(m["id"], {f["id"]: "2044metro_dev" for f in m["fields"]})
            dump(out, "debug:" + name + "/password")

    print("\n=== ИТОГ ===")
    print("Ошибок:", len(FAILS))
    for tag, text, _ in FAILS:
        print(" -", tag, ":", text)
    if discord_shim.GAPS:
        print("Не реализовано в адаптере:", ", ".join(discord_shim.GAPS))
    await delete_player(TEST_ID)
    if isinstance(players, dict): players.pop(TEST_ID, None)

asyncio.run(main())