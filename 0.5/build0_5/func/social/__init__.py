# -*- coding: utf-8 -*-
# func/social/__init__.py - Публичный API пакета social (0.4.6)

from .brigade import Brigade, BrigadeMember
from .brigade_manager import brigade_manager

__all__ = [
    "Brigade",
    "BrigadeMember",
    "brigade_manager",
]