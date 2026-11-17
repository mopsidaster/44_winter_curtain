# -*- coding: utf-8 -*-
# func/weapon_system/weapons.py - Оружие, типы, дробовики (0.4.7.6)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено
#   0.4.7.2 — get_weapon_damage_with_modules
#   0.4.7.6 — подтипы снайперских: get_sniper_subtype,
#             is_semi_auto_sniper, is_bolt_action_sniper

from config.map_config import WEAPONS, BALANCE, MODULES

from utils.logger import get_logger

logger = get_logger()


# ==================== ОРУЖИЕ ====================

def get_weapon(weapon_id: str) -> dict:
    return WEAPONS.get(weapon_id)


def get_weapon_type(weapon_id: str) -> str:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return "unknown"
    return weapon.get("type", "unknown")


def is_spec_weapon(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("spec_weapon", False)


def is_shotgun(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("shotgun", False) or weapon.get("type") == "shotgun"


def is_shell_loaded_weapon(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("shell_loading", False)


def is_smg(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("type") == "smg"


def is_mg(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("type") == "mg"


def is_light_mg(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("type") == "mg" and weapon.get("subtype") == "light"


def is_heavy_mg(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("type") == "mg" and weapon.get("subtype") == "heavy"


def is_grenade(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("type") == "grenade"


def is_throwing_knife(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("type") == "throwing_knife"


def is_throwable(weapon_id: str) -> bool:
    return is_grenade(weapon_id) or is_throwing_knife(weapon_id)


def has_builtin_suppressor(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    return weapon.get("builtin_module") == 'глушитель'


# ==================== 0.4.7.6: ПОДТИПЫ СНАЙПЕРОК ====================

def is_sniper(weapon_id: str) -> bool:
    return get_weapon_type(weapon_id) == "sniper"


def get_sniper_subtype(weapon_id: str) -> str:
    """
    0.4.7.6: подтип снайперской винтовки.
    Возвращает 'semi-auto', 'bolt-action' или '' (если не снайперка).
    """
    weapon = get_weapon(weapon_id)
    if not weapon:
        return ""
    if weapon.get("type") != "sniper":
        return ""
    return weapon.get("subtype", "bolt-action")


def is_semi_auto_sniper(weapon_id: str) -> bool:
    return get_sniper_subtype(weapon_id) == "semi-auto"


def is_bolt_action_sniper(weapon_id: str) -> bool:
    return get_sniper_subtype(weapon_id) == "bolt-action"


def get_sniper_subtype_config(weapon_id: str) -> dict:
    """
    Возвращает конфиг подтипа из balance.sniper_subtypes.
    """
    subtype = get_sniper_subtype(weapon_id)
    if not subtype:
        return {}

    cfg = BALANCE.get('sniper_subtypes', {})
    return cfg.get(subtype, {})


# ==================== УРОН ====================

def get_weapon_damage(weapon_id: str, ammo_type: str = "оболочечные") -> float:
    from .ammo import get_ammo_type

    weapon = get_weapon(weapon_id)
    ammo = get_ammo_type(ammo_type)
    if not weapon:
        return 0
    base_damage = weapon.get("damage", 1.0)
    multiplier = ammo.get("multiplier", 1.0) if ammo else 1.0
    return base_damage * multiplier


def get_modules_damage_bonus(player, weapon_id: str) -> float:
    """
    Суммарный бонус к урону от установленных модулей.
    Учитываются только модули с полем 'damage_bonus'.
    """
    if player is None:
        return 0.0

    equipped = getattr(player, 'equipped_modules', {}) or {}
    if not equipped:
        return 0.0

    total = 0.0
    seen = set()

    for slot, module_id in equipped.items():
        if not module_id or module_id in seen:
            continue
        seen.add(module_id)

        module_data = MODULES.get('modules', {}).get(module_id)
        if not isinstance(module_data, dict):
            continue

        bonus = module_data.get('damage_bonus', 0)
        try:
            total += float(bonus)
        except (TypeError, ValueError):
            continue

    return total


def get_weapon_damage_with_modules(player, weapon_id: str) -> float:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return 0.0
    base = float(weapon.get("damage", 1.0))
    bonus = get_modules_damage_bonus(player, weapon_id)
    return base + bonus


def get_weapon_base_accuracy(weapon_id: str) -> float:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return 0.0
    return weapon.get("accuracy", 0.5)


# ==================== ДРОБОВИКИ ====================

def get_shotgun_damage_multiplier(distance: str, ammo_type: str = None) -> float:
    from .ammo import get_ammo_type  # noqa: F401

    shotgun_cfg = BALANCE.get('shotgun', {})
    dist_cfg = shotgun_cfg.get('distance_damage_mult', {})

    if distance == "far":
        far_unlock_ammo = shotgun_cfg.get('far_unlock_ammo', 'пулевой')
        if ammo_type == far_unlock_ammo:
            general = BALANCE.get('distance', {}).get('far', {}).get('modifier', 0.5)
            return general
        return 0.0

    return dist_cfg.get(distance, 1.0)


def is_shotgun_far_blocked(ammo_type: str = None) -> bool:
    shotgun_cfg = BALANCE.get('shotgun', {})
    if not shotgun_cfg.get('far_blocked', True):
        return False
    far_unlock_ammo = shotgun_cfg.get('far_unlock_ammo', 'пулевой')
    return ammo_type != far_unlock_ammo


def get_shotgun_close_bonus(ammo_type: str) -> float:
    from .ammo import get_ammo_type

    ammo = get_ammo_type(ammo_type)
    if not ammo:
        return 1.0
    return float(ammo.get('close_multiplier', 1.0))


def get_shotgun_ammo_damage_bonus(ammo_type: str) -> float:
    from .ammo import get_ammo_type

    ammo = get_ammo_type(ammo_type)
    if not ammo:
        return 0.0
    return float(ammo.get('damage_bonus', 0.0))


# ==================== ПИСТОЛЕТНЫЕ КАЛИБРЫ ====================

PISTOL_CALIBERS = {"9x18", "9x19", ".44 Магнум"}


def is_pistol_caliber(weapon_id: str) -> bool:
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False
    caliber = weapon.get('caliber')
    return caliber in PISTOL_CALIBERS

def get_weapon_double_shot_config(weapon_id: str) -> dict:
    """
    0.4.8.7: конфиг выстрела дуплетом (только Дуплет).
    Возвращает {"enabled": bool, "ammo_cost": 2, "damage_mult": 2.0,
                "accuracy_penalty": 0.10} или {}.
    """
    weapon = get_weapon(weapon_id)
    if not isinstance(weapon, dict):
        return {}
    cfg = weapon.get("double_shot")
    if not isinstance(cfg, dict) or not cfg.get("enabled", False):
        return {}
    return cfg