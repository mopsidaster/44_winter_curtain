# -*- coding: utf-8 -*-
# utils/calculations.py - Расчёты в одном месте (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.2.10 — единый источник правды для порога опыта
#   0.4.7.2  — новая линейно-логарифмическая формула: 100 + (level-1)*50

from config.map_config import BALANCE


def calculate_xp_to_level(current_level: int) -> int:
    """
    0.4.7.2: линейная формула.

    lvl 1 → 100
    lvl 2 → 150
    lvl 3 → 200
    lvl 4 → 250
    ...
    lvl N → 100 + (N-1)*50
    """
    if current_level < 1:
        current_level = 1
    return 100 + (current_level - 1) * 50


def get_heal_amount() -> float:
    """Сколько HP восстанавливает аптечка."""
    return 5.0