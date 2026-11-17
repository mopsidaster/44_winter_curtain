# -*- coding: utf-8 -*-
# func/game_manager/manager.py - Итоговый класс GameManager + синглтон (0.4.4.8)
#
# Рефакторинг без изменения логики: класс собран из миксинов.
# Публичный API не изменился — game_manager.foo(...) работает как раньше.

from .init_mixin import GameManagerInitMixin
from .players_mixin import PlayersMixin
from .damage_mixin import DamageMixin
from .transition_events_mixin import TransitionEventsMixin
from .combat_start_mixin import CombatStartMixin
from .move_mixin import MoveMixin


class GameManager(
    GameManagerInitMixin,
    PlayersMixin,
    DamageMixin,
    TransitionEventsMixin,
    CombatStartMixin,
    MoveMixin,
):
    """
    Менеджер игрового мира 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍.

    Разбит на миксины для навигации по коду:
      • GameManagerInitMixin     — __init__ (флаги ивентов, зоны)
      • PlayersMixin             — загрузка, создание, поиск, возрождение
      • DamageMixin              — мелкие утилиты урона (тело, маска)
      • TransitionEventsMixin    — случайные события перехода (safe/danger/mixed)
      • CombatStartMixin         — старт боя, отправка embed'ов
      • MoveMixin                — move_player с обработкой событий

    Порядок наследования: Init первым (для __init__), далее — по логике.
    Конфликтов имён между миксинами нет.
    """
    pass


# Синглтон
game_manager = GameManager()