# -*- coding: utf-8 -*-
# func/spec_weapons/raider.py - Босс Рейдер и его носачи (0.4.7.6)
#
# ИСТОРИЯ:
#   0.4.4.2 — броня/шлем согласованной парой
#   0.4.5   — should_spawn_raider принимает gm и location
#   0.4.7.3 — 2 спутника Вождя
#   0.4.7.6 — СКС (semi-auto sniper) в списке вооружения Рейдера

import random
from config.map_config import BALANCE, WEAPONS

from utils.logger import get_logger

logger = get_logger()


# Заранее заданные полные комплекты (броня + шлем)
RAIDER_LOADOUTS = [
    {
        "armor": "броня_юг",
        "helmet": "шлем_юг",
    },
    {
        "armor": "кузнец_броня",
        "helmet": "кузнец_шлем",
    },
]


def get_raider_config() -> dict:
    return BALANCE.get('bosses', {}).get('raider', {})


def should_spawn_raider(game_manager=None, location: str = None) -> bool:
    """
    Бросок на спавн босса.

    0.4.5:
      • При активном raider_raid и станции игрока в списке — 100% спавн.
      • Иначе — обычный шанс spawn_chance_on_hostile (по умолчанию 5-15%).
    """
    if game_manager is not None and location is not None:
        try:
            from ..global_events import is_raider_raid_zone
            if is_raider_raid_zone(location, game_manager):
                if getattr(game_manager, 'raider_raid_killed', False):
                    return False
                logger.info(f"☠️ raider_raid активен на {location} — 100% спавн Рейдера")
                return True
        except Exception as e:
            logger.error(f"Ошибка проверки raider_raid: {e}")

    cfg = get_raider_config()
    chance = cfg.get('spawn_chance_on_hostile', 5)
    return random.randint(1, 100) <= chance


def get_raider_weapon_setup() -> dict:
    """
    Выбрать случайный вариант оружия Рейдера.

    0.4.7.6: добавлен вариант с СКС (semi-auto sniper) на трассерах.
    """
    cfg = get_raider_config()
    choices = cfg.get('weapons_choices', [])

    if not choices:
        return {
            "weapon": "вск_94",
            "ammo_type": "бронебойные",
            "modules": {"scope": "оптический_х2"},
            "magazine": None,
        }

    chosen = dict(random.choice(choices))

    # СКС — уточняем магазин, если его не указали явно
    if chosen.get("weapon") == "скс" and not chosen.get("magazine"):
        chosen["magazine"] = "магазин_скс_20"

    return chosen


def get_raider_armor_setup() -> dict:
    """Выбрать СЛУЧАЙНЫЙ ПОЛНЫЙ комплект (броня + шлем)."""
    cfg = get_raider_config()
    armor_choices = cfg.get('armor_choices', [])
    helmet_choices = cfg.get('helmet_choices', [])

    pairs_from_config = cfg.get('loadouts')
    if isinstance(pairs_from_config, list) and pairs_from_config:
        valid = [
            p for p in pairs_from_config
            if isinstance(p, dict) and p.get('armor') and p.get('helmet')
        ]
        if valid:
            chosen = random.choice(valid)
            return {"armor": chosen["armor"], "helmet": chosen["helmet"]}

    if armor_choices and helmet_choices:
        armor = random.choice(armor_choices)

        armor_lower = str(armor).lower()
        matched_helmet = None

        keyword_map = {
            "юг": "юг",
            "кузнец": "кузнец",
            "спарта": "спарта",
            "ганза": "ганза",
            "рхбз": "рхбз",
        }
        for key, helmet_key in keyword_map.items():
            if key in armor_lower:
                for h in helmet_choices:
                    if helmet_key in str(h).lower():
                        matched_helmet = h
                        break
                break

        if matched_helmet:
            return {"armor": armor, "helmet": matched_helmet}

        for loadout in RAIDER_LOADOUTS:
            if loadout["armor"] == armor:
                return dict(loadout)

    return dict(random.choice(RAIDER_LOADOUTS))


def get_raider_body_parts() -> dict:
    """Части тела Рейдера из конфига."""
    cfg = get_raider_config()
    parts = cfg.get('body_parts', {})
    result = {}
    for part_id, part_data in parts.items():
        result[part_id] = {
            "hp": part_data.get('hp', 10),
            "max_hp": part_data.get('hp', 10),
            "multiplier": part_data.get('multiplier', 1.0),
        }
    return result


def get_raider_hit_chance(danger_level: int) -> int:
    cfg = get_raider_config()
    base = cfg.get('hit_chance_base', 70)
    per = cfg.get('hit_chance_per_danger', 3)
    return min(base + per * danger_level, 95)


def get_raider_damage(danger_level: int) -> float:
    cfg = get_raider_config()
    dmg_min = cfg.get('damage_min', 3.5)
    dmg_max = cfg.get('damage_max', 5.5)
    return random.uniform(dmg_min, dmg_max)


def get_companion_ids() -> list:
    cfg = get_raider_config()
    return cfg.get('companions', ["носач_рафик", "носач_жуля"])