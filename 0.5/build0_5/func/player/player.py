# -*- coding: utf-8 -*-
# func/player/player.py - Итоговый класс Player (0.4.8)
#
# ИСТОРИЯ:
#   0.4.4.8 — рефакторинг на миксины
#   0.4.8 — добавлен FactionMixin

from .init_mixin import PlayerInitMixin
from .body_mixin import BodyMixin
from .ammo_mixin import AmmoMixin
from .throwables_mixin import ThrowablesMixin
from .combat_mixin import CombatMixin
from .armor_mixin import ArmorMixin
from .legacy_mixin import LegacyMixin
from .faction_mixin import FactionMixin


class Player(
    PlayerInitMixin,
    FactionMixin,
    BodyMixin,
    AmmoMixin,
    ThrowablesMixin,
    CombatMixin,
    ArmorMixin,
    LegacyMixin,
):
    """
    Игрок 44: White Curtain.

    Миксины:
      • PlayerInitMixin  — __init__
      • FactionMixin     — фракции и лояльность
      • BodyMixin        — тело, стамина, холод, горение
      • AmmoMixin        — магазины, shell_ammo
      • ThrowablesMixin  — гранаты и ножи
      • CombatMixin      — ближний бой, модули, точность
      • ArmorMixin       — броня, противогаз, инвентари
      • LegacyMixin      — опыт, урон, дебаффы, статус
    """
    pass