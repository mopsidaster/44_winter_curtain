# -*- coding: utf-8 -*-
# func/game_manager/damage_mixin.py - Мелкие хелперы урона (0.4.4.8)
#
# Рефакторинг без изменения логики.

import random

from ..player import Player

from utils.logger import get_logger

logger = get_logger()


class DamageMixin:
    """Мелкие утилиты урона: радиация-заглушка, распределение по телу, урон маске."""

    def check_radiation_damage(self, player: Player) -> str:
        # Заглушка: реальная радиация обрабатывается в disease_system
        return ""

    def _apply_damage_to_body(self, player: Player, damage: float):
        alive_parts = player.get_alive_body_parts()
        if alive_parts:
            target_part = random.choice(alive_parts)
            result = player.take_body_part_damage(target_part, damage)
            if result.get("destroyed", False):
                part_names = {"голова": "Голова", "торс": "Торс", "руки": "Руки", "ноги": "Ноги"}
                logger.info(
                    f"Часть тела {part_names.get(target_part, target_part)} "
                    f"игрока {player.name} уничтожена"
                )
        else:
            player.is_alive = False
            logger.info(f"Игрок {player.name} погиб (нет живых частей тела)")

    def _damage_mask(self, player: Player) -> None:
        if player.has_gas_mask and player.gas_mask.get("надет", False):
            player.gas_mask["прочность"] -= 1
            if player.gas_mask["прочность"] <= 0:
                player.gas_mask["состояние"] = "разбитый"
                player.gas_mask["фильтр_вставлен"] = False
                player.gas_mask["фильтр_прочность"] = 0.0
                player.equipped_filter = None
                logger.info(f"Игрок {player.name}: противогаз разбит")