# -*- coding: utf-8 -*-
# func/game_manager/transition_events_mixin.py - Случайные события перехода (0.4.8.9)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено из game_manager.py
#   0.4.7   — локальные события «поверхности»
#   0.4.8.8 — 9 интерактивных ивентов на поверхности Бутовской линии.
#   0.4.8.9 — _trigger_surface_event теперь async и ЖДЁТ завершения ивента
#             через asyncio.Future. Возвращает {"combat_started", "event_text"}.

import random
import asyncio
import discord

from config.map_config import BALANCE

from ..player import Player
from ..disease_system import add_radiation, add_chemical
from ..global_events import is_event_active
from ..combat.helpers import get_spawn_chance, get_event_wave_multiplier

from utils.logger import get_logger

logger = get_logger()


class TransitionEventsMixin:
    """Случайные события: safe / danger / mixed / surface."""

    # ==================== SAFE ====================

    def _trigger_safe_event(self, player: Player) -> str:
        safe_station_events = [
            {"chance": 12, "text": "🍄 Вы нашли грибы! +2 еды",
             "action": lambda p: p.food_inventory.extend(["съедобные_грибы", "съедобные_грибы"])},
            {"chance": 10, "text": "📦 Тайник сталкера! +1 аптечка АИ-2, +5 патронов",
             "action": lambda p: [
                 p.inventory.__setitem__('аптечка_аи2', p.inventory.get('аптечка_аи2', 0) + 1),
                 p.inventory.__setitem__('патроны', p.inventory.get('патроны', 0) + 5)
             ]},
            {"chance": 8, "text": "🫂 Вы встретили караван! +3 еды",
             "action": lambda p: p.food_inventory.extend(["мясо_крысы", "мясо_крысы", "мясо_крысы"])},
            {"chance": 10, "text": "💤 Вы отдохнули! +2 выносливости",
             "action": lambda p: p.restore_stamina(2.0)},
            {"chance": 5, "text": "💰 Вы нашли ценные вещи! +10 никелей",
             "action": lambda p: p.inventory.__setitem__('никели', p.inventory['никели'] + 10)},
            {"chance": 5, "text": "🔧 Вы нашли запчасти! +1 прочность маски",
             "action": lambda p: p.gas_mask.__setitem__('прочность', min(p.gas_mask['прочность'] + 1, p.get_gas_mask_max_durability()))},
            {"chance": 50, "text": "🌿 Путь был спокоен.", "action": lambda p: None}
        ]

        roll = random.randint(1, 100)
        cumulative = 0

        for event in safe_station_events:
            cumulative += event["chance"]
            if roll <= cumulative:
                event["action"](player)
                return event["text"]

        return "🌿 Путь был спокоен."

    # ==================== DANGER ====================

    def _trigger_danger_event(self, player: Player, interaction: discord.Interaction = None) -> str:
        spawn_chance = get_spawn_chance('danger_stations')

        if is_event_active('mutant_wave', self):
            spawn_chance = int(spawn_chance * get_event_wave_multiplier())

        danger_station_events = [
            {"chance": spawn_chance, "text": "💀 Мутант выпрыгнул из темноты!", "action": lambda p: None},
            {"chance": 12, "text": "☢️ Радиационная вспышка!",
             "action": lambda p: add_radiation(p, 5.0)},
            {"chance": 10, "text": "💥 Взрыв!",
             "action": lambda p: [self._apply_damage_to_body(p, 2.0), self._damage_mask(p)]},
            {"chance": 8, "text": "🕯️ Убежище! +1 выносливость",
             "action": lambda p: p.restore_stamina(1.0)},
            {"chance": 7, "text": "📦 Тайник с оружием! +10 патронов",
             "action": lambda p: p.inventory.__setitem__('патроны', p.inventory.get('патроны', 0) + 10)},
            {"chance": 5, "text": "💰 Труп сталкера! +15 никелей",
             "action": lambda p: p.inventory.__setitem__('никели', p.inventory['никели'] + 15)},
            {"chance": 8, "text": "🩸 Поранились! -0.5 жизни",
             "action": lambda p: self._apply_damage_to_body(p, 0.5)},
            {"chance": 5, "text": "🧪 Меднабор! +2 аптечки АИ-2",
             "action": lambda p: p.inventory.__setitem__('аптечка_аи2', p.inventory.get('аптечка_аи2', 0) + 2)},
            {"chance": 15, "text": "🌿 Путь был спокоен...", "action": lambda p: None}
        ]

        roll = random.randint(1, 100)
        cumulative = 0

        for event in danger_station_events:
            cumulative += event["chance"]
            if roll <= cumulative:
                if "Мутант выпрыгнул" in event["text"]:
                    combat_result = self._start_mutant_encounter(player, interaction)
                    if combat_result:
                        return f"💀 Мутант выпрыгнул из темноты!\n{combat_result}"
                    return "💀 Мутант выпрыгнул из темноты!\n⚔️ Бой начался!"

                res = event["action"](player)
                if not player.is_alive:
                    return f"{event['text']}\n💀 **{player.name}** погиб!"
                if isinstance(res, dict) and res.get('message'):
                    return f"{event['text']}\n{res['message']}"
                return event["text"]

        return "🌿 Путь был спокоен..."

    # ==================== MIXED ====================

    def _trigger_mixed_event(self, player: Player, interaction: discord.Interaction = None) -> str:
        mixed_transition_events = [
            {"chance": 8, "text": "📦 Рюкзак! +1 еда, +3 патрона",
             "action": lambda p: [p.food_inventory.append("мясо_крысы"),
                                  p.inventory.__setitem__('патроны', p.inventory.get('патроны', 0) + 3)]},
            {"chance": 6, "text": "🕯️ Свечи! +1 выносливость",
             "action": lambda p: p.restore_stamina(1.0)},
            {"chance": 5, "text": "💊 Таблетки! +1 жизнь",
             "action": lambda p: p.heal_all_body_parts(1.0)},
            {"chance": 4, "text": "📡 Сигнал! +10 опыта",
             "action": lambda p: p.add_xp(10)},
            {"chance": 3, "text": "💰 Монеты! +5 никелей",
             "action": lambda p: p.inventory.__setitem__('никели', p.inventory['никели'] + 5)},
            {"chance": 3, "text": "🍄 Редкие грибы! +3 еды",
             "action": lambda p: p.food_inventory.extend(["съедобные_грибы", "съедобные_грибы", "съедобные_грибы"])},
            {"chance": 10, "text": "🌫️ Туман.", "action": lambda p: None},
            {"chance": 8, "text": "🔊 Странные звуки.", "action": lambda p: None},
            {"chance": 7, "text": "💧 Капает вода. +1 выносливость",
             "action": lambda p: p.restore_stamina(1.0)},
            {"chance": 10, "text": "💀 Присутствие мутанта.", "action": lambda p: None},
            {"chance": 8, "text": "🕸️ Паутина! Замедление",
             "action": lambda p: p.add_debuff("замедление", 2)},
            {"chance": 7, "text": "⚡ Замыкание! -0.5 жизни",
             "action": lambda p: self._apply_damage_to_body(p, 0.5)},
            {"chance": 5, "text": "💨 Взрыв газа!",
             "action": lambda p: [self._apply_damage_to_body(p, 1.0),
                                  self._damage_mask(p),
                                  add_chemical(p, 5.0)]},
            {"chance": 4, "text": "🔒 Завал! -1 выносливость",
             "action": lambda p: p.use_stamina(1.0)},
            {"chance": 4, "text": "🧟 Обезумевший сталкер! Бой!", "action": lambda p: None},
            {"chance": 3, "text": "☢️ Радиоактивный источник!",
             "action": lambda p: add_radiation(p, 3.0)},
            {"chance": 3, "text": "🩸 Порезались! -0.5 жизни",
             "action": lambda p: [self._apply_damage_to_body(p, 0.5), p.add_debuff("кровотечение", 3)]},
            {"chance": 1, "text": "🌟 Артефакт! +20 опыта, +10 никелей",
             "action": lambda p: [p.add_xp(20),
                                  p.inventory.__setitem__('никели', p.inventory['никели'] + 10)]},
            {"chance": 1, "text": "💀 Стая крыс! -2 жизни",
             "action": lambda p: self._apply_damage_to_body(p, 2.0)},
        ]

        fall_chance = 30 - (player.skills.get("стойкость", 0) * BALANCE['skills'].get('toughness_fall_reduction', 10))
        if random.randint(1, 100) <= max(5, fall_chance):
            damage = random.choice([0.3, 0.5])
            self._apply_damage_to_body(player, damage)
            return f"💨 **{player.name}** поскользнулся! -{damage:.1f} жизни"

        roll = random.randint(1, 100)
        cumulative = 0

        for event in mixed_transition_events:
            cumulative += event["chance"]
            if roll <= cumulative:
                if "обезумевшего сталкера" in event["text"] or "сталкер" in event["text"].lower():
                    combat_result = self._start_mutant_encounter(player, interaction)
                    if combat_result:
                        return f"🧟 Встретили сталкера!\n{combat_result}"
                    return "🧟 Встретили сталкера!\n⚔️ Бой начался!"

                res = event["action"](player)
                if not player.is_alive:
                    return f"{event['text']}\n💀 **{player.name}** погиб!"
                if isinstance(res, list):
                    for item in res:
                        if isinstance(item, dict) and item.get('message'):
                            return f"{event['text']}\n{item['message']}"
                if isinstance(res, dict) and res.get('message'):
                    return f"{event['text']}\n{res['message']}"
                return event["text"]

        return "🌿 Переход прошел спокойно."

    # ==================== SURFACE (0.4.8.9) ====================

    async def _trigger_surface_event(self, player: Player,
                                     interaction: discord.Interaction = None) -> dict:
        """
        0.4.8.9: интерактивные ивенты поверхности.
        ЖДЁТ завершения ивента через asyncio.Future.

        Возвращает:
          {"combat_started": bool, "event_text": str}
        """
        if interaction is None:
            logger.warning(
                "[SURFACE] _trigger_surface_event без interaction — "
                "ивент не запускается"
            )
            return {"combat_started": False, "event_text": "🌫️ Белая мгла..."}

        try:
            from ..views.surface_events import (
                SurfaceEventView, pick_surface_event,
            )
        except Exception as e:
            logger.error(f"[SURFACE] import: {e}", exc_info=True)
            return {"combat_started": False, "event_text": "🌫️ Белая мгла..."}

        group_players = self._get_group_players_for_surface(player)
        event_id = pick_surface_event(player, group_players)

        try:
            view = SurfaceEventView(
                interaction=interaction,
                leader=player,
                group_players=group_players,
                event_id=event_id,
            )
            await view.start()
        except Exception as e:
            logger.error(f"[SURFACE] view start: {e}", exc_info=True)
            return {"combat_started": False, "event_text": ""}

        # 0.4.8.9: ЖДЁМ завершения ивента
        try:
            result = await asyncio.wait_for(view.result_future, timeout=300)
        except asyncio.TimeoutError:
            logger.warning("[SURFACE] ивент не завершён за 5 минут")
            return {"combat_started": False, "event_text": ""}

        return {
            "combat_started": result.get("combat_started", False),
            "event_text": "",
        }

    # ==================== ХЕЛПЕРЫ ====================

    def _get_group_players_for_surface(self, leader: Player) -> list:
        """
        Возвращает список всех живых игроков группы (включая лидера),
        если бригада в режиме «Вместе» и все на одной станции.
        Иначе — [leader].
        """
        try:
            from ..social.brigade_manager import brigade_manager
        except Exception:
            return [leader]

        brigade = brigade_manager.get_user_brigade(leader.user_id)
        if not brigade or not brigade.is_active():
            return [leader]

        if not brigade.is_leader(leader.user_id):
            return [leader]

        group = []
        for uid in brigade.get_member_ids():
            p = self.get_player(uid)
            if p and p.is_alive and p.location == leader.location \
                    and not getattr(p, 'is_sleeping', False):
                group.append(p)

        return group or [leader]