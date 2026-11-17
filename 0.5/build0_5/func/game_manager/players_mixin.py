# -*- coding: utf-8 -*-
# func/game_manager/players_mixin.py - Управление игроками (0.4.7.8)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено из game_manager.py
#   0.4.6   — загрузка бригад при старте
#   0.4.7.8 — смерть = вайп персонажа (полное удаление из БД и памяти)

import asyncio
import traceback

from config.map_config import BALANCE

from ..player import Player
from ..map_data import MAP_DATA
from ..station_utils import has_station_type
from ..combat import combat_manager
from ..disease_system import ensure_disease_fields
from ..cold_system import reset_cold, ensure_cold_fields
from database.db import save_player, get_all_players, delete_player

from utils.logger import get_logger

logger = get_logger()


class PlayersMixin:
    """Загрузка, создание, поиск и вайп игроков."""

    async def load_all_players(self):
        try:
            players_data = await get_all_players()
            logger.info(f"Найдено записей в БД: {len(players_data)}")

            tasks = []
            for data in players_data:
                if data['user_id'] not in self.players:
                    task = asyncio.create_task(self._load_single_player(data))
                    tasks.append(task)

            if tasks:
                await asyncio.gather(*tasks)

            try:
                from ..social.brigade_manager import brigade_manager
                await brigade_manager.load_all()
            except Exception as e:
                logger.error(f"Ошибка загрузки бригад: {e}")

            logger.info(f"Загружено игроков в память: {len(self.players)}")
        except Exception as e:
            logger.error(f"Ошибка загрузки игроков: {e}")
            logger.error(traceback.format_exc())

    async def _load_single_player(self, data: dict):
        try:
            player = Player(
                data['user_id'],
                data.get('username', 'Unknown'),
                data.get('name', 'Безымянный'),
                data
            )
            ensure_disease_fields(player)
            ensure_cold_fields(player)
            self.players[data['user_id']] = player
            logger.debug(f"Загружен игрок: {player.name}")
        except Exception as e:
            logger.error(f"Ошибка загрузки игрока {data.get('name', 'unknown')}: {e}")
            logger.error(traceback.format_exc())

    def add_player(self, user_id: int, username: str, name: str) -> Player:
        if user_id not in self.players:
            player = Player(user_id, username, name)
            ensure_disease_fields(player)
            ensure_cold_fields(player)
            self.players[user_id] = player
            asyncio.create_task(save_player(player))
            logger.info(f"Создан новый игрок: {name}")
        return self.players[user_id]

    def get_player(self, user_id: int):
        return self.players.get(user_id)

    def get_alive_players(self) -> list:
        return list(filter(lambda p: p.is_alive, self.players.values()))

    def get_players_by_location(self, location: str) -> list:
        return list(filter(
            lambda p: p.location == location and p.is_alive,
            self.players.values()
        ))

    async def revive_player(self, user_id: int) -> str:
        """
        0.4.8: смерть = вайп персонажа.
        Удаляет все данные: фракции, лояльность, задачи, пролог.
        Игрок создаёт персонажа заново через /start.
        """
        player = self.get_player(user_id)
        if not player:
            return "❌ Персонаж не найден!"

        if player.is_alive:
            return "❌ Вы еще живы!"

        player_name = player.name

        # === 1. Выход из боёв ===
        try:
            if combat_manager.get_combat(user_id):
                combat_manager.end_combat(user_id)
        except Exception as e:
            logger.error(f"[WIPE] combat_manager: {e}")

        try:
            from ..combat.pvp_manager import pvp_manager
            if pvp_manager.is_user_in_combat(user_id):
                combat = pvp_manager.get_combat_by_user(user_id)
                if combat:
                    pvp_manager.end_combat(combat.combat_id)
        except Exception as e:
            logger.error(f"[WIPE] pvp_manager: {e}")

        # === 2. Выход из бригады ===
        try:
            from ..social.brigade_manager import brigade_manager
            brigade = brigade_manager.get_user_brigade(user_id)
            if brigade:
                if brigade.is_leader(user_id):
                    await brigade_manager.handle_leader_left(brigade.brigade_id)
                else:
                    await brigade_manager.remove_member(brigade.brigade_id, user_id)
        except Exception as e:
            logger.error(f"[WIPE] brigade_manager: {e}")

        # === 3. Удаление из памяти ===
        self.players.pop(user_id, None)

        # === 4. Удаление из БД ===
        try:
            from database.db import delete_player
            await delete_player(user_id)
        except Exception as e:
            logger.error(f"[WIPE] delete_player: {e}")

        logger.info(
            f"[WIPE] Персонаж '{player_name}' (id={user_id}) удалён после смерти. "
            f"Все данные (фракции, задачи, пролог) сброшены."
        )

        return (
            f"💀 **{player_name}** погиб в Метро. Персонаж удалён.\n\n"
            f"🔁 Введите `/start`, чтобы создать нового персонажа.\n"
            f"⚠️ Ключ доступа сохраняется — заново вводить не нужно.\n"
            f"📖 Пролог и обучение проходятся заново."
        )