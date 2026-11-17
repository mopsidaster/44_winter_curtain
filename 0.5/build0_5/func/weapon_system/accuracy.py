# -*- coding: utf-8 -*-
# func/weapon_system/accuracy.py - Точность стрельбы (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Добавлено логирование через utils.logger.

from config.map_config import BALANCE, MODULES

from .weapons import is_mg
from ._helpers import _get_modules_accuracy_bonus, _get_optics_close_penalty

from utils.logger import get_logger

logger = get_logger()


def get_weapon_accuracy(weapon_id: str, player_skill: int = 0,
                        distance: str = "close", player=None) -> float:
    """
    Итоговая точность оружия на дистанции.

    Базовая точность оружия + бонус от навыка «меткость»,
    умноженные на модификатор дистанции, плюс бонус от модулей,
    минус штраф от оптики на близкой дистанции, минус штраф MG
    на близкой дистанции.
    """
    from .weapons import get_weapon

    weapon = get_weapon(weapon_id)
    if not weapon:
        return 0.0

    base_accuracy = weapon.get("accuracy", 0.5)
    skill_bonus = player_skill * (BALANCE['skills']['accuracy_per_level'] / 100)

    distance_config = BALANCE.get('distance', {}).get(distance, {})
    distance_modifier = distance_config.get('modifier', 1.0)

    accuracy = (base_accuracy + skill_bonus) * distance_modifier

    # MG штраф на близкой
    if is_mg(weapon_id) and distance == "close":
        mg_cfg = BALANCE.get('combat', {}).get('mg', {})
        accuracy *= mg_cfg.get('close_penalty', 0.6)

    if player and hasattr(player, 'equipped_modules'):
        accuracy += _get_modules_accuracy_bonus(player, weapon_id, distance)
        accuracy -= _get_optics_close_penalty(player, weapon_id, distance)

    return max(0.0, min(accuracy, 0.95))