# -*- coding: utf-8 -*-
# func/player/throwables_mixin.py - Гранаты и метательные ножи (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Добавлено логирование через utils.logger.

from utils.logger import get_logger

logger = get_logger()


class ThrowablesMixin:
    """Инвентарь гранат и метательных ножей."""

    # ==================== ГРАНАТЫ ====================

    def add_grenade(self, grenade_id: str, count: int = 1):
        if count <= 0:
            return
        self.grenades_inventory[grenade_id] = (
                self.grenades_inventory.get(grenade_id, 0) + count
        )

    def consume_grenade(self, grenade_id: str) -> bool:
        current = self.grenades_inventory.get(grenade_id, 0)
        if current <= 0:
            return False
        if current == 1:
            del self.grenades_inventory[grenade_id]
        else:
            self.grenades_inventory[grenade_id] = current - 1
        return True

    def get_grenade_count(self, grenade_id: str) -> int:
        return self.grenades_inventory.get(grenade_id, 0)

    def get_all_grenades(self) -> dict:
        return dict(self.grenades_inventory)

    def get_grenades_total(self) -> int:
        return sum(self.grenades_inventory.values())

    # ==================== НОЖИ ====================

    def add_knife(self, knife_id: str, count: int = 1):
        if count <= 0:
            return
        self.throwing_knives_inventory[knife_id] = (
                self.throwing_knives_inventory.get(knife_id, 0) + count
        )

    def consume_knife(self, knife_id: str) -> bool:
        current = self.throwing_knives_inventory.get(knife_id, 0)
        if current <= 0:
            return False
        if current == 1:
            del self.throwing_knives_inventory[knife_id]
        else:
            self.throwing_knives_inventory[knife_id] = current - 1
        return True

    def get_knife_count(self, knife_id: str) -> int:
        return self.throwing_knives_inventory.get(knife_id, 0)

    def get_all_knives(self) -> dict:
        return dict(self.throwing_knives_inventory)

    def get_knives_total(self) -> int:
        return sum(self.throwing_knives_inventory.values())