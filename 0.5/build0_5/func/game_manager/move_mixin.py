# -*- coding: utf-8 -*-
# func/game_manager/move_mixin.py - Перемещение игрока (0.4.8.7.4)
#
# ИСТОРИЯ:
#   0.4.8.3 — surface_lock
#   0.4.8.6 — Гутаги: пропуск → проход, нет → охранник
#   0.4.8.7 — _apply_destination_effects для каждого в группе
#   0.4.8.7.3 — ФИКС: can_enter_station пропускается для Гутагов
#   0.4.8.7.4 — ФИКС: elif is_gutagi: pass перед can_enter_station

import random
import discord

from config.map_config import BALANCE

from ..player import Player
from ..map_data import MAP_DATA
from ..station_utils import is_blocked_station, can_enter_station
from ..global_events import (
    get_stamina_multiplier, get_radiation_multiplier,
    can_move, is_event_active, get_gas_damage,
    is_celebration_station, is_workshop_station,
    is_frost_zone,
    is_chemical_zone, is_heating_zone,
)
from ..filter_system import get_current_filter_info, use_filter
from ..disease_system import (
    process_transition_effects, add_radiation, add_chemical,
    get_disease_stamina_penalty,
)
from ..cold_system import process_cold_on_transition
from ..armor_system import has_set_bonus
from ..combat.helpers import get_spawn_chance, get_event_wave_multiplier
from ..factions import can_enter_station_with_faction_full
from database.db import save_player

from utils.logger import get_logger

logger = get_logger()


class MoveMixin:

    async def move_player(self, user_id: int, destination: str,
                          interaction: discord.Interaction = None) -> str:
        from ..combat.manager import combat_manager
        from ..combat.pvp_manager import pvp_manager
        from ..social.brigade_manager import brigade_manager

        player = self.get_player(user_id)
        if not player:
            return "❌ Персонаж не найден!"
        if not player.is_alive:
            return "💀 Вы мертвы!"

        if getattr(player, 'is_sleeping', False):
            return "😴 Вы спите. Проснитесь через /menu."

        if combat_manager.get_combat(user_id) or pvp_manager.is_user_in_combat(user_id):
            return "⚔️ Вы в бою! Завершите бой перед перемещением."

        if not can_move(self):
            return "🌍 **Землетрясение!** Переходы временно заблокированы!"

        st = MAP_DATA["станции"].get(destination, {})
        is_surface = st.get("surface_lock", False) or st.get("type") == "на_поверхности"

        gutagi_stations = [
            "павелецкая_кольцо", "добрынинская", "октябрьская_кольцо",
            "серпуховская", "тульская",
        ]
        is_gutagi = destination in gutagi_stations

        # 0.4.8.7.4: Гутаги — пропускаем can_enter_station
        if is_surface and getattr(player, 'surface_unlocked', False):
            pass
        elif is_gutagi:
            pass
        else:
            ok, reason = can_enter_station(destination)
            if not ok:
                return reason

        # 0.4.8.7.4: Гутаги — проверка пропуска и вызов охранника
        hlam = player.inventory.get("хлам", []) or []
        has_perm_pass = "постоянный_пропуск" in hlam

        if is_gutagi:
            if has_perm_pass:
                ok2, reason2, warning = True, "OK", ""
            else:
                # 0.4.8.7.4: вызываем охранника
                from ..views.faction_npc.guard_dialog import start_guard_check
                if interaction:
                    await start_guard_check(interaction, player, destination)
                    return ""
                return "🚫 Требуется пропуск Гутагов."
        elif is_surface and getattr(player, 'surface_unlocked', False):
            ok2, reason2, warning = True, "OK", ""
        else:
            ok2, reason2, warning = can_enter_station_with_faction_full(
                player, destination
            )

        if not ok2:
            return reason2

        current = player.location
        if destination not in MAP_DATA["станции"][current]["connections"]:
            return f"❌ Нет прямого пути!"

        brigade = brigade_manager.get_user_brigade(user_id)
        if brigade and brigade.is_active():
            return await self._move_group(user_id, brigade, destination, interaction)

        return await self._move_single(player, destination, interaction)

    # ==================== ОДИНОЧНОЕ ====================

    async def _move_single(self, player: Player, destination: str,
                           interaction: discord.Interaction = None) -> str:
        user_id = player.user_id
        current = player.location

        disease_stamina_penalty = get_disease_stamina_penalty(player)
        stamina_mult = get_stamina_multiplier(self)
        stamina_cost = (
                BALANCE['player']['stamina_per_move'] * stamina_mult
                + disease_stamina_penalty
        )

        if player.stamina < stamina_cost:
            # 0.4.8.8: Нет выносливости — урон
            damage = 2.0
            body_parts = player.get_alive_body_parts()
            if not body_parts:
                return "💀 Вы погибли от истощения!"
            part = random.choice(body_parts)
            player.take_body_part_damage(part, damage)
            if not player.is_alive:
                return (
                    f"💀 **Вы погибли от истощения!**\n"
                    f"❌ Нужно {stamina_cost:.1f} выносливости."
                )
            return (
                f"⚠️ **Вы истощены!** -{damage:.0f} HP ({part}).\n"
                f"❌ Нужно {stamina_cost:.1f} выносливости, у вас {player.stamina:.1f}."
            )

        dest_data = MAP_DATA["станции"][destination]
        current_data = MAP_DATA["станции"][current]

        player.use_stamina(stamina_cost)

        from ..factions import can_enter_station_with_faction_full as _check
        _ok, _reason, _warning = _check(player, destination)
        result_text = (
            f"🚇 **{player.name}** идет от **{current_data['name']}** "
            f"к **{dest_data['name']}**...\n"
        )
        if _warning:
            result_text += f"\n{_warning}\n"
        if stamina_mult > 1.0:
            result_text += f"🌊 Переход стоит {stamina_cost:.1f} выносливости!\n"
        if disease_stamina_penalty > 0:
            result_text += (
                f"🤒 Болезнь: +{disease_stamina_penalty:.1f} "
                f"к затрате выносливости.\n"
            )

        if dest_data.get("type") == "на_поверхности":
            player._transition_to_surface = True
        try:
            event_text = await self._process_transition_events(
                player, current, destination, interaction
            )
        finally:
            if hasattr(player, '_transition_to_surface'):
                del player._transition_to_surface

        if event_text.startswith("⚔️") or "Бой начался" in event_text \
                or "**Бандиты!**" in event_text or "Мутант!" in event_text:
            return result_text + f"\n{event_text}"

        if not player.is_alive:
            return result_text + f"\n💀 **{player.name}** погиб!"

        player.location = destination
        player.update_effects()

        extra = await self._apply_destination_effects(
            player, current, destination
        )
        event_text += extra

        await save_player(player)

        return (
                result_text
                + f"\n{event_text}\n"
                + f"✅ **{player.name}** прибыл на **{dest_data['name']}**"
        )

    # ==================== ГРУППОВОЕ ====================

    async def _move_group(self, leader_id: int, brigade, destination: str,
                          interaction: discord.Interaction = None) -> str:
        current = None
        members = []
        for uid in brigade.get_member_ids():
            p = self.get_player(uid)
            if p and p.is_alive and not getattr(p, 'is_sleeping', False):
                members.append(p)
                if uid == leader_id:
                    current = p.location

        if not members:
            return "❌ В группе нет живых участников."

        if current is None:
            current = members[0].location

        if destination not in MAP_DATA["станции"][current]["connections"]:
            return f"❌ Нет прямого пути!"

        stamina_mult = get_stamina_multiplier(self)
        base_cost = BALANCE['player']['stamina_per_move'] * stamina_mult

        costs = {}
        for p in members:
            d = get_disease_stamina_penalty(p)
            cost = base_cost + d
            costs[p.user_id] = cost
            if p.stamina < cost:
                return (
                    f"❌ У **{p.name}** не хватает выносливости "
                    f"({p.stamina:.1f}/{cost:.1f}). Группа не идёт."
                )

        for p in members:
            p.use_stamina(costs[p.user_id])

        dest_data = MAP_DATA["станции"][destination]
        current_data = MAP_DATA["станции"][current]

        result_text = (
            f"🚇 **Бригада «{brigade.name}»** движется от "
            f"**{current_data['name']}** к **{dest_data['name']}**...\n"
        )

        leader = self.get_player(leader_id)

        if dest_data.get("type") == "на_поверхности":
            for p in members:
                p._transition_to_surface = True
        try:
            event_text = await self._process_transition_events(
                leader, current, destination, interaction
            )
        finally:
            for p in members:
                if hasattr(p, '_transition_to_surface'):
                    del p._transition_to_surface

        if event_text.startswith("⚔️") or "Бой начался" in event_text \
                or "**Бандиты!**" in event_text or "Мутант!" in event_text:
            return result_text + f"\n{event_text}"

        all_extras = []
        for p in members:
            p.location = destination
            p.update_effects()
            extra = await self._apply_destination_effects(p, current, destination)
            if extra:
                all_extras.append(extra)

        seen_keys = set()
        deduped_lines = []
        for extra in all_extras:
            if extra not in seen_keys:
                seen_keys.add(extra)
                deduped_lines.append(extra)

        extra_text = "".join(deduped_lines)

        for p in members:
            await save_player(p)

        return (
                result_text
                + f"\n{event_text}\n"
                + (f"{extra_text}\n" if extra_text else "")
                + f"✅ Бригада прибыла на **{dest_data['name']}** "
                  f"({len(members)} уч.)"
        )

    # ==================== СОБЫТИЯ ПЕРЕХОДА ====================

    async def _process_transition_events(self, player: Player, current: str,
                                         destination: str,
                                         interaction) -> str:
        current_data = MAP_DATA["станции"][current]
        dest_data = MAP_DATA["станции"][destination]

        current_dangerous = current_data.get("ruined", False) or current_data["danger"] >= 3
        dest_dangerous = dest_data.get("ruined", False) or dest_data["danger"] >= 3
        current_hostile = current_data.get("hostile", False)
        dest_hostile = dest_data.get("hostile", False)

        player_faction = getattr(player, 'faction', 'loners')
        if player_faction == "bandits":
            current_hostile = False
            dest_hostile = False

        any_hostile = current_hostile or dest_hostile

        enemy_spawn_bonus = 0
        if 'простуда' in player.diseases:
            enemy_spawn_bonus = int(
                BALANCE.get('cold_sickness', {}).get(
                    'enemy_spawn_bonus_percent', 10
                )
            )

        event_text = ""

        current_surface = current_data.get("type") == "на_поверхности"
        dest_surface = dest_data.get("type") == "на_поверхности"

        # ПОВЕРХНОСТЬ → ПОВЕРХНОСТЬ
        if current_surface and dest_surface and not any_hostile:
            surface_combat_chance = 60
            roll = random.randint(1, 100)

            if roll <= surface_combat_chance:
                combat_result = self._start_mutant_encounter(
                    player, interaction, hostile=False
                )
                if combat_result:
                    return f"🐺 **Стая Мерзляков!**\n{combat_result}"
                return "🐺 **Стая Мерзляков!**\n⚔️ Бой начался!"

            result = await self._trigger_surface_event(player, interaction)
            if result.get("combat_started"):
                return "⚔️ Бой начался!"
            return result.get("event_text", "") or ""

        # ПОВЕРХНОСТЬ ↔ МЕТРО
        if current_surface or dest_surface:
            if not current_dangerous and not dest_dangerous:
                safe_events = BALANCE['transition_events']['safe']
                event_roll = random.randint(1, 100)
                mutant_spawn_chance = (
                        get_spawn_chance('safe_stations') + enemy_spawn_bonus
                )
                if event_roll <= mutant_spawn_chance:
                    combat_result = self._start_mutant_encounter(
                        player, interaction, hostile=dest_hostile
                    )
                    if combat_result:
                        return f"💀 Мутант!\n{combat_result}"
                    return "💀 Мутант!\n⚔️ Бой начался!"

                if event_roll <= safe_events['mushrooms']['chance']:
                    event_text = "🍄 Грибы! +1 еда"
                    player.food_inventory.append("съедобные_грибы")
                elif event_roll <= (safe_events['mushrooms']['chance']
                                    + safe_events['cache']['chance']):
                    event_text = "📦 Тайник! +1 аптечка АИ-2"
                    player.inventory["аптечка_аи2"] = (
                            player.inventory.get("аптечка_аи2", 0) + 1
                    )
                elif event_roll <= (safe_events['mushrooms']['chance']
                                    + safe_events['cache']['chance']
                                    + safe_events['ammo']['chance']):
                    event_text = "🔫 Патроны! +3 патрона"
                    player.inventory["патроны"] = (
                            player.inventory.get("патроны", 0) + 3
                    )
                else:
                    event_text = self._trigger_safe_event(player)
            else:
                danger_events = BALANCE['transition_events']['danger']
                event_roll = random.randint(1, 100)
                mutant_spawn_chance = (
                        get_spawn_chance('ruined_stations') + enemy_spawn_bonus
                )
                if is_event_active('mutant_wave', self):
                    mutant_spawn_chance = int(
                        mutant_spawn_chance * get_event_wave_multiplier()
                    )
                if event_roll <= mutant_spawn_chance:
                    combat_result = self._start_mutant_encounter(
                        player, interaction, hostile=False
                    )
                    if combat_result:
                        return f"💀 Мутант!\n{combat_result}"
                    return "💀 Мутант!\n⚔️ Бой начался!"
                elif event_roll <= (mutant_spawn_chance
                                    + danger_events['explosion']['chance']):
                    event_text = "⚠️ Взрыв! -3 HP"
                    self._apply_damage_to_body(player, 3.0)
                    for _ in range(3):
                        self._damage_mask(player)
                else:
                    event_text = self._trigger_danger_event(
                        player, interaction
                    )

            return event_text

        # МЕТРО → МЕТРО
        if not current_dangerous and not dest_dangerous:
            safe_events = BALANCE['transition_events']['safe']
            event_roll = random.randint(1, 100)
            mutant_spawn_chance = (
                    get_spawn_chance('safe_stations') + enemy_spawn_bonus
            )
            if event_roll <= mutant_spawn_chance:
                combat_result = self._start_mutant_encounter(
                    player, interaction, hostile=dest_hostile
                )
                if combat_result:
                    return f"💀 Мутант!\n{combat_result}"
                return "💀 Мутант!\n⚔️ Бой начался!"

            if event_roll <= safe_events['mushrooms']['chance']:
                event_text = "🍄 Грибы! +1 еда"
                player.food_inventory.append("съедобные_грибы")
            elif event_roll <= (safe_events['mushrooms']['chance']
                                + safe_events['cache']['chance']):
                event_text = "📦 Тайник! +1 аптечка АИ-2"
                player.inventory["аптечка_аи2"] = (
                        player.inventory.get("аптечка_аи2", 0) + 1
                )
            elif event_roll <= (safe_events['mushrooms']['chance']
                                + safe_events['cache']['chance']
                                + safe_events['ammo']['chance']):
                event_text = "🔫 Патроны! +3 патрона"
                player.inventory["патроны"] = (
                        player.inventory.get("патроны", 0) + 3
                )
            else:
                event_text = self._trigger_safe_event(player)

        elif current_dangerous != dest_dangerous:
            event_roll = random.randint(1, 100)
            if any_hostile:
                bandit_chance = 45 + enemy_spawn_bonus
                if event_roll <= bandit_chance:
                    combat_result = self._start_mutant_encounter(
                        player, interaction, hostile=True
                    )
                    if combat_result:
                        return f"🏴‍☠️ **Бандиты!**\n{combat_result}"
                    return "🏴‍☠️ **Бандиты!**\n⚔️ Бой начался!"
                elif event_roll <= bandit_chance + 10:
                    combat_result = self._start_mutant_encounter(
                        player, interaction, hostile=False
                    )
                    if combat_result:
                        return f"💀 Мутант!\n{combat_result}"
                    return "💀 Мутант!\n⚔️ Бой начался!"
                else:
                    event_text = self._trigger_mixed_event(
                        player, interaction
                    )
            else:
                mutant_spawn_chance = (
                        get_spawn_chance('technical_tunnel') + enemy_spawn_bonus
                )
                if event_roll <= mutant_spawn_chance:
                    combat_result = self._start_mutant_encounter(
                        player, interaction, hostile=False
                    )
                    if combat_result:
                        return f"💀 Мутант!\n{combat_result}"
                    return "💀 Мутант!\n⚔️ Бой начался!"
                event_text = self._trigger_mixed_event(
                    player, interaction
                )

        else:
            danger_events = BALANCE['transition_events']['danger']
            event_roll = random.randint(1, 100)
            if any_hostile:
                bandit_chance = 55 + enemy_spawn_bonus
                if event_roll <= bandit_chance:
                    combat_result = self._start_mutant_encounter(
                        player, interaction, hostile=True
                    )
                    if combat_result:
                        return f"🏴‍☠️ **Бандиты!**\n{combat_result}"
                    return "🏴‍☠️ **Бандиты!**\n⚔️ Бой начался!"
                elif event_roll <= bandit_chance + 10:
                    combat_result = self._start_mutant_encounter(
                        player, interaction, hostile=False
                    )
                    if combat_result:
                        return f"💀 Мутант!\n{combat_result}"
                    return "💀 Мутант!\n⚔️ Бой начался!"
                else:
                    event_text = self._trigger_danger_event(
                        player, interaction
                    )
            else:
                mutant_spawn_chance = (
                        get_spawn_chance('ruined_stations') + enemy_spawn_bonus
                )
                if is_event_active('mutant_wave', self):
                    mutant_spawn_chance = int(
                        mutant_spawn_chance * get_event_wave_multiplier()
                    )
                if event_roll <= mutant_spawn_chance:
                    combat_result = self._start_mutant_encounter(
                        player, interaction, hostile=False
                    )
                    if combat_result:
                        return f"💀 Мутант!\n{combat_result}"
                    return "💀 Мутант!\n⚔️ Бой начался!"
                elif event_roll <= (mutant_spawn_chance
                                    + danger_events['explosion']['chance']):
                    event_text = "⚠️ Взрыв! -3 HP"
                    self._apply_damage_to_body(player, 3.0)
                    for _ in range(3):
                        self._damage_mask(player)
                else:
                    event_text = self._trigger_danger_event(
                        player, interaction
                    )

        return event_text

    async def _apply_destination_effects(self, player: Player, current: str,
                                         destination: str) -> str:
        dest_data = MAP_DATA["станции"][destination]
        extra = ""

        if is_celebration_station(destination, self):
            player.food_inventory.append("жареное_мясо_крысы")
            player.food_inventory.append("съедобные_грибы")
            extra += "\n🎉 **Праздник!** +3 еды!"

        if is_workshop_station(destination, self):
            player.gas_mask["состояние"] = "целый"
            player.gas_mask["прочность"] = player.get_gas_mask_max_durability()
            extra += "\n🔧 **Мастерская!** Противогаз восстановлен!"

        from ..global_events import get_breach_station
        breach_station = get_breach_station(self)
        if breach_station and breach_station == destination:
            self._apply_damage_to_body(player, 1.0)
            extra += "\n🧟 **Прорыв мутантов!** -1 жизнь!"

        surface_cfg = BALANCE.get('surface', {})
        danger_rad = surface_cfg.get('radiation_per_transition', 5.0)
        surface_no_mask_rad = surface_cfg.get(
            'radiation_per_transition_no_mask', 10.0
        )

        is_surface = dest_data.get("type") == "на_поверхности"
        is_danger = dest_data.get("ruined", False) or dest_data.get("danger", 0) >= 3

        if is_danger:
            current_filter = get_current_filter_info(player)
            has_protection = (
                    current_filter["has_filter"] and not current_filter["is_expired"]
            )

            if has_protection:
                result = use_filter(
                    player, BALANCE['gas_mask']['filter_cost_per_move']
                )
                if result.get("expired", False):
                    extra += "\n🧪 Фильтр израсходован!"
            else:
                if is_surface:
                    rad_amount = surface_no_mask_rad
                else:
                    rad_amount = danger_rad

                radiation_mult = get_radiation_multiplier(self)
                rad_amount *= radiation_mult

                if is_event_active('gas_leak', self):
                    rad_amount += get_gas_damage(self)

                rad_result = add_radiation(player, rad_amount)
                if rad_result.get('delta', 0) > 0:
                    extra += f"\n{rad_result.get('message', '')}"

        if is_event_active('gas_leak', self):
            gas_cfg = BALANCE.get('gas_leak', {})
            requires_set = gas_cfg.get('requires_full_rxbz_set', True)
            rxbz_protected = (
                has_set_bonus(player, 'chemical_immunity')
                if requires_set else False
            )
            if not rxbz_protected:
                gas_dmg = gas_cfg.get('damage_per_transition', 5.0)
                chem_result = add_chemical(player, gas_dmg)
                if chem_result.get('delta', 0) > 0:
                    extra += (
                        f"\n☠️ Утечка газа! {chem_result.get('message', '')}"
                    )
            else:
                extra += "\n✅ РХБЗ защищает от газа."

        if is_chemical_zone(destination, self) or is_chemical_zone(current, self):
            chem_cfg = BALANCE.get('chemical_cloud', {})
            chem_amount = chem_cfg.get('chemical_damage_per_transition', 25)
            rxbz_protected = has_set_bonus(player, 'chemical_immunity')
            if not rxbz_protected:
                chem_result = add_chemical(player, chem_amount)
                if chem_result.get('delta', 0) > 0:
                    extra += (
                        f"\n☣️ Химический выброс! "
                        f"{chem_result.get('message', '')}"
                    )
            else:
                extra += "\n✅ РХБЗ защищает от химии."

        if is_heating_zone(destination, self) or is_heating_zone(current, self):
            heat_cfg = BALANCE.get('heating_failure', {})
            cold_amount = heat_cfg.get('cold_damage_per_transition', 25)
            cold_result = process_cold_on_transition(
                player, to_station_in_frost_zone=True,
                custom_amount=cold_amount
            )
            if cold_result.get('cold_message'):
                extra += (
                    f"\n🥶 Отопление вышло из строя!\n"
                    f"{cold_result['cold_message']}"
                )

        surface_cfg = BALANCE.get('surface', {})
        cold_by_danger = surface_cfg.get('cold_by_danger', {})
        danger = dest_data.get("danger", 0)
        base_cold = cold_by_danger.get(str(danger), 0)

        if base_cold > 0:
            cold_result = process_cold_on_transition(
                player, to_station_in_frost_zone=True,
                custom_amount=base_cold
            )
            if cold_result.get('cold_message'):
                extra += (
                    f"\n❄️ Температура станции:\n"
                    f"{cold_result['cold_message']}"
                )

        in_frost_zone = is_frost_zone(destination, self)
        if in_frost_zone:
            cold_result = process_cold_on_transition(
                player, to_station_in_frost_zone=True
            )
            if cold_result.get('cold_message'):
                extra += f"\n❄️ Заморозки:\n{cold_result['cold_message']}"

        cold_sickness_msg = self._check_cold_sickness(player, current, destination)
        if cold_sickness_msg:
            extra += f"\n{cold_sickness_msg}"

        disease_result = process_transition_effects(
            player, current, destination, self
        )
        if disease_result.get('decay_message'):
            extra += f"\n{disease_result['decay_message']}"
        if disease_result.get('disease_message'):
            extra += f"\n{disease_result['disease_message']}"

        from ..cold_system import apply_frostbite_damage
        frost_dmg = apply_frostbite_damage(player)
        if frost_dmg.get('total_damage', 0) > 0:
            extra += f"\n{frost_dmg.get('message', '')}"
            if frost_dmg.get('killed'):
                player.is_alive = False

        return extra

    def _check_cold_sickness(self, player: Player, from_station: str,
                             to_station: str) -> str:
        from ..disease_system import get_immunity_reduction
        if 'простуда' in player.diseases:
            return ""
        cold_threshold = BALANCE.get('cold_sickness', {}).get(
            'cold_threshold', 25
        )
        delay = BALANCE.get('cold_sickness', {}).get('delay_transitions', 2)
        base_chance = BALANCE.get('cold_sickness', {}).get('base_chance', 35)
        if player.cold < cold_threshold:
            if player.cold_transition_counter > 0:
                player.cold_transition_counter = 0
            return ""
        player.cold_transition_counter += 1
        if player.cold_transition_counter < delay:
            return (
                f"❄️ Холод на пределе: ещё "
                f"{delay - player.cold_transition_counter} переход(а) "
                f"до простуды."
            )
        immunity = get_immunity_reduction(player)
        final_chance = base_chance * (1 - immunity)
        roll = random.uniform(0, 100)
        player.cold_transition_counter = 0
        if roll <= final_chance:
            player.diseases.append('простуда')
            player.cold_sickness_transitions = 0
            logger.info(f"{player.name}: заболел простудой")
            return (
                "🤧 **Вы простудились!**\n"
                "⚠️ Штраф к стамине, шансу врагов, рукопашной и меткости."
            )
        return "🤧 Вы почувствовали недомогание, но обошлось."