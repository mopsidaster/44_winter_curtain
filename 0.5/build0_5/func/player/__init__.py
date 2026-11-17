# -*- coding: utf-8 -*-
# func/player/__init__.py - Публичный API пакета Player (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Внешние импорты "from func.player import Player" / "from .player import Player"
# продолжают работать без правок.

from .player import Player
from ._constants import DEFAULT_SKILLS, _normalize_skills

__all__ = [
    "Player",
    "DEFAULT_SKILLS",
    "_normalize_skills",
]