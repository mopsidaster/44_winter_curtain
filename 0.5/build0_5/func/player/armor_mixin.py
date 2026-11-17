# -*- coding: utf-8 -*-
# func/player/armor_mixin.py - Броня, противогаз, инвентари (0.4.8 Оптимизация)

from config.map_config import BALANCE, ARMOR
from utils.logger import get_logger

logger = get_logger()

class ArmorMixin:
    """Броня/шлем, противогаз, инвентари оружия и фильтров."""

    def equip_armor_item(self, item_id: str) -> tuple:
        from ..armor_system import equip_item as armor_equip
        result = armor_equip(self, item_id)

        if result.get('success'):
            self.recalc_body_parts_max_hp()
            self.recalc_max_stamina()
            self._apply_gas_mask_bonus()

        return result.get('success', False), result.get('message', '')

    def unequip_armor_item(self, slot: str) -> tuple:
        from ..armor_system import unequip_item as armor_unequip
        result = armor_unequip(self, slot)

        if result.get('success'):
            self.recalc_body_parts_max_hp()
            self.recalc_max_stamina()
            self._apply_gas_mask_bonus()

        return result.get('success', False), result.get('message', '')

    # ==================== ПРОТИВОГАЗ ====================

    def _apply_gas_mask_bonus(self):
        base_max = BALANCE['gas_mask'].get('max_durability', 15)
        helmet_id = getattr(self, 'helmet', None)
        bonus = 0
        if helmet_id:
            helmet_data = ARMOR.get('armor_sets', {}).get(helmet_id, {})
            if isinstance(helmet_data, dict):
                bonus = helmet_data.get('gas_mask_durability_bonus', 0)

        new_max = base_max + bonus
        old_max = self.gas_mask.get('max_durability', base_max)

        if old_max == new_max:
            return

        diff = new_max - old_max
        current = self.gas_mask.get('прочность', 0)

        if diff > 0:
            current += diff
        else:
            if current > new_max:
                current = new_max

        self.gas_mask['max_durability'] = new_max
        self.gas_mask['прочность'] = max(0, min(current, new_max))
        self.gas_mask['base_max_durability'] = base_max
        self.gas_mask['helmet_bonus'] = bonus

    def get_gas_mask_max_durability(self) -> float:
        base_max = BALANCE['gas_mask'].get('max_durability', 15)
        helmet_id = getattr(self, 'helmet', None)
        bonus = 0
        if helmet_id:
            helmet_data = ARMOR.get('armor_sets', {}).get(helmet_id, {})
            if isinstance(helmet_data, dict):
                bonus = helmet_data.get('gas_mask_durability_bonus', 0)
        return base_max + bonus

    def get_gas_mask_base_max_durability(self) -> float:
        return BALANCE['gas_mask'].get('max_durability', 15)

    def is_gas_mask_at_max(self) -> bool:
        return self.gas_mask.get('прочность', 0) >= self.get_gas_mask_max_durability()

    def repair_gas_mask_full(self):
        max_dur = self.get_gas_mask_max_durability()
        self.gas_mask['прочность'] = max_dur
        if max_dur > BALANCE['gas_mask'].get('worn_durability', 10):
            self.gas_mask['состояние'] = "целый"
        else:
            self.gas_mask['состояние'] = "поношенный"

    def get_armor_status_text(self) -> str:
        from ..armor_system import format_armor_status
        return format_armor_status(self)

    # ==================== ИНВЕНТАРИ ОРУЖИЯ ====================

    def add_weapon(self, weapon_id: str):
        if weapon_id not in self.weapons_inventory and weapon_id != self.weapon:
            self.weapons_inventory.append(weapon_id)

    def remove_weapon(self, weapon_id: str) -> bool:
        if weapon_id in self.weapons_inventory:
            self.weapons_inventory.remove(weapon_id)
            return True
        return False

    def add_melee(self, melee_id: str):
        if melee_id not in self.melee_inventory and melee_id != self.melee_weapon:
            self.melee_inventory.append(melee_id)

    def remove_melee(self, melee_id: str) -> bool:
        if melee_id in self.melee_inventory:
            self.melee_inventory.remove(melee_id)
            return True
        return False

    # ==================== ФИЛЬТРЫ И МОДУЛИ ====================

    def add_filter(self, filter_id: str):
        self.filters.append(filter_id)

    def remove_filter(self, filter_id: str) -> bool:
        if filter_id in self.filters:
            self.filters.remove(filter_id)
            return True
        return False

    def add_module(self, module_id: str):
        if module_id not in self.modules_inventory:
            self.modules_inventory.append(module_id)

    # ==================== ЕДА (упрощено) ====================

    def add_food(self, food_id: str, count: int = 1):
        for _ in range(count):
            self.food_inventory.append(food_id)

    def remove_food(self, food_id: str, count: int = 1) -> bool:
        removed = 0
        for i in range(len(self.food_inventory) - 1, -1, -1):
            if self.food_inventory[i] == food_id and removed < count:
                del self.food_inventory[i]
                removed += 1
        return removed == count

    def get_food_count(self, food_id: str) -> int:
        return self.food_inventory.count(food_id)

    def get_max_food(self) -> int:
        return 999

    def get_hunt_chance(self) -> int:
        return 0