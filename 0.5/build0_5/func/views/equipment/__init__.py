# -*- coding: utf-8 -*-
# func/views/equipment/__init__.py - Пакет снаряжения (0.4.4.7.1)
#
# Рефакторинг без изменения логики: единый equipment.py разбит
# на отдельные модули по функциональности.

from .main_menu import EquipmentMenu
from .shell_load import _ShellLoadMenu
from .weapon_change import _WeaponChangeMenu
from .modules import ModuleManagementMenu, ModuleInstallSelect
from .magazine_insert import MagazineInsertMenu
from .load_magazine import EquipmentLoadMenu, EquipmentLoadSelectMenu
from .melee_change import MeleeChangeMenu

__all__ = [
    "EquipmentMenu",
    "_ShellLoadMenu",
    "_WeaponChangeMenu",
    "ModuleManagementMenu",
    "ModuleInstallSelect",
    "MagazineInsertMenu",
    "EquipmentLoadMenu",
    "EquipmentLoadSelectMenu",
    "MeleeChangeMenu",
]