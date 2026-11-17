# -*- coding: utf-8 -*-
# func/views/weapon_shop/_helpers.py - Общие константы и хелперы (0.4.4.6)
#
# Рефакторинг без изменения логики.

from ..helpers import WEAPONS
from config.map_config import MODULES


# ==================== КОНСТАНТЫ ====================

WEAPON_TYPE_PAGES = {
    "pistol": {"name": "Пистолеты", "emoji": "🔫", "description": "Компактное оружие. 1 выстрел за ход."},
    "smg": {"name": "Пистолеты-пулемёты", "emoji": "🔫", "description": "Очередь из 4 выстрелов с распределением."},
    "assault": {"name": "Автоматы", "emoji": "💥", "description": "Очередь из 2 выстрелов."},
    "mg": {"name": "Пулемёты", "emoji": "🔫", "description": "Очередь из 3 выстрелов. Light / Heavy."},
    "sniper": {"name": "Снайперские винтовки", "emoji": "🎯", "description": "Мощный точный выстрел."},
    "shotgun": {"name": "Дробовики", "emoji": "🔫", "description": "Смертельны вблизи."},
    "spec_w": {"name": "Специальное", "emoji": "💀", "description": "Уникальное вооружение."}
}

SLOT_PAGES = {
    "scope": {"name": "Прицелы", "emoji": "🔭", "description": "Оптические и коллиматорные прицелы."},
    "grip": {"name": "Рукояти", "emoji": "🖐️", "description": "Улучшают хват."},
    "muzzle": {"name": "Дуло", "emoji": "🔧", "description": "Пламегасители, глушители, компенсаторы, сошки."}
}

WEAPONS_PER_PAGE = 5
MAGAZINES_PER_PAGE = 5


# ==================== ФУНКЦИИ ====================

def get_weapons_by_type(weapon_type: str) -> list:
    return [
        wid for wid, wdata in WEAPONS.items()
        if isinstance(wdata, dict) and wdata.get('type') == weapon_type
    ]


def get_modules_by_slot(slot_id: str) -> list:
    modules = MODULES.get('modules', {})
    if not isinstance(modules, dict):
        return []
    result = []
    for mid, mdata in modules.items():
        if not isinstance(mdata, dict):
            continue
        if mdata.get('slot') == slot_id:
            result.append(mid)
    return result