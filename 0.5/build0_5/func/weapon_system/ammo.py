# -*- coding: utf-8 -*-
# func/weapon_system/ammo.py - Магазины, патроны, зажигательный, кровотечение (0.4.5)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено из weapon_system.py
#   0.4.5   — get_bleeding_config, is_bleeding_ammo

from config.map_config import WEAPONS, MAGAZINES, AMMO, BALANCE

from utils.logger import get_logger

logger = get_logger()


# ==================== МАГАЗИНЫ ====================

def get_magazine(magazine_id: str) -> dict:
    return MAGAZINES.get(magazine_id)


def get_weapon_magazines(weapon_id: str) -> list:
    weapon = WEAPONS.get(weapon_id)
    if not weapon:
        return []
    return weapon.get("magazines", [])


def is_magazine_compatible(weapon_id: str, magazine_id: str) -> bool:
    weapon = get_weapon_safe(weapon_id)
    magazine = get_magazine(magazine_id)
    if not weapon or not magazine:
        return False
    weapon_mags = weapon.get('magazines', [])
    if magazine_id in weapon_mags:
        return True
    if magazine.get("weapon") == weapon_id:
        if magazine.get("caliber") == weapon.get("caliber"):
            return True
    return False


def get_magazine_capacity(magazine_id: str) -> int:
    magazine = get_magazine(magazine_id)
    if not magazine:
        return 0
    return magazine.get("capacity", 0)


def get_available_magazines_for_weapon(weapon_id: str, player) -> list:
    available = []
    weapon_magazines = get_weapon_magazines(weapon_id)
    for mag in player.get_uninstalled_magazines():
        if mag["type_id"] in weapon_magazines:
            available.append(mag)
    return available


def get_weapon_max_ammo(weapon_id: str, player) -> int:
    if not player.equipped_magazine:
        return 0
    equipped = player.get_equipped_magazine_obj()
    if not equipped:
        return 0
    mag_data = get_magazine(equipped["type_id"])
    if not mag_data:
        return 0
    return mag_data.get("capacity", 0)


def get_current_ammo(weapon_id: str, player) -> int:
    from .weapons import is_shell_loaded_weapon

    if is_shell_loaded_weapon(weapon_id):
        return player.get_shell_ammo_count(weapon_id)

    if not player.equipped_magazine:
        return 0
    equipped = player.get_equipped_magazine_obj()
    if not equipped:
        return 0
    return sum(equipped.get("ammo", {}).values())


def get_ammo_types_in_magazine(player) -> list:
    if not player.equipped_magazine:
        return []
    equipped = player.get_equipped_magazine_obj()
    if not equipped:
        return []
    return list(equipped.get("ammo", {}).keys())


def can_reload(weapon_id: str, player) -> bool:
    from .weapons import is_shell_loaded_weapon

    if is_shell_loaded_weapon(weapon_id):
        weapon = WEAPONS.get(weapon_id)
        if not weapon:
            return False
        caliber = weapon.get('caliber')
        ammo_types = get_caliber_ammo_types(caliber)
        for atype in ammo_types:
            if player.inventory.get(atype, 0) > 0:
                return True
        return False

    if not player.equipped_magazine:
        return False
    current_ammo = get_current_ammo(weapon_id, player)
    max_ammo = get_weapon_max_ammo(weapon_id, player)
    if current_ammo >= max_ammo:
        return False
    equipped = player.get_equipped_magazine_obj()
    if not equipped:
        return False
    mag_data = get_magazine(equipped["type_id"])
    if not mag_data:
        return False
    caliber = mag_data.get("caliber")
    ammo_types = get_caliber_ammo_types(caliber)
    for ammo_type in ammo_types:
        if player.inventory.get(ammo_type, 0) > 0:
            return True
    return False


def get_weapon_safe(weapon_id: str) -> dict:
    return WEAPONS.get(weapon_id)


# ==================== ПАТРОНЫ ====================

def get_ammo_type(ammo_type_id: str) -> dict:
    return AMMO["ammo_types"].get(ammo_type_id)


def get_caliber(caliber_id: str) -> dict:
    return AMMO["calibers"].get(caliber_id)


def get_caliber_ammo_types(caliber: str) -> list:
    caliber_data = get_caliber(caliber)
    if not caliber_data:
        return []
    return caliber_data.get("types", [])


def get_ammo_type_for_caliber(caliber: str) -> list:
    return get_caliber_ammo_types(caliber)


def get_ammo_price(ammo_type: str, caliber: str = None) -> int:
    prices = BALANCE.get('prices', {}).get('ammo', {})
    if caliber:
        caliber_prices = prices.get(caliber, {})
        return caliber_prices.get(ammo_type, 0)
    for caliber_name, caliber_prices in prices.items():
        if ammo_type in caliber_prices:
            return caliber_prices[ammo_type]
    return 0


def get_ammo_price_for_weapon(weapon_id: str, ammo_type: str) -> int:
    weapon = WEAPONS.get(weapon_id)
    if not weapon:
        return 0
    caliber = weapon.get('caliber')
    return get_ammo_price(ammo_type, caliber)


def is_armor_piercing(ammo_type: str) -> bool:
    if ammo_type == "бронебойные":
        return True
    ammo = get_ammo_type(ammo_type)
    if ammo and ammo.get('armor_piercing'):
        return True
    return False


def is_incendiary(ammo_type: str) -> bool:
    if ammo_type == "трассеры" or ammo_type == "зажигательный":
        return True
    ammo = get_ammo_type(ammo_type)
    return bool(ammo and ammo.get('incendiary'))


def is_expansive(ammo_type: str) -> bool:
    return ammo_type == "экспансивные"


def is_buckshot(ammo_type: str) -> bool:
    return ammo_type == "картечь"


def is_slug(ammo_type: str) -> bool:
    return ammo_type == "пулевой"


def is_shotgun_ammo(ammo_type: str) -> bool:
    ammo = get_ammo_type(ammo_type)
    if not ammo:
        return False
    return ammo.get('shotgun_only', False)


def ammo_ignores_armor(ammo_type: str) -> bool:
    return is_armor_piercing(ammo_type)


def get_ammo_damage_multiplier(ammo_type: str, target_has_armor: bool = False) -> float:
    ammo = get_ammo_type(ammo_type)
    if not ammo:
        return 1.0

    base_multiplier = ammo.get("multiplier", 1.0)

    if is_expansive(ammo_type):
        if target_has_armor:
            return base_multiplier * 0.35
        return base_multiplier

    if ammo_type == "бронебойно_экспансивные":
        return base_multiplier

    # 0.4.8.9: универсально — если у патрона есть incendiary и explosive_multiplier,
    # применяем его (трассеры и зажигательные работают одинаково).
    if ammo.get("incendiary") or ammo_type in ("трассеры", "зажигательный"):
        return ammo.get("explosive_multiplier", 1.25)

    if is_armor_piercing(ammo_type):
        return base_multiplier

    return base_multiplier


# ==================== ЗАЖИГАТЕЛЬНЫЙ ====================

def get_incendiary_config() -> dict:
    return BALANCE.get('incendiary', {})


def get_incendiary_damage_per_tick() -> float:
    return float(get_incendiary_config().get('damage_per_tick', 1.0))


def get_incendiary_turns_per_stack() -> int:
    return int(get_incendiary_config().get('turns_per_stack', 2))


def get_incendiary_stacks_enabled() -> bool:
    return bool(get_incendiary_config().get('stacks', True))


# ==================== КРОВОТЕЧЕНИЕ (0.4.5) ====================

def get_bleeding_config() -> dict:
    """Весь блок bleeding из balance.json."""
    return BALANCE.get('bleeding', {})


def is_bleeding_ammo(ammo_type: str) -> bool:
    """
    Может ли этот тип патрона накладывать кровотечение.
    По ТЗ: экспансивные и бронебойно-экспансивные.
    """
    if ammo_type in ("экспансивные", "бронебойно_экспансивные"):
        return True
    return False


def get_bleeding_ammo_chances(ammo_type: str) -> dict:
    """
    Шансы наложения кровотечения для конкретного патрона.
    Возвращает {"weak_chance": N, "strong_chance": M} или пустой dict.
    """
    cfg = get_bleeding_config()
    sources = cfg.get('sources', {})

    if not is_bleeding_ammo(ammo_type):
        return {}

    # Все «стрелковые» патроны используют один и тот же источник.
    return sources.get('expansive_ammo', {})

# ==================== ФОРМАТ КЛЮЧА ПАТРОНА (0.4.6.3) ====================

AMMO_KEY_SEPARATOR = "|"


def make_ammo_key(caliber: str, ammo_type: str) -> str:
    """
    0.4.6.3: сформировать ключ для инвентаря: '<caliber>|<ammo_type>'.
    Например: '9x19|экспансивные'.
    """
    return f"{caliber}{AMMO_KEY_SEPARATOR}{ammo_type}"


def parse_ammo_key(key: str) -> tuple:
    """
    Разобрать ключ '<caliber>|<ammo_type>'.
    Возвращает (caliber, ammo_type) или (None, key), если ключ старый.
    """
    if AMMO_KEY_SEPARATOR in key:
        parts = key.split(AMMO_KEY_SEPARATOR, 1)
        return parts[0], parts[1]
    return None, key


def is_new_ammo_key(key: str) -> bool:
    return AMMO_KEY_SEPARATOR in key