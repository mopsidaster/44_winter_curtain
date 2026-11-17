# -*- coding: utf-8 -*-
# func/spec_weapons/grenade_launcher.py - Логика ГП-25 (Билд 0.4.3)
#
# Режимы стрельбы:
#   • Прицельный (single) — только на средней или дальней дистанции.
#     На близкой — нельзя (заденет себя).
#     Точность динамическая: база от BALANCE.spec_weapons.гп_25
#     + бонус от навыка Меткость + множитель дистанции.
#     Урон масштабируется от точности.
#   • По группе (group) — точность не влияет.
#     Урон 10 делится на всех врагов.
#     У каждого врага — 35% шанс укрыться (не получить урон).

import random
from config.map_config import BALANCE, WEAPONS, AMMO


def get_gp25_config() -> dict:
    """Получить конфиг ГП-25."""
    return BALANCE.get('spec_weapons', {}).get('гп_25', {})


def get_weapon_data(weapon_id: str = "гп_25") -> dict:
    """Данные оружия из weapons.json."""
    return WEAPONS.get(weapon_id, {})


def get_ammo_data(ammo_id: str = "оф_граната") -> dict:
    """Данные боеприпаса из ammo.json."""
    return AMMO.get('ammo_types', {}).get(ammo_id, {})


def can_fire_grenade_launcher(distance: str) -> tuple:
    """
    Можно ли выстрелить из ГП-25 на данной дистанции в прицельном режиме.

    Returns:
        (can_fire: bool, reason: str)
    """
    if distance == "close":
        return False, "❌ На близкой дистанции граната заденет вас самих! Используйте «По группе» или смените дистанцию."
    return True, ""


def calculate_single_accuracy(distance: str, player_skill: int = 0) -> float:
    """
    Динамическая точность для прицельного выстрела.

    На близкой: 0 (нельзя стрелять, обрабатывается выше).
    На средней: от medium_accuracy_min до medium_accuracy_max + скилл + модификатор.
    На дальней: от far_accuracy_min до far_accuracy_max + скилл + модификатор.

    Returns:
        float — точность от 0.0 до 1.0
    """
    cfg = get_gp25_config()
    if not cfg:
        return 0.5

    if distance == "close":
        return 0.0

    if distance == "medium":
        base_min = cfg.get('medium_accuracy_min', 25) / 100.0
        base_max = cfg.get('medium_accuracy_max', 50) / 100.0
    elif distance == "far":
        base_min = cfg.get('far_accuracy_min', 50) / 100.0
        base_max = cfg.get('far_accuracy_max', 75) / 100.0
    else:
        return 0.5

    # Случайная база в диапазоне
    base = random.uniform(base_min, base_max)

    # Бонус от навыка Меткость
    accuracy_per_level = BALANCE.get('skills', {}).get('accuracy_per_level', 4) / 100.0
    skill_bonus = player_skill * accuracy_per_level

    # Модификатор дистанции
    distance_data = BALANCE.get('distance', {}).get(distance, {})
    distance_mod = distance_data.get('modifier', 1.0)

    final = (base + skill_bonus) * distance_mod

    return min(final, 0.95)


def fire_single_target(distance: str, player_skill: int = 0) -> dict:
    """
    Прицельный выстрел по одной цели.

    Returns:
        {
            "success": bool,
            "accuracy": float,
            "damage": float,
            "message": str,
        }
    """
    can_fire, reason = can_fire_grenade_launcher(distance)
    if not can_fire:
        return {
            "success": False,
            "accuracy": 0.0,
            "damage": 0.0,
            "message": reason,
        }

    cfg = get_gp25_config()
    base_damage = cfg.get('base_damage', 10.0)

    accuracy = calculate_single_accuracy(distance, player_skill)

    # Урон масштабируется от точности
    final_damage = base_damage * accuracy

    return {
        "success": True,
        "accuracy": accuracy,
        "damage": final_damage,
        "message": (
            f"💥 **ГП-25 (прицельный)** — точность **{accuracy * 100:.0f}%**\n"
            f"💣 Нанесено **{final_damage:.1f}** урона"
        ),
    }


def fire_group_target(enemies_count: int) -> dict:
    """
    Выстрел по группе врагов.

    Урон делится на всех. У каждого — шанс укрыться.

    Args:
        enemies_count: количество живых врагов в бою

    Returns:
        {
            "success": bool,
            "hits": list[dict],   # [{enemy_index, damage, covered}]
            "total_damage": float,
            "message": str,
        }
    """
    if enemies_count <= 0:
        return {
            "success": False,
            "hits": [],
            "total_damage": 0.0,
            "message": "❌ Нет врагов для выстрела.",
        }

    cfg = get_gp25_config()
    base_damage = cfg.get('base_damage', 10.0)
    cover_chance = cfg.get('group_cover_chance', 35)

    damage_per_enemy = base_damage / enemies_count

    hits = []
    total_damage = 0.0
    hit_lines = []

    for idx in range(enemies_count):
        covered = random.randint(1, 100) <= cover_chance
        if covered:
            hits.append({"enemy_index": idx, "damage": 0.0, "covered": True})
            hit_lines.append(f"   • Враг #{idx + 1}: укрылся")
        else:
            hits.append({"enemy_index": idx, "damage": damage_per_enemy, "covered": False})
            total_damage += damage_per_enemy
            hit_lines.append(f"   • Враг #{idx + 1}: {damage_per_enemy:.1f} урона")

    message = (
            f"💥 **ГП-25 (по группе)** — урон делится на **{enemies_count}** врагов\n"
            f"💣 Урон от гранаты: **{base_damage:.1f}** (по {damage_per_enemy:.1f} на каждого)\n"
            f"🎯 Шанс укрытия: {cover_chance}%\n"
            + "\n".join(hit_lines) +
            f"\n\n💥 **Итого нанесено:** {total_damage:.1f}"
    )

    return {
        "success": True,
        "hits": hits,
        "total_damage": total_damage,
        "message": message,
    }


def get_grenade_launcher_info() -> dict:
    """Информация о ГП-25 для отображения в UI."""
    cfg = get_gp25_config()
    weapon = get_weapon_data()
    ammo = get_ammo_data()

    return {
        "name": weapon.get('name', 'ГП-25'),
        "emoji": weapon.get('emoji', '💥'),
        "damage": cfg.get('base_damage', 10.0),
        "ammo_name": ammo.get('name', 'ОФ Граната'),
        "ammo_emoji": ammo.get('emoji', '💣'),
        "close_block": cfg.get('close_block', True),
        "medium_range": f"{cfg.get('medium_accuracy_min', 25)}–{cfg.get('medium_accuracy_max', 50)}%",
        "far_range": f"{cfg.get('far_accuracy_min', 50)}–{cfg.get('far_accuracy_max', 75)}%",
        "group_cover_chance": cfg.get('group_cover_chance', 35),
    }