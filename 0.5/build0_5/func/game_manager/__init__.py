# -*- coding: utf-8 -*-
# func/game_manager/__init__.py - Публичный API пакета GameManager (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Внешние импорты "from .game_manager import game_manager" /
# "from func.game_manager import game_manager" продолжают работать без правок.

from .manager import GameManager, game_manager

__all__ = [
    "GameManager",
    "game_manager",
]