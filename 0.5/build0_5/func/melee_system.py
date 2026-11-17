# -*- coding: utf-8 -*-
# func/melee_system.py - Система оружия ближнего боя (0.4.7.6.2)
#
# ИСТОРИЯ:
#   0.4.1   — базовая система
#   0.4.5   — can_cause_bleeding, get_melee_bleeding_chances
#   0.4.7.6.2 — защита от не-dict значений в melee_weapons

from config.map_config import MELEE
from utils.logger import get_logger

logger = get_logger()


def _get_melee_dict() -> dict:
    """
    Безопасно достаёт MELEE['melee_weapons'] и возвращает dict.
    Если данные повреждены — возвращает пустой dict с логом.
    """
    raw = MELEE.get('melee_weapons', {})
    if not isinstance(raw, dict):
        logger.error(
            f"[MELEE] melee_weapons имеет тип {type(raw).__name__}, "
            f"ожидался dict. Первые элементы: {str(raw)[:100]}"
        )
        return {}
    return raw


def get_melee_weapon(weapon_id: str) -> dict:
    if not weapon_id or not isinstance(weapon_id, str):
        return {}
    raw = _get_melee_dict()
    data = raw.get(weapon_id)
    if not isinstance(data, dict):
        return {}
    return data


def get_melee_weapon_name(weapon_id: str) -> str:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return weapon_id
    return weapon.get('name', weapon_id)


def get_melee_weapon_emoji(weapon_id: str) -> str:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return "👊"
    return weapon.get('emoji', '👊')


def get_melee_weapon_damage(weapon_id: str) -> float:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return 1.0
    return weapon.get('damage', 1.0)


def get_melee_weapon_type(weapon_id: str) -> str:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return "тупое"
    return weapon.get('type', 'тупое')


def get_melee_weapon_stun_chance(weapon_id: str) -> int:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return 0
    return weapon.get('stun_chance', 0)


def get_melee_weapon_accuracy(weapon_id: str) -> int:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return 70
    return weapon.get('accuracy', 70)


def get_melee_weapon_price(weapon_id: str) -> int:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return 0
    return weapon.get('price', 0)


def get_melee_weapon_max_durability(weapon_id: str) -> int:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return 999
    return weapon.get('max_durability', 999)


def get_melee_weapon_skill_multiplier(weapon_id: str) -> float:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return 1.0
    return weapon.get('skill_multiplier', 1.0)


def is_melee_weapon_indestructible(weapon_id: str) -> bool:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return True
    return weapon.get('indestructible', False)


def get_all_melee_weapons() -> list:
    return list(_get_melee_dict().keys())


def get_available_melee_weapons() -> list:
    """Оружие с ценой > 0 (продаётся в магазине)."""
    result = []
    for weapon_id, weapon_data in _get_melee_dict().items():
        if not isinstance(weapon_data, dict):
            logger.warning(
                f"[MELEE] пропущено '{weapon_id}' — не dict: "
                f"{type(weapon_data).__name__}"
            )
            continue
        try:
            price = weapon_data.get('price', 0)
            if isinstance(price, (int, float)) and price > 0:
                result.append(weapon_id)
        except Exception as e:
            logger.error(f"[MELEE] '{weapon_id}': ошибка чтения price — {e}")
    return result


def format_melee_weapon_info(weapon_id: str) -> str:
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return "❌ Оружие не найдено"

    result = f"**{weapon.get('emoji', '👊')} {weapon.get('name', weapon_id)}**\n"
    result += f"📊 Урон: {weapon.get('damage', 1.0)}\n"
    result += f"🎯 Точность: {weapon.get('accuracy', 70)}%\n"
    result += f"📦 Тип: {weapon.get('type', 'тупое')}\n"

    max_durability = weapon.get('max_durability', 999)
    if max_durability >= 999:
        result += f"🔧 Прочность: ∞\n"
    else:
        result += f"🔧 Прочность: {max_durability}\n"

    stun = weapon.get('stun_chance', 0)
    if stun > 0:
        result += f"💫 Шанс оглушения: {stun}% (при ударе в голову)\n"

    result += f"💰 Цена: {weapon.get('price', 0)} никелей\n"
    result += f"📝 {weapon.get('description', '')}"

    return result


def calculate_melee_damage(player) -> float:
    weapon_data = get_melee_weapon(player.melee_weapon)
    if not weapon_data:
        return 1.0

    from config.map_config import BALANCE

    base_damage = weapon_data.get('damage', 1.0)
    strength = player.skills.get("сила", 0)
    skill_multiplier = weapon_data.get('skill_multiplier', 1.0)

    damage_multiplier = 1.0 + (strength * skill_multiplier * 0.1)
    return base_damage * damage_multiplier


def calculate_melee_accuracy(player, target_part: str = None) -> int:
    weapon_data = get_melee_weapon(player.melee_weapon)
    if not weapon_data:
        return 70

    base_accuracy = weapon_data.get('accuracy', 70)
    strength = player.skills.get("сила", 0)

    accuracy = base_accuracy + (strength * 2)

    if target_part == "голова":
        accuracy -= 10

    return min(max(accuracy, 10), 95)


def calculate_melee_stun_chance(player, target_part: str = "голова") -> int:
    if target_part != "голова":
        return 0

    weapon_data = get_melee_weapon(player.melee_weapon)
    if not weapon_data:
        return 0

    if weapon_data.get('type') != "тупое":
        return 0

    base_stun = weapon_data.get('stun_chance', 0)
    strength = player.skills.get("сила", 0)

    return min(base_stun + strength, 50)


# ==================== КРОВОТЕЧЕНИЕ (0.4.5) ====================

def can_cause_bleeding(weapon_id: str) -> bool:
    """
    Может ли это оружие ближнего боя накладывать кровотечение.
    Только острое оружие.
    """
    weapon = get_melee_weapon(weapon_id)
    if not weapon:
        return False
    if weapon.get('type') != "острое":
        return False
    if weapon_id == "кулаки":
        return False
    return True


def get_melee_bleeding_chances(weapon_id: str) -> dict:
    """
    Шансы наложения кровотечения для острого оружия.
    Возвращает {"weak_chance": N, "strong_chance": M} или пустой dict.
    """
    from .weapon_system import get_bleeding_config

    if not can_cause_bleeding(weapon_id):
        return {}

    cfg = get_bleeding_config()
    sources = cfg.get('sources', {})
    return sources.get('melee_sharp', {})