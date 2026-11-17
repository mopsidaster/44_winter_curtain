# -*- coding: utf-8 -*-
# func/combat/helpers.py - Общие функции боя (0.4.8.6)
#
# ИСТОРИЯ:
#   0.4.8   — кэш конфига
#   0.4.8.6 — жукопаук исключён с поверхности (SURFACE_ONLY_ENEMIES).

import random
from config.map_config import MUTANTS, BALANCE

MUTANTS_CONFIG = MUTANTS
MUTANTS_DATA = MUTANTS_CONFIG.get('mutants', {})
LOOT_ITEMS = MUTANTS_CONFIG.get('loot_items', {})
SPAWN_CONFIG = MUTANTS_CONFIG.get('spawn', {})

# Мутанты, которых нельзя спавнить через общий пул (только forced).
SURFACE_ONLY_ENEMIES = {
    "мерзляк_вождь",
    "мерзляк_охотник",
    "мерзляк",
    "страж",
    "демон",
    "жукопаук",  # 0.4.8.6
}


def get_mutant_data(mutant_id: str) -> dict:
    data = MUTANTS_DATA.get(mutant_id)
    return data if isinstance(data, dict) else {}


def _is_surface_only(mutant_id: str, data: dict) -> bool:
    return mutant_id in SURFACE_ONLY_ENEMIES


def get_random_mutant(danger_level: int = 1, exclude_boss: bool = True) -> tuple:
    available = []
    for mutant_id, data in MUTANTS_DATA.items():
        if not isinstance(data, dict) or not data.get('is_mutant', False):
            continue
        if exclude_boss and data.get('is_boss', False):
            continue
        if _is_surface_only(mutant_id, data):
            continue
        min_d, max_d = data.get('min_danger', 0), data.get('max_danger', 5)
        if min_d <= danger_level <= max_d:
            weight = data.get('spawn_weight', 1)
            if danger_level >= 4:
                weight *= 2
            available.extend([mutant_id] * weight)
    if not available:
        return "упырь", get_mutant_data("упырь")
    chosen = random.choice(available)
    return chosen, get_mutant_data(chosen)


def pick_enemy_type(danger_level: int, hostile_station: bool = False) -> str:
    return "human" if hostile_station else "mutant"


def get_random_enemy(danger_level: int, enemy_type: str = "mutant") -> tuple:
    available = []
    for enemy_id, data in MUTANTS_DATA.items():
        if not isinstance(data, dict) or data.get('is_boss', False) or _is_surface_only(enemy_id, data):
            continue
        if enemy_type == "mutant" and not data.get('is_mutant', False):
            continue
        if enemy_type == "human" and not data.get('is_human', False):
            continue
        min_d, max_d = data.get('min_danger', 0), data.get('max_danger', 5)
        if not (min_d <= danger_level <= max_d):
            continue
        weight = data.get('spawn_weight', 1)
        if danger_level >= 4 and data.get('is_mutant', False):
            weight *= 2
        available.extend([enemy_id] * weight)

    if not available:
        return ("бандит", get_mutant_data("бандит")) if enemy_type == "human" else ("упырь", get_mutant_data("упырь"))
    chosen = random.choice(available)
    return chosen, get_mutant_data(chosen)


def get_max_enemies(danger_level: int) -> int:
    return SPAWN_CONFIG.get('max_enemies_by_danger', {}).get(str(danger_level), 1)


def get_enemies_count(danger_level: int, enemy_id: str = None) -> int:
    if enemy_id:
        data = MUTANTS_DATA.get(enemy_id, {})
        if isinstance(data, dict) and data.get('always_count'):
            return int(data.get('always_count'))
    max_e = get_max_enemies(danger_level)
    if max_e <= 1:
        return 1
    return random.randint(2, max_e) if danger_level >= 4 else random.randint(1, max_e)


def get_spawn_chance(location_type: str) -> int:
    return SPAWN_CONFIG.get(f"{location_type}_chance", 10)


def get_event_wave_multiplier() -> float:
    return SPAWN_CONFIG.get('event_wave_multiplier', 1.5)