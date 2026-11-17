# -*- coding: utf-8 -*-
# func/task_board_manager.py - Менеджер доски заданий (0.4.8.3)

import asyncio
import time
import discord

from .factions import generate_tasks_for_faction, get_all_factions
from config.map_config import BALANCE
from utils.logger import get_logger

logger = get_logger()


class TaskBoardManager:
    """Хранит задания по фракциям, обновляет раз в N часов."""

    def __init__(self):
        self.boards: dict[str, list] = {}
        self.last_refresh: dict[str, float] = {}
        self._refresh_task: asyncio.Task = None
        self._bot: discord.Client = None

    def _get_refresh_interval(self) -> int:
        cfg = BALANCE.get('factions', {})
        hours = int(cfg.get('task_board_refresh_hours', 3))
        return hours * 3600

    def get_board(self, faction_id: str, player_location: str = None) -> list:
        """Получить доску заданий фракции (обновляет, если истекла)."""
        now = time.time()
        interval = self._get_refresh_interval()

        if faction_id not in self.boards or (now - self.last_refresh.get(faction_id, 0) > interval):
            # 0.4.8.3: Передаем локацию игрока в генератор
            self.boards[faction_id] = generate_tasks_for_faction(faction_id, player_location)
            self.last_refresh[faction_id] = now
            logger.info(f"[TASKS] Доска обновлена для фракции {faction_id}")

        return self.boards[faction_id]

    def refresh_all(self):
        """Принудительное обновление всех досок."""
        for fid in get_all_factions().keys():
            self.boards[fid] = generate_tasks_for_faction(fid)
            self.last_refresh[fid] = time.time()
        logger.info(f"[TASKS] Все доски обновлены ({len(self.boards)} фракций)")

    def refresh_board_force(self, faction_id: str, player_location: str = None):
        """Принудительное обновление доски конкретной фракции."""
        self.boards[faction_id] = generate_tasks_for_faction(faction_id, player_location)
        self.last_refresh[faction_id] = time.time()
        logger.info(f"[TASKS] Доска принудительно обновлена для {faction_id}")

    def get_task_by_id(self, faction_id: str, task_id: str) -> dict:
        for t in self.get_board(faction_id):
            if t.get("task_id") == task_id:
                return t
        return {}

    async def run_loop(self, bot: discord.Client):
        """Фоновый цикл обновления досок."""
        self._bot = bot
        await bot.wait_until_ready()
        logger.info("[TASKS] Фоновый цикл обновления досок запущен")

        # Первичное обновление
        self.refresh_all()

        interval = self._get_refresh_interval()
        while not bot.is_closed():
            await asyncio.sleep(interval)
            self.refresh_all()

    def start(self, bot: discord.Client):
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self.run_loop(bot))
            logger.info("[TASKS] Запущен фоновый обновлятор заданий")


task_board_manager = TaskBoardManager()