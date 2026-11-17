# -*- coding: utf-8 -*-
# main.py - Точка входа (Билд 0.4.8.2)

import os
import asyncio
import discord
from discord.ext import commands
import traceback
import aiohttp

from func.game_manager import game_manager
from func.commands import setup_commands
from func.social_commands import setup_social_commands
from func.debug_tool import setup_debug_commands  # <-- ВОЗВРАЩЕНО
from func.global_events import run_global_events
from database.db import init_db, close_db
from utils.logger import get_logger
from utils.autosave import autosaver

logger = get_logger()

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = ""
GAME_CHANNEL_ID = 1522572454122360912

bot = None
_events_task: asyncio.Task = None


# ==================== ДИАГНОСТИКА ИМПОРТА ====================

def _check_imports():
    print("=" * 60)
    print("🔎 [CHECK] Диагностика импортов")
    print("=" * 60)

    checks = [
        ("func.combat", None),
        ("func.combat.combatant", "Combatant"),
        ("func.combat.combat", "Combat"),
        ("func.combat.manager", "combat_manager"),
        ("func.combat.api", "handle_combat_action"),
        ("func.views.combat_views", "CombatView"),
        ("func.combat.player_combatant", "PlayerCombatant"),
        ("func.combat.pvp_manager", "pvp_manager"),
        ("func.combat.pvp_combat", "PvPCombat"),
        ("func.combat.api_pvp", "handle_pvp_action"),
        ("func.social.brigade_manager", "brigade_manager"),
        ("func.social_commands", "setup_social_commands"),
        ("func.views.map_render", "MapPaginationView"),
        ("func.factions", None),
        ("func.task_board_manager", "task_board_manager"),
        ("func.views.prologue", "PrologueView"),
        ("func.views.faction_npc", "DialogView"),
        ("func.views.faction_npc.task_board_view", "TaskBoardView"),
        ("func.global_events", "run_global_events"),
        ("func.debug_tool", "setup_debug_commands"), # <-- ВОЗВРАЩЕНО
    ]

    for module_path, attr in checks:
        try:
            if attr:
                mod = __import__(module_path, fromlist=[attr])
                obj = getattr(mod, attr)
                print(f"[CHECK] ✅ {module_path}.{attr}")
            else:
                __import__(module_path)
                print(f"[CHECK] ✅ {module_path}")
        except Exception as e:
            print(f"[CHECK] ❌ {module_path}.{attr or ''}: {e}")
            traceback.print_exc()
            return False

    print("=" * 60)
    print("✅ [CHECK] Все ключевые импорты OK")
    print("=" * 60)
    return True


async def check_discord_api():
    logger.info("🔌 Проверка соединения с Discord API...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "https://discord.com/api/v10/gateway",
                    timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"✅ Discord API доступен (gateway: {data.get('url', '?')})")
                    return True
                else:
                    logger.error(f"❌ Discord API вернул статус {resp.status}")
                    return False
    except asyncio.TimeoutError:
        logger.error("❌ Таймаут подключения к Discord API")
        return False
    except Exception as e:
        logger.error(f"❌ Discord API недоступен: {e}")
        return False


# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

async def main():
    global bot, _events_task

    logger.info("=" * 60)
    logger.info("🚇 ЗАПУСК 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍 БОТА - БИЛД 0.4.8.2")
    logger.info("=" * 60)

    if not TOKEN:
        logger.error("❌ Токен не задан!")
        return

    await check_discord_api()

    try:
        await init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return

    try:
        await game_manager.load_all_players()
        logger.info(f"✅ Загружено игроков: {len(game_manager.players)}")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки игроков: {e}")

    game_manager.game_channel = GAME_CHANNEL_ID

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.presences = True

    bot = commands.Bot(command_prefix='!', intents=intents)

    @bot.event
    async def on_ready():
        global _events_task

        logger.info("=" * 60)
        logger.info(f"✅ БОТ ЗАПУЩЕН как {bot.user}")
        logger.info("=" * 60)

        autosaver.start(bot, game_manager)

        try:
            from func.views.map_render import MapPaginationView
            bot.add_view(MapPaginationView())
        except Exception as e:
            logger.error(f"❌ Ошибка регистрации MapPaginationView: {e}")

        try:
            from func.task_board_manager import task_board_manager
            task_board_manager.start(bot)
        except Exception as e:
            logger.error(f"❌ Ошибка запуска TaskBoardManager: {e}")

        try:
            synced = await bot.tree.sync()
            logger.info(f"✅ Синхронизировано команд: {len(synced)}")
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации: {e}")

        if _events_task is None or _events_task.done():
            _events_task = asyncio.create_task(run_global_events(bot, game_manager))

    @bot.event
    async def on_error(event, *args, **kwargs):
        logger.error(f"❌ Ошибка в событии {event}")
        logger.error(traceback.format_exc())

    setup_commands(bot, game_manager)
    setup_social_commands(bot)
    setup_debug_commands(bot, game_manager)  # <-- ВОЗВРАЩЕНО

    try:
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"❌ ОШИБКА ЗАПУСКА: {e}")
        logger.error(traceback.format_exc())
    finally:
        try:
            await close_db()
        except Exception:
            pass


if __name__ == "__main__":
    if not _check_imports():
        raise SystemExit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")