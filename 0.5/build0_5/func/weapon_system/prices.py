# -*- coding: utf-8 -*-
# func/weapon_system/prices.py - Цены оружия, магазинов, модулей (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Добавлено логирование через utils.logger.

from config.map_config import BALANCE, MODULES

from utils.logger import get_logger

logger = get_logger()


def get_weapon_price(weapon_id: str) -> int:
    return BALANCE.get('prices', {}).get('weapon', {}).get(weapon_id, 0)


def get_magazine_price(magazine_id: str) -> int:
    return BALANCE.get('prices', {}).get('magazine', {}).get(magazine_id, 0)


def get_module_price(module_id: str) -> int:
    module_data = MODULES.get('modules', {}).get(module_id)
    if not isinstance(module_data, dict):
        return 0
    return module_data.get('price', 0)