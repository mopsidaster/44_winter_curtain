# -*- coding: utf-8 -*-
# func/weapon_system/modules.py - Слоты и совместимость модулей (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Добавлено логирование через utils.logger.

from config.map_config import WEAPONS, MODULES

from ._helpers import _is_module_compatible
from .weapons import get_weapon, get_weapon_type, is_spec_weapon

from utils.logger import get_logger

logger = get_logger()


# ==================== СЛОТЫ МОДУЛЕЙ ====================

def get_module_slots(module_id: str) -> list:
    """
    Все слоты модуля (для сошек — два).
    0.4.4.7.2: защита от не-dict — не падает на строках.
    """
    if not module_id or not isinstance(module_id, str):
        return []
    module_data = MODULES.get('modules', {}).get(module_id)
    if not isinstance(module_data, dict):
        return []
    slots = module_data.get('slots')
    if isinstance(slots, list) and slots:
        return slots
    s = module_data.get('slot')
    return [s] if s else []


def get_module_slot(module_id: str) -> str:
    """Первый слот модуля (совместимость)."""
    slots = get_module_slots(module_id)
    return slots[0] if slots else None


# ==================== СОВМЕСТИМОСТЬ ====================

def can_install_module(weapon_id: str, module_id: str) -> tuple:
    """
    Проверка установки модуля.

    0.4.4.7.2:
      • Защита от не-dict (модуль-строка возвращает False).
      • Логирование причины отказа.
      • Heavy MG: запрет прицелов и рукоятей.
    """
    weapon = get_weapon(weapon_id)
    if not weapon:
        return False, "Оружие не найдено"

    if not module_id or not isinstance(module_id, str):
        return False, "Неверный ID модуля"

    module_data = MODULES.get('modules', {}).get(module_id)
    if not isinstance(module_data, dict):
        return False, "Модуль не найден (или повреждён)"

    if is_spec_weapon(weapon_id):
        return False, "На специальное оружие модули не устанавливаются"

    weapon_type = weapon.get("type", "unknown")
    module_type = module_data.get('type', 'all')
    module_slot = module_data.get('slot')

    # Heavy MG: запрет прицелов и рукоятей
    if weapon_type == "mg" and weapon.get("subtype") == "heavy":
        if module_slot in ("scope", "grip") and module_type != "mg_only":
            reason = "Тяжёлый пулемёт не поддерживает прицелы и рукояти"
            logger.info(
                f"[weapon_system] can_install_module({weapon_id}, {module_id}): False — {reason}"
            )
            return False, reason

    if not _is_module_compatible(module_type, weapon_type, weapon_id, module_id):
        reason = f"Модуль не подходит для типа оружия «{weapon_type}»"
        logger.info(
            f"[weapon_system] can_install_module({weapon_id}, {module_id}): False — {reason}"
        )
        return False, reason

    return True, "OK"


def get_modules_for_weapon(weapon_id: str) -> list:
    if is_spec_weapon(weapon_id):
        return []
    weapon = get_weapon(weapon_id)
    if not weapon:
        return []
    weapon_type = weapon.get("type", "unknown")

    result = []
    for module_id, module_data in MODULES.get('modules', {}).items():
        if not isinstance(module_data, dict):
            continue
        module_type = module_data.get('type', 'all')
        if not _is_module_compatible(module_type, weapon_type, weapon_id, module_id):
            continue
        ok, _ = can_install_module(weapon_id, module_id)
        if ok:
            result.append(module_id)
    return result


def uninstall_all_modules(player) -> list:
    """Снять все установленные модули с игрока и вернуть их в инвентарь."""
    removed = []
    equipped = getattr(player, 'equipped_modules', {}) or {}
    seen = set()
    for slot in list(equipped.keys()):
        module_id = equipped.get(slot)
        if module_id and module_id not in seen:
            if module_id not in player.modules_inventory:
                player.modules_inventory.append(module_id)
            equipped[slot] = None
            removed.append(module_id)
            seen.add(module_id)
    return removed