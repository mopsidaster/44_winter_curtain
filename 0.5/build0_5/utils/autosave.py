# -*- coding: utf-8 -*-
# utils/autosave.py - Фоновое автосохранение игроков

import asyncio
from utils.logger import get_logger
from database.db import save_player

logger = get_logger()

class AutoSaver:
    def __init__(self):
        self.dirty_players = set()
        self.game_manager = None

    def start(self, bot, game_manager):
        self.game_manager = game_manager
        asyncio.create_task(self._loop(bot))

    def mark_dirty(self, player):
        """Помечает игрока для сохранения в БД."""
        if player:
            self.dirty_players.add(player.user_id)

    async def _loop(self, bot):
        await bot.wait_until_ready()
        logger.info("💾 [AutoSave] Система автосохранения запущена")

        while not bot.is_closed():
            await asyncio.sleep(120) # Сохраняем раз в 2 минуты

            if not self.dirty_players:
                continue

            logger.info(f"💾 [AutoSave] Сохраняем {len(self.dirty_players)} игроков...")
            for user_id in list(self.dirty_players):
                player = self.game_manager.get_player(user_id)
                if player:
                    try:
                        await save_player(player)
                    except Exception as e:
                        logger.error(f"Ошибка сохранения {user_id}: {e}")
                self.dirty_players.discard(user_id)

autosaver = AutoSaver()