# -*- coding: utf-8 -*-
# func/spec_weapons/throwing_knives.py - Метательные ножи (Билд 0.4.4.5)
#
# Механика:
#   • Метание = полноценный ход.
#   • Один бросок по одной цели.
#   • Точность = weapon.accuracy × модификатор дистанции.
#   • Противоударная защита брони РАБОТАЕТ (урон считается как рукопашный).

import random
from config.map_config import WEAPONS, BALANCE


def get_knife_data(knife_id: str) -> dict:
    return WEAPONS.get(knife_id, {})


def is_throwing_knife(knife_id: str) -> bool:
    data = get_knife_data(knife_id)
    return data.get('type') == 'throwing_knife'


def calculate_throw_accuracy(knife_id: str, distance: str,
                             player_skill: int = 0) -> float:
    """
    Точность броска:
      base_accuracy × distance_modifier + bonus от навыка «меткость»
    Ограничение [0.05, 0.95].
    """
    knife = get_knife_data(knife_id)
    if not knife:
        return 0.0

    base = float(knife.get('accuracy', 0.5))
    skill_bonus = player_skill * (BALANCE.get('skills', {}).get('accuracy_per_level', 4) / 100.0)
    distance_mod = BALANCE.get('distance', {}).get(distance, {}).get('modifier', 1.0)

    acc = (base + skill_bonus) * distance_mod
    return max(0.05, min(acc, 0.95))


def throw_knife(player, knife_id: str, target, target_part: str,
                distance: str = "medium", player_skill: int = 0) -> dict:
    """
    Метание ножа.

    Args:
        player: объект Player
        knife_id: 'кустарный_метательный_нож' | 'боевой_метательный_нож'
        target: Combatant-цель
        target_part: 'голова' | 'торс' | 'руки' | 'ноги'
        distance: текущая дистанция
        player_skill: player.skills['меткость']

    Returns:
        {
          "success": bool,
          "hit": bool,
          "damage": float,
          "part": str,
          "accuracy": float,
          "message": str,
        }
    """
    result = {
        "success": False,
        "hit": False,
        "damage": 0.0,
        "part": target_part,
        "accuracy": 0.0,
        "message": "",
    }

    knife = get_knife_data(knife_id)
    if not knife or knife.get('type') != 'throwing_knife':
        result['message'] = "❌ Это не метательный нож!"
        return result

    if target is None or not getattr(target, 'is_alive', False):
        result['message'] = "❌ Нет живой цели!"
        return result

    name = knife.get('name', knife_id)
    emoji = knife.get('emoji', '🔪')
    base_damage = float(knife.get('damage', 0.0))

    accuracy = calculate_throw_accuracy(knife_id, distance, player_skill)
    result['accuracy'] = accuracy

    roll = random.uniform(0, 1)
    if roll > accuracy:
        result['success'] = True
        result['hit'] = False
        result['message'] = (
            f"❌ {emoji} **{name}** — промах! "
            f"(точность {accuracy * 100:.0f}%, дист. «{_dist_name(distance)}»)"
        )
        return result

    # Попадание — выбираем часть тела
    part = target_part
    try:
        if part not in target.body_parts or target.body_parts[part].get('hp', 0) <= 0:
            available = target.get_available_parts()
            if available:
                part = random.choice(available)
    except Exception:
        pass

    result['success'] = True
    result['hit'] = True
    result['part'] = part
    result['damage'] = base_damage
    result['message'] = (
        f"🎯 {emoji} **{name}** — попадание в **{part}** "
        f"({base_damage:.1f} урона, точность {accuracy * 100:.0f}%)"
    )
    return result


def _dist_name(distance: str) -> str:
    return {
        "close": "Близко",
        "medium": "Средняя",
        "far": "Далеко",
    }.get(distance, distance)