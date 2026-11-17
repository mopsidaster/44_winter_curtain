# -*- coding: utf-8 -*-
# func/technical_tunnels.py - Технические тоннели (0.4.8.7.3)
#
# ИСТОРИЯ:
#   0.4.3.1 — заражение в тоннеле идёт в player.radiation (1:1)
#   0.4.7.5 — tunnel_status для всех тоннелей
#   0.4.8.7.3 — ФИКС: player.lives → take_body_part_damage

import random
import asyncio
from typing import Dict, Optional
from config.map_config import BALANCE
from utils.logger import get_logger
from .global_events import get_stamina_multiplier, get_radiation_multiplier, is_event_active
from .filter_system import get_current_filter_info, use_filter
from .disease_system import add_radiation, ensure_disease_fields

logger = get_logger()


tunnel_status: Dict[str, dict] = {}


def _ensure_tunnel_status(tunnel_id: str) -> bool:
    from .map_data import MAP_DATA

    if tunnel_id not in MAP_DATA.get("technical_tunnels", {}):
        return False

    if tunnel_id not in tunnel_status:
        tunnel_status[tunnel_id] = {
            "contaminated": False,
            "last_check": 0,
            "move_counter": 0,
            "next_change": None,
            "initialized": False,
        }

    return True


TUNNEL_CONFIG = {
    "безопасные": {
        "initial": "clean",
        "change_after": 15,
        "change_back_after": 5,
        "description": "Безопасные станции вокруг"
    },
    "mixed": {
        "initial": "random",
        "change_after": [5, 10, 15, 30],
        "change_back_after": None,
        "description": "Смешанные станции вокруг"
    },
    "опасные": {
        "initial": "contaminated",
        "change_after": None,
        "change_back_after": None,
        "description": "Опасные станции вокруг"
    }
}


def get_station_type(station_id: str) -> str:
    from .map_data import MAP_DATA
    if station_id not in MAP_DATA["станции"]:
        return "обычная"
    station = MAP_DATA["станции"][station_id]
    is_dangerous = station.get("ruined", False) or station.get("danger", 0) >= 3
    return "опасная" if is_dangerous else "безопасная"


def get_tunnel_zone_type(tunnel_id: str) -> str:
    from .map_data import MAP_DATA
    if tunnel_id not in MAP_DATA.get("technical_tunnels", {}):
        return "mixed"

    tunnel = MAP_DATA["technical_tunnels"][tunnel_id]
    stations = tunnel.get("connections", [])

    if not stations:
        return "mixed"

    danger_count = 0
    safe_count = 0

    for station_id in stations:
        if station_id not in MAP_DATA["станции"]:
            continue
        station = MAP_DATA["станции"][station_id]
        is_dangerous = station.get("ruined", False) or station.get("danger", 0) >= 3
        if is_dangerous:
            danger_count += 1
        else:
            safe_count += 1

    if danger_count > 0 and safe_count == 0:
        return "опасные"
    elif danger_count > 0 and safe_count > 0:
        return "mixed"
    else:
        return "безопасные"


def init_tunnel(tunnel_id: str):
    if not _ensure_tunnel_status(tunnel_id):
        return
    if tunnel_status[tunnel_id]["initialized"]:
        return

    zone_type = get_tunnel_zone_type(tunnel_id)
    config = TUNNEL_CONFIG.get(zone_type, TUNNEL_CONFIG["mixed"])

    if config["initial"] == "clean":
        contaminated = False
    elif config["initial"] == "contaminated":
        contaminated = True
    else:
        contaminated = random.choice([True, False])

    tunnel_status[tunnel_id]["contaminated"] = contaminated
    tunnel_status[tunnel_id]["move_counter"] = 0
    tunnel_status[tunnel_id]["initialized"] = True
    tunnel_status[tunnel_id]["zone_type"] = zone_type


def check_tunnel_contamination(tunnel_id: str, stations_status: dict) -> bool:
    if not _ensure_tunnel_status(tunnel_id):
        return False
    if not tunnel_status[tunnel_id]["initialized"]:
        init_tunnel(tunnel_id)

    zone_type = tunnel_status[tunnel_id].get("zone_type", "mixed")

    if zone_type == "опасные":
        tunnel_status[tunnel_id]["contaminated"] = True
        return True

    tunnel_status[tunnel_id]["move_counter"] += 1
    moves = tunnel_status[tunnel_id]["move_counter"]
    current_state = tunnel_status[tunnel_id]["contaminated"]

    if zone_type == "безопасные":
        if current_state:
            if moves >= 5:
                tunnel_status[tunnel_id]["contaminated"] = False
                tunnel_status[tunnel_id]["move_counter"] = 0
        else:
            if moves >= 15:
                tunnel_status[tunnel_id]["contaminated"] = True
                tunnel_status[tunnel_id]["move_counter"] = 0
    elif zone_type == "mixed":
        change_thresholds = [5, 10, 15, 30]
        if moves in change_thresholds:
            tunnel_status[tunnel_id]["contaminated"] = random.choice([True, False])
            tunnel_status[tunnel_id]["move_counter"] = 0

    return tunnel_status[tunnel_id]["contaminated"]


def get_tunnel_info(tunnel_id: str) -> dict:
    if not _ensure_tunnel_status(tunnel_id):
        return {"exists": False}
    if not tunnel_status[tunnel_id]["initialized"]:
        init_tunnel(tunnel_id)

    return {
        "exists": True,
        "contaminated": tunnel_status[tunnel_id]["contaminated"],
        "last_check": tunnel_status[tunnel_id]["last_check"],
        "move_counter": tunnel_status[tunnel_id]["move_counter"],
        "zone_type": tunnel_status[tunnel_id].get("zone_type", "mixed")
    }


def check_tunnel(tunnel_id: str) -> dict:
    if not _ensure_tunnel_status(tunnel_id):
        return {"exists": False}
    if not tunnel_status[tunnel_id]["initialized"]:
        init_tunnel(tunnel_id)

    return {
        "exists": True,
        "contaminated": tunnel_status[tunnel_id].get("contaminated", False),
        "move_counter": tunnel_status[tunnel_id].get("move_counter", 0),
        "zone_type": tunnel_status[tunnel_id].get("zone_type", "mixed")
    }


async def enter_technical_tunnel(player, tunnel_id: str, destination: str,
                                 game_manager, interaction=None) -> str:
    from .map_data import MAP_DATA
    from .combat import combat_manager
    from .social.brigade_manager import brigade_manager

    brigade = brigade_manager.get_user_brigade(player.user_id)
    if brigade and brigade.is_active() and brigade.is_leader(player.user_id):
        members = []
        for uid in brigade.get_member_ids():
            m = game_manager.get_player(uid)
            if m and m.is_alive:
                members.append(m)

        if len(members) > 1:
            return await _enter_tunnel_group(
                player, members, tunnel_id, destination, game_manager, interaction
            )

    if tunnel_id not in MAP_DATA.get("technical_tunnels", {}):
        return "❌ Технический тоннель не найден!"

    tunnel_data = MAP_DATA["technical_tunnels"][tunnel_id]

    if destination not in tunnel_data["connections"]:
        return "❌ Нет выхода на эту станцию!"

    if destination == player.location:
        return "❌ Нельзя перейти в тоннель на ту же станцию!"

    is_contaminated = check_tunnel_contamination(tunnel_id, {})

    result_text = f"🚇 **{player.name}** входит в технический тоннель **{tunnel_data['name']}**...\n"

    if is_contaminated:
        result_text += "☢️ **ВНИМАНИЕ!** Тоннель загрязнён радиацией!\n"

        current_filter = get_current_filter_info(player)
        has_protection = current_filter["has_filter"] and not current_filter["is_expired"]

        if has_protection:
            result = use_filter(player, 1.0)
            if result.get("expired", False):
                result_text += "🧪 Фильтр в противогазе полностью израсходован!\n"
            else:
                result_text += "✅ Противогаз защищает от радиации.\n"
        else:
            base_rad = BALANCE['gas_mask']['radiation_damage'] * 2
            radiation_mult = get_radiation_multiplier(game_manager)
            rad_amount = base_rad * radiation_mult

            if is_event_active('gas_leak', game_manager):
                from .global_events import get_gas_damage
                rad_amount += get_gas_damage(game_manager)

            ensure_disease_fields(player)
            rad_result = add_radiation(player, rad_amount)

            result_text += f"☢️ {rad_result.get('message', '')}\n"

            if rad_result.get('disease_triggered'):
                result_text += "💀 **Вы заболели лучевой болезнью!**\n"
    else:
        result_text += "✅ Тоннель чист. Можно проходить без противогаза.\n"

    event_roll = random.randint(1, 100)
    if event_roll <= 35:
        encounter_result = _tunnel_encounter(player)

        if encounter_result.get("is_combat"):
            combat_started = game_manager._start_mutant_encounter(player, interaction)
            if combat_started:
                return result_text + encounter_result["text"] + f"\n{combat_started}"
            else:
                return result_text + encounter_result["text"] + "\n⚔️ Бой начался!"
        else:
            result_text += encounter_result["text"]
            if not player.is_alive:
                return result_text

    stamina_mult = get_stamina_multiplier(game_manager)
    stamina_cost = BALANCE['player']['stamina_per_move'] * 1.5 * stamina_mult
    player.use_stamina(stamina_cost)
    result_text += f"\n🏃 Затрачено выносливости: {stamina_cost:.1f}"

    player.location = destination
    player.update_effects()

    dest_data = MAP_DATA["станции"][destination]
    result_text += f"\n✅ **{player.name}** вышел из тоннеля на станцию **{dest_data['name']}**!"

    return result_text


def _tunnel_encounter(player) -> dict:
    """0.4.8.7.3: ФИКС — урон через take_body_part_damage, не lives."""
    events = [
        {
            "chance": 25,
            "text": "🐀 На вас напала стая крыс! -1 жизнь",
            "is_combat": False,
            "action": lambda p: p.take_body_part_damage(
                random.choice(p.get_alive_body_parts() or ["торс"]), 1.0
            )
        },
        {
            "chance": 20,
            "text": "💀 Вы встретили мутанта! Бой!",
            "is_combat": True,
            "action": lambda p: None
        },
        {
            "chance": 15,
            "text": "📦 Вы нашли тайник с припасами! +1 аптечка, +3 патрона",
            "is_combat": False,
            "action": lambda p: [
                p.inventory.__setitem__('аптечка_аи2', p.inventory.get('аптечка_аи2', 0) + 1),
                p.inventory.__setitem__('патроны', p.inventory.get('патроны', 0) + 3)
            ]
        },
        {
            "chance": 15,
            "text": "💡 Вы нашли старый фонарь!",
            "is_combat": False,
            "action": lambda p: None
        },
        {
            "chance": 15,
            "text": "⚡ Обвал! -1.5 жизни",
            "is_combat": False,
            "action": lambda p: p.take_body_part_damage(
                random.choice(p.get_alive_body_parts() or ["торс"]), 1.5
            )
        },
        {
            "chance": 10,
            "text": "💀 Вы услышали странный звук... Но никто не появился.",
            "is_combat": False,
            "action": lambda p: None
        }
    ]

    roll = random.randint(1, 100)
    cumulative = 0

    for event in events:
        cumulative += event["chance"]
        if roll <= cumulative:
            if event["is_combat"]:
                return {"text": event["text"], "is_combat": True}

            event["action"](player)
            if not player.is_alive:
                return {
                    "text": event["text"] + f"\n💀 **{player.name}** погиб!",
                    "is_combat": False,
                }
            return {"text": event["text"], "is_combat": False}

    return {"text": "🌿 Тоннель пуст.", "is_combat": False}


async def _enter_tunnel_group(leader, members, tunnel_id: str, destination: str,
                              game_manager, interaction=None) -> str:
    from .map_data import MAP_DATA
    from .filter_system import get_current_filter_info, use_filter
    from .disease_system import add_radiation, ensure_disease_fields
    from database.db import save_player
    from config.map_config import BALANCE

    tunnel_data = MAP_DATA["technical_tunnels"].get(tunnel_id, {})
    if not tunnel_data:
        return "❌ Тоннель не найден."

    if destination == leader.location:
        return "❌ Нельзя перейти в тоннель на ту же станцию!"

    is_contaminated = check_tunnel_contamination(tunnel_id, {})

    result_text = f"🚇 **Бригада «{leader.name}»** входит в тоннель...\n"

    if is_contaminated:
        result_text += "☢️ **ВНИМАНИЕ!** Тоннель загрязнён радиацией!\n"
    else:
        result_text += "✅ Тоннель чист.\n"

    for p in members:
        if is_contaminated:
            current_filter = get_current_filter_info(p)
            has_protection = current_filter["has_filter"] and not current_filter["is_expired"]
            if has_protection:
                result = use_filter(p, 1.0)
                if result.get("expired"):
                    result_text += f"🧪 У **{p.name}** фильтр израсходован.\n"
            else:
                base_rad = BALANCE['gas_mask']['radiation_damage'] * 2
                ensure_disease_fields(p)
                rad_result = add_radiation(p, base_rad)
                result_text += f"☢️ **{p.name}**: {rad_result.get('message', '')}\n"

        stamina_cost = BALANCE['player']['stamina_per_move'] * 1.5
        p.use_stamina(stamina_cost)

        p.location = destination
        p.update_effects()
        await save_player(p)

    dest_data = MAP_DATA["станции"][destination]
    result_text += f"\n✅ Бригада прибыла на **{dest_data['name']}** ({len(members)} чел.)"

    event_roll = random.randint(1, 100)
    if event_roll <= 35:
        encounter_result = _tunnel_encounter(leader)
        if encounter_result.get("is_combat"):
            combat_started = game_manager._start_mutant_encounter(leader, interaction)
            if combat_started:
                return result_text + encounter_result["text"] + f"\n{combat_started}"
        else:
            result_text += encounter_result["text"]

    return result_text