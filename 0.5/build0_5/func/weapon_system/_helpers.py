# -*- coding: utf-8 -*-
# func/weapon_system/_helpers.py - Приватные хелперы (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено
#   0.4.8.7 — allowed_weapons (эм-усилитель АК),
#             assault_smg (эм-стабилизатор),
#             headshot_accuracy_bonus (пистолеты).

import random
import re

from config.map_config import WEAPONS, MODULES, BALANCE

from utils.logger import get_logger

logger = get_logger()


def _parse_zoom_from_id(module_id: str):
    if not module_id or not isinstance(module_id, str):
        return None
    match = re.search(r'[хx](\d+)', module_id)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _is_module_compatible(module_type: str, weapon_type: str,
                          weapon_id: str = None, module_id: str = None) -> bool:
    """Проверка совместимости типа модуля с типом оружия."""
    module_data = {}
    if module_id and isinstance(module_id, str):
        m = MODULES.get('modules', {}).get(module_id)
        if isinstance(m, dict):
            module_data = m

    slot = module_data.get('slot') if module_data else None

    # 0.4.8.7: allowed_weapons — жёсткое ограничение по ID оружия
    allowed = module_data.get("allowed_weapons") if module_data else None
    if isinstance(allowed, list) and allowed:
        if weapon_id not in allowed:
            return False

    if module_type == "mg_only":
        return weapon_type == "mg"

    if weapon_type == "mg" and weapon_id:
        weapon = WEAPONS.get(weapon_id) or {}
        if weapon.get('subtype') == "heavy":
            if slot in ("scope", "grip") and module_type != "mg_only":
                return False

    if weapon_type == "smg" and module_id and slot == 'scope':
        zoom = _parse_zoom_from_id(module_id)
        if zoom is not None and zoom >= 6:
            return False

    if module_type == "all":
        return True
    if module_type == "all_wo_pistol":
        return weapon_type != "pistol"
    if module_type == "all_wo_shotgun":
        return weapon_type != "shotgun"
    if module_type == "all_wo_pistol_and_shotgun":
        return weapon_type not in ("pistol", "shotgun")
    if module_type == "all_wo_pistol_and_sniper":
        return weapon_type not in ("pistol", "sniper")
    if module_type == "assault":
        return weapon_type == "assault"
    # 0.4.8.7
    if module_type == "assault_smg":
        return weapon_type in ("assault", "smg")
    if module_type == "sniper":
        return weapon_type == "sniper"
    if module_type == "shotgun":
        return weapon_type == "shotgun"
    if module_type == "shotgun_and_assault":
        return weapon_type in ("shotgun", "assault")
    if module_type == "mg_only":
        return weapon_type == "mg"
    return False


def _get_optics_close_penalty(player, weapon_id: str, distance: str) -> float:
    if distance != "close":
        return 0.0

    optics_cfg = BALANCE.get('optics', {})
    penalty_per_zoom = optics_cfg.get('close_penalty_per_zoom', 12.5)
    min_zoom = optics_cfg.get('min_zoom_for_penalty', 3)

    equipped = getattr(player, 'equipped_modules', {}) or {}
    scope_id = equipped.get('scope')
    if not scope_id:
        return 0.0

    module_data = MODULES.get('modules', {}).get(scope_id)
    if not isinstance(module_data, dict):
        return 0.0

    zoom = _parse_zoom_from_id(scope_id)
    if zoom is None or zoom < min_zoom:
        return 0.0

    penalty = (zoom - 2) * (penalty_per_zoom / 100.0)
    return penalty


def _get_modules_accuracy_bonus(player, weapon_id: str, distance: str) -> float:
    from .weapons import get_weapon_type, is_spec_weapon

    bonus = 0.0
    weapon_type = get_weapon_type(weapon_id)

    if is_spec_weapon(weapon_id):
        return 0.0

    equipped = getattr(player, 'equipped_modules', {}) or {}
    if not equipped:
        return 0.0

    for slot, module_id in equipped.items():
        if not module_id:
            continue

        module_data = MODULES.get('modules', {}).get(module_id)
        if not isinstance(module_data, dict):
            continue

        module_type = module_data.get('type', 'all')
        if not _is_module_compatible(module_type, weapon_type, weapon_id, module_id):
            continue

        acc_bonus = 0.0

        special_weapon_bonus = module_data.get('special_weapon_bonus')
        if special_weapon_bonus and weapon_id in special_weapon_bonus:
            acc_bonus = special_weapon_bonus[weapon_id].get(distance, 0.0)
        else:
            acc_by_weapon = module_data.get('accuracy_by_weapon')
            if acc_by_weapon and weapon_type in acc_by_weapon:
                acc_bonus = acc_by_weapon[weapon_type].get(distance, 0.0)
            else:
                acc_bonus = module_data.get('accuracy', {}).get(distance, 0.0)

        special = module_data.get('special')
        if special and 'proc_chance' in special:
            if random.random() > special['proc_chance']:
                acc_bonus = 0.0

        bonus += acc_bonus

    return bonus


def _get_headshot_accuracy_bonus(player) -> int:
    """
    Суммарный бонус точности в голову от прицелов (headshot_accuracy).
    """
    if player is None:
        return 0

    equipped = getattr(player, 'equipped_modules', {}) or {}
    if not equipped:
        return 0

    total = 0
    seen = set()
    for slot, module_id in equipped.items():
        if not module_id or module_id in seen:
            continue
        seen.add(module_id)

        module_data = MODULES.get('modules', {}).get(module_id)
        if not isinstance(module_data, dict):
            continue

        bonus = module_data.get('headshot_accuracy', 0)
        try:
            total += int(bonus)
        except (TypeError, ValueError):
            continue

    return total