# -*- coding: utf-8 -*-
# func/views/weapon_shop/__init__.py - Пакет оружейного магазина (0.4.4.6)
#
# Рефакторинг без изменения логики: единый weapon_shop.py разбит
# на отдельные модули по функциональности.

from .main_menu import WeaponShopMainMenu
from .consumables import (
    ConsumablesMenu,
    GrenadeBuyMenu,
    ThrowingKnifeBuyMenu,
)
from .weapon_types import WeaponTypeMenu
from .modules import ModuleSlotMenu
from .magazines import MagazineBuyMenu
from .melee import MeleeBuyMenu

__all__ = [
    "WeaponShopMainMenu",
    "ConsumablesMenu",
    "GrenadeBuyMenu",
    "ThrowingKnifeBuyMenu",
    "WeaponTypeMenu",
    "ModuleSlotMenu",
    "MagazineBuyMenu",
    "MeleeBuyMenu",
]