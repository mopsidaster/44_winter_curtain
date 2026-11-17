# -*- coding: utf-8 -*-
# func/game_manager/combat_start_mixin.py - Старт боя (0.4.8.6)
#
# ИСТОРИЯ:
#   0.4.5   — 100% спавн Рейдера при raider_raid
#   0.4.6   — поддержка групп
#   0.4.7   — спавн Мерзляков/Стража на «на_поверхности»
#   0.4.7.2 — surface-only через forced_enemy_ids
#   0.4.8.6 — ФИКС: при переходе «метро → поверхность» спавн идёт
#             через surface-пул (флаг _transition_to_surface).

import asyncio
import random
import discord
import traceback

from ..player import Player
from ..map_data import MAP_DATA
from ..combat import combat_manager
from ..global_events import is_event_active, is_raider_raid_zone
from ..social.brigade_manager import brigade_manager
from ..social.brigade import STATE_ACTIVE

from utils.logger import get_logger

logger = get_logger()

SURFACE_ONLY_ENEMIES = {
    "мерзляк_вождь",
    "мерзляк_охотник",
    "мерзляк",
    "страж",
    "демон",
    "жукопаук",  # 0.4.8.6
}


class CombatStartMixin:

    def _get_brigade_allies(self, leader: Player) -> list:
        brigade = brigade_manager.get_user_brigade(leader.user_id)
        if not brigade or not brigade.is_active():
            return []

        allies = []
        for uid in brigade.get_member_ids():
            if uid == leader.user_id:
                continue
            ally = self.get_player(uid)
            if ally and ally.is_alive and ally.location == leader.location:
                allies.append(ally)
        return allies

    def _is_surface_station(self, station_id: str) -> bool:
        if not station_id:
            return False
        station = MAP_DATA["станции"].get(station_id, {})
        return station.get("type") == "на_поверхности"

    def _start_mutant_encounter(self, player: Player,
                                interaction: discord.Interaction = None,
                                hostile: bool = None) -> str:
        if combat_manager.get_combat(player.user_id):
            return "⚔️ Вы уже в бою! Завершите текущий бой."

        location_data = MAP_DATA["станции"][player.location]
        danger_level = location_data.get("danger", 3)
        is_surface = location_data.get("type") == "на_поверхности"

        # 0.4.8.6: если переход на поверхность — считаем поверхностью
        if getattr(player, '_transition_to_surface', False):
            is_surface = True

        if hostile is None:
            hostile = location_data.get("hostile", False)
            if getattr(player, 'faction', 'loners') == "bandits":
                hostile = False

        if is_raider_raid_zone(player.location, self):
            hostile = True

        if is_event_active('mutant_wave', self):
            danger_level = min(danger_level + 1, 5)

        allies = self._get_brigade_allies(player)

        if is_surface and not hostile:
            return self._start_surface_encounter(player, interaction, allies)

        channel = None

        if interaction:
            channel = interaction.channel
            if channel:
                self.game_channel = channel.id
                asyncio.create_task(
                    self._start_combat_with_response(
                        interaction, player, danger_level, hostile, allies
                    )
                )
                for a in [player] + allies:
                    asyncio.create_task(self._safe_save(a))
                return ""

        if self.game_channel:
            try:
                import main
                bot = main.bot if hasattr(main, 'bot') else None
                if bot:
                    channel = bot.get_channel(self.game_channel)
                    if channel:
                        asyncio.create_task(
                            self._start_combat_no_interaction(
                                player, danger_level, channel, hostile, allies
                            )
                        )
                        for a in [player] + allies:
                            asyncio.create_task(self._safe_save(a))
                        return ""
            except Exception as e:
                logger.error(f"Ошибка получения канала: {e}")

        try:
            import main
            bot = main.bot if hasattr(main, 'bot') else None
            if bot:
                for guild in bot.guilds:
                    for text_channel in guild.text_channels:
                        if text_channel.permissions_for(guild.me).send_messages:
                            channel = text_channel
                            self.game_channel = channel.id
                            asyncio.create_task(
                                self._start_combat_no_interaction(
                                    player, danger_level, channel, hostile, allies
                                )
                            )
                            for a in [player] + allies:
                                asyncio.create_task(self._safe_save(a))
                            return ""
        except Exception as e:
            logger.error(f"Ошибка поиска канала: {e}")

        return "❌ Не удалось начать бой: канал не найден."

    def _start_surface_encounter(self, player: Player,
                                 interaction: discord.Interaction,
                                 allies: list) -> str:
        """0.4.8.6: поверхность — Демон 20%, Стражи 40%, Вождь 15%, стая."""
        enemy_ids = []

        demon_chance = 20
        strazh_chance = 40
        boss_chance = 15

        roll = random.randint(1, 100)

        if roll <= demon_chance:
            enemy_ids = ["демон"]
            logger.info(f"[SURFACE] Демон (босс): 1")
        elif roll <= demon_chance + strazh_chance:
            count = random.randint(1, 3)
            enemy_ids = ["страж"] * count
            logger.info(f"[SURFACE] Стая Стражей: {count}")
        elif roll <= demon_chance + strazh_chance + boss_chance:
            enemy_ids = ["мерзляк_вождь"]
            companions_count = random.randint(1, 2)
            for _ in range(companions_count):
                enemy_ids.append(random.choice(["мерзляк", "мерзляк_охотник"]))
            logger.info(f"[SURFACE] Стая с Вождём: {enemy_ids}")
        else:
            count = random.randint(1, 3)
            for _ in range(count):
                enemy_ids.append(random.choice(["мерзляк", "мерзляк_охотник"]))
            logger.info(f"[SURFACE] Стая без Вождя: {enemy_ids}")

        for eid in list(enemy_ids):
            if eid not in SURFACE_ONLY_ENEMIES:
                logger.warning(
                    f"[SURFACE] Попытка добавить '{eid}' в surface-энкаунтер — пропущено"
                )
                enemy_ids.remove(eid)

        if interaction:
            channel = interaction.channel
            if channel:
                self.game_channel = channel.id
                asyncio.create_task(self._start_combat_with_response_forced(
                    interaction, player, danger_level=5, hostile=False,
                    allies=allies, forced_enemy_ids=enemy_ids,
                ))
                for a in [player] + (allies or []):
                    asyncio.create_task(self._safe_save(a))
                return ""

        return ""

    async def _start_combat_with_response_forced(self, interaction, player,
                                                 danger_level, hostile,
                                                 allies, forced_enemy_ids):
        try:
            from ..combat import start_combat as start_combat_func
        except Exception as e:
            logger.error(f"❌ Ошибка импорта start_combat: {e}")
            return

        try:
            self.game_channel = interaction.channel.id
            embed, view = await start_combat_func(
                interaction, player, danger_level,
                hostile_station=hostile,
                extra_players=allies or [],
                forced_enemy_ids=forced_enemy_ids,
            )
            logger.info(f"[SURFACE] Бой отправлен: {forced_enemy_ids}")
        except Exception as e:
            logger.error(f"Ошибка отправки боя: {e}")
            logger.error(traceback.format_exc())

    async def _safe_save(self, player: Player):
        from database.db import save_player
        try:
            await save_player(player)
        except Exception as e:
            logger.error(f"Ошибка сохранения игрока {player.name}: {e}")

    async def _start_combat_with_response(self, interaction, player, danger_level,
                                          hostile=False, allies=None):
        try:
            from ..combat import start_combat as start_combat_func
        except Exception as e:
            logger.error(f"❌ Ошибка импорта start_combat: {e}")
            raise

        try:
            self.game_channel = interaction.channel.id
            embed, view = await start_combat_func(
                interaction, player, danger_level,
                hostile_station=hostile,
                extra_players=allies or [],
            )
            logger.info(f"Бой отправлен для {player.name} (+{len(allies or [])} союз.)")
        except Exception as e:
            logger.error(f"Ошибка отправки боя: {e}")
            logger.error(traceback.format_exc())

    async def _start_combat_no_interaction(self, player, danger_level, channel,
                                           hostile=False, allies=None):
        try:
            from ..combat import start_combat_no_interaction as start_combat_func
        except Exception as e:
            logger.error(f"❌ Ошибка импорта: {e}")
            return

        try:
            embed, view = await start_combat_func(
                player, danger_level, channel,
                hostile_station=hostile,
                extra_players=allies or [],
            )
            if embed and view:
                await channel.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка отправки боя: {e}")

    def encounter_mutant(self, user_id: int, interaction: discord.Interaction = None) -> str:
        player = self.get_player(user_id)
        if not player:
            return "❌ Персонаж не найден!"
        self._start_mutant_encounter(player, interaction)
        return "⚔️_БОЙ"

    async def check_raider_raid_early_end(self, player, killed_mutant_ids: list) -> bool:
        if not is_event_active('raider_raid', self):
            return False
        if getattr(self, 'raider_raid_killed', False):
            return False
        if 'рейдер' not in killed_mutant_ids:
            return False

        self.raider_raid_killed = True
        logger.info(f"☠️ Рейдер убит игроком {player.name} — ивент завершается досрочно")

        from ..global_events import current_event, end_event
        try:
            import main
            bot = main.bot if hasattr(main, 'bot') else None
        except Exception:
            bot = None

        if bot and current_event.active and current_event.event \
                and current_event.event.get('id') == 'raider_raid':
            if current_event.task:
                current_event.task.cancel()
                current_event.task = None
            try:
                await end_event(bot, self, current_event.event)
            except Exception as e:
                logger.error(f"Ошибка завершения raider_raid: {e}")
            try:
                from ..global_events import get_event_channel
                channel = await get_event_channel(bot, self)
                if channel:
                    await channel.send(
                        f"🎉 **{player.name}** убил Рейдера! "
                        f"Рейдерский захват завершён досрочно."
                    )
            except Exception as e:
                logger.error(f"Ошибка оповещения: {e}")
            return True

        return False