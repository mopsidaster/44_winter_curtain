# -*- coding: utf-8 -*-
# func/weapon_system/misc.py - Прочие хелперы (0.4.7.6)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено
#   0.4.7.2 — без изменений
#   0.4.7.6 — get_shots_per_action не меняется: sniper = 1.
#             Второй выстрел semi-auto — через subtype-логику в combat.py

import random

from config.map_config import BALANCE

from .weapons import get_weapon_type
from .ammo import get_caliber_ammo_types

from utils.logger import get_logger

logger = get_logger()


def get_shots_per_action(weapon_id: str) -> int:
    """Сколько выстрелов делает оружие за одно действие."""
    weapon_type = get_weapon_type(weapon_id)
    if weapon_type == "mg":
        return 3
    if weapon_type == "smg":
        return 4
    if weapon_type == "sniper":
        return 1
    if weapon_type == "assault":
        return 2
    if weapon_type in ["spec_w", "grenade_launcher"]:
        return 1
    if weapon_type == "shotgun":
        return 1
    return 1


def get_ammo_cost_per_action(weapon_id: str) -> int:
    return get_shots_per_action(weapon_id)


def get_random_ammo_type(caliber: str) -> str:
    types = get_caliber_ammo_types(caliber)
    if not types:
        return "оболочечные"
    return random.choice(types)


def get_headshot_accuracy(player_skill: int = 0) -> int:
    base = BALANCE['skills']['headshot_accuracy_base']
    per_level = BALANCE['skills'].get('accuracy_headshot_percent', 3)
    return min(base + (player_skill * per_level), 70)