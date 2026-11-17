# -*- coding: utf-8 -*-
# func/combat/manager.py - Менеджер боёв (0.4.7.6)
#
# ИСТОРИЯ:
#   0.4.4.7 — вынесено из combat.py
#   0.4.5   — should_spawn_raider
#   0.4.6   — extra_players
#   0.4.7   — forced_enemy_ids
#   0.4.7.2 — защита от surface-only
#   0.4.7.3 — 2 спутника Вождя
#   0.4.7.6 — Уровень Мутации мутантов

import asyncio
import random
import discord
import traceback
from typing import Dict, Optional, List

from ..weapon_system import get_weapon, get_magazine
from ..player import Player
from utils.logger import get_logger
from database.db import save_player
from config.map_config import BALANCE

from .combatant import Combatant
from .combat import Combat
from .helpers import (
    get_mutant_data,
    get_random_enemy,
    get_enemies_count,
    pick_enemy_type,
    SURFACE_ONLY_ENEMIES,
)
from .mutation import roll_mutation_level, apply_mutation_to_enemy, can_mutate
from ..spec_weapons.raider import (
    should_spawn_raider,
    get_raider_weapon_setup,
    get_raider_armor_setup,
    get_raider_body_parts,
    get_companion_ids,
)


logger = get_logger()

MERZLYAK_COMPANION_CHOICES = ["мерзляк", "мерзляк_охотник"]


class CombatManager:
    def __init__(self):
        self.active_combats: Dict[int, Combat] = {}
        self.combat_messages: Dict[int, discord.Message] = {}

    def get_combat(self, user_id: int) -> Optional[Combat]:
        return self.active_combats.get(user_id)

    def start_combat(self, player: Player, danger_level: int, channel: discord.TextChannel,
                     hostile_station: bool = False,
                     extra_players: List[Player] = None,
                     forced_enemy_ids: List[str] = None) -> Combat:
        enemy_type = pick_enemy_type(danger_level, hostile_station)

        enemies = []
        mutant_ids = []

        _gm = None
        try:
            from ..game_manager import game_manager as _gm_singleton
            _gm = _gm_singleton
        except Exception as e:
            logger.error(f"Не удалось получить game_manager: {e}")

        spawn_raider = False
        if hostile_station and not forced_enemy_ids:
            try:
                if should_spawn_raider(_gm, player.location):
                    spawn_raider = True
            except Exception as e:
                logger.error(f"Ошибка проверки should_spawn_raider: {e}")
                spawn_raider = should_spawn_raider()

        if spawn_raider:
            logger.info(f"☠️ БОСС РЕЙДЕР появился на {player.location}!")
            raider_combatants = self._create_raider_squad(player, danger_level)
            if raider_combatants:
                enemies.extend(raider_combatants)
                mutant_ids = ['рейдер'] + get_companion_ids()
        # 0.4.8: спавн NPC фракции при враждебности
        faction_npc_spawned = False
        if not forced_enemy_ids:
            try:
                from ..factions import get_faction_enemy_type, get_faction_human_mutant_id, get_faction_human_display_name
                hostile_faction = get_faction_enemy_type(player, player.location)
                if hostile_faction:
                    human_id = get_faction_human_mutant_id(hostile_faction)
                    human_data_base = get_mutant_data(human_id)
                    if human_data_base:
                        # Клонируем данные для NPC фракции
                        human_data = dict(human_data_base)
                        human_data['faction_id'] = hostile_faction
                        human_data['display_name'] = get_faction_human_display_name(hostile_faction)
                        human_data['name'] = human_data['display_name']

                        danger = danger_level
                        enemies_count = get_enemies_count(danger, human_id)

                        for _ in range(enemies_count):
                            enemy = Combatant(
                                player, is_mutant=False, is_human=True,
                                mutant_id=human_id, mutant_data=human_data,
                            )
                            # Переопределяем display_name
                            enemy.display_name = human_data['display_name']
                            mutant_ids.append(human_id)
                            enemies.append(enemy)

                        faction_npc_spawned = True
                        logger.info(
                            f"[FACTIONS] Спавн {enemies_count} × {human_data['display_name']} "
                            f"(фракция {hostile_faction}) на {player.location}"
                        )
            except Exception as e:
                logger.error(f"[FACTIONS] Ошибка спавна фракционных NPC: {e}")
                logger.error(traceback.format_exc())
        if forced_enemy_ids:
            final_forced = list(forced_enemy_ids)

            if "мерзляк_вождь" in final_forced:
                companions_present = [
                    eid for eid in final_forced
                    if eid in ("мерзляк", "мерзляк_охотник")
                ]
                missing = 2 - len(companions_present)
                if missing > 0:
                    for _ in range(missing):
                        final_forced.append(random.choice(MERZLYAK_COMPANION_CHOICES))
                    logger.info(
                        f"[COMBAT] К Вождю добавлено {missing} спутник(ов): {final_forced}"
                    )

            for enemy_id in final_forced:
                enemy_data = get_mutant_data(enemy_id)
                if not enemy_data:
                    logger.warning(f"[COMBAT] Нет данных для врага '{enemy_id}'")
                    continue

                mutant_ids.append(enemy_id)

                if enemy_data.get('is_human', False):
                    enemy = Combatant(player, is_mutant=False, is_human=True,
                                      mutant_id=enemy_id, mutant_data=enemy_data)
                else:
                    enemy = Combatant(player, is_mutant=True, is_human=False,
                                      mutant_id=enemy_id, mutant_data=enemy_data)

                if enemy.is_mutant:
                    base_health = enemy_data.get('base_health', 6.0)
                    health_per_danger = enemy_data.get('health_per_danger', 0)
                    enemy.lives = base_health + (health_per_danger * danger_level)
                    enemy.max_lives = enemy.lives

                    # 0.4.7.6: мутация
                    if can_mutate(enemy_data):
                        lvl = roll_mutation_level(danger_level)
                        apply_mutation_to_enemy(enemy, lvl, danger_level)

                enemies.append(enemy)

        if not enemies:
            enemy_id, enemy_data = get_random_enemy(danger_level, enemy_type)

            if enemy_id in SURFACE_ONLY_ENEMIES:
                logger.warning(
                    f"[COMBAT] get_random_enemy вернул surface-only '{enemy_id}' — "
                    f"подменяем на 'упырь'"
                )
                enemy_id = "упырь"
                enemy_data = get_mutant_data("упырь")

            enemies_count = get_enemies_count(danger_level, enemy_id)

            for _ in range(enemies_count):
                mutant_ids.append(enemy_id)

                if enemy_data.get('is_human', False):
                    enemy = Combatant(player, is_mutant=False, is_human=True,
                                      mutant_id=enemy_id, mutant_data=enemy_data)
                else:
                    enemy = Combatant(player, is_mutant=True, is_human=False,
                                      mutant_id=enemy_id, mutant_data=enemy_data)

                if enemy.is_mutant:
                    base_health = enemy_data.get('base_health', 6.0)
                    health_per_danger = enemy_data.get('health_per_danger', 1.0)
                    enemy.lives = base_health + (health_per_danger * danger_level)
                    enemy.max_lives = enemy.lives

                    # 0.4.7.6: мутация
                    if can_mutate(enemy_data):
                        lvl = roll_mutation_level(danger_level)
                        apply_mutation_to_enemy(enemy, lvl, danger_level)

                enemies.append(enemy)

        player._combat_mutant_id = mutant_ids[0] if mutant_ids else None
        player._combat_mutant_ids = mutant_ids

        combat = Combat(player, enemies, danger_level, mutant_ids=mutant_ids)
        combat.channel = channel

        if extra_players:
            for ally in extra_players:
                if ally and ally.is_alive and ally.user_id != player.user_id:
                    combat.extra_players.append(ally)
                    ally.combat_mode = True
                    ally.combat_target = id(combat)

        self.active_combats[player.user_id] = combat
        for ally in combat.extra_players:
            self.active_combats[ally.user_id] = combat

        asyncio.create_task(save_player(player))
        for ally in combat.extra_players:
            asyncio.create_task(save_player(ally))

        enemy_names = ", ".join([e.display_name for e in enemies])
        logger.info(
            f"Бой начат: {player.name}"
            + (f" + {len(combat.extra_players)} союз." if combat.extra_players else "")
            + f" vs [{enemy_names}], дистанция: {combat.distance}"
        )
        return combat

    def _create_raider_squad(self, player: Player, danger_level: int) -> list:
        combatants = []

        raider_data = get_mutant_data('рейдер')
        if not raider_data or not isinstance(raider_data, dict):
            logger.warning("Данные Рейдера не найдены — отряд не создан")
            return []

        try:
            raider = Combatant(player, is_mutant=False, is_human=True,
                               mutant_id='рейдер', mutant_data=raider_data)

            weapon_setup = get_raider_weapon_setup()
            raider.weapon = weapon_setup.get('weapon', 'вск_94')
            raider.weapon_ammo_type = weapon_setup.get('ammo_type', 'бронебойные')
            raider.weapon_modules = weapon_setup.get('modules', {})
            raider.equipped_magazine = weapon_setup.get('magazine')
            if not raider.equipped_magazine:
                weapon_data = get_weapon(raider.weapon)
                if isinstance(weapon_data, dict):
                    mags = weapon_data.get('magazines', [])
                    if isinstance(mags, list) and mags:
                        raider.equipped_magazine = mags[0]

            armor_setup = get_raider_armor_setup()
            raider.equipped_armor_id = armor_setup.get('armor')
            raider.equipped_helmet_id = armor_setup.get('helmet')

            raider.body_parts = get_raider_body_parts()
            raider.lives = sum(p["hp"] for p in raider.body_parts.values())
            raider.max_lives = raider.lives

            cfg = BALANCE.get('healing', {})
            raider.medkits = list(cfg.get('raider_medkits', []))

            combatants.append(raider)
        except Exception as e:
            logger.error(f"Ошибка создания Рейдера: {e}")
            logger.error(traceback.format_exc())
            return []

        for companion_id in get_companion_ids():
            comp_data = get_mutant_data(companion_id)
            if not comp_data or not isinstance(comp_data, dict):
                continue
            try:
                comp = Combatant(player, is_mutant=True, is_human=False,
                                 mutant_id=companion_id, mutant_data=comp_data)
                base_health = comp_data.get('base_health', 10.0)
                health_per_danger = comp_data.get('health_per_danger', 1.5)
                comp.lives = base_health + (health_per_danger * danger_level)
                comp.max_lives = comp.lives
                combatants.append(comp)
            except Exception as e:
                logger.error(f"Ошибка создания компаньона {companion_id}: {e}")

        return combatants

    def end_combat(self, user_id: int):
        combat = self.active_combats.get(user_id)
        if not combat:
            return

        combat.is_active = False
        combat.player.combat_mode = False
        for ally in combat.extra_players:
            ally.combat_mode = False

        all_ids = [combat.player.user_id] + [a.user_id for a in combat.extra_players]
        for uid in all_ids:
            self.active_combats.pop(uid, None)
            self.combat_messages.pop(uid, None)

        logger.info(f"Бой завершён (участников: {len(all_ids)})")


combat_manager = CombatManager()