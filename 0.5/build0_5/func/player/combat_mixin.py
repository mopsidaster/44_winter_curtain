# -*- coding: utf-8 -*-
# func/player/combat_mixin.py - Ближний бой, модули, точность (0.4.8.8)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено из player.py
#   0.4.5   — штрафы от простуды и заражения крови
#   0.4.8.8 — get_headshot_accuracy учитывает бонус от прицелов
#             (headshot_accuracy в modules.json). Потолок 90%.

from config.map_config import BALANCE, HEALTH, MODULES

from utils.logger import get_logger

logger = get_logger()


class CombatMixin:
    """Ближний бой, блок, модули оружия, точность стрельбы."""

    # ==================== ШТРАФЫ ОТ БОЛЕЗНЕЙ ====================

    def _get_disease_melee_penalty(self) -> float:
        penalty_percent = 0.0

        if 'простуда' in self.diseases:
            penalty_percent += 25.0

        if 'заражение_крови' in self.diseases:
            soft_left = getattr(self, 'blood_infection_soft_transitions', 0)
            if soft_left > 0:
                penalty_percent += 15.0
            else:
                penalty_percent += 35.0

        return max(0.0, 1.0 - penalty_percent / 100.0)

    def _get_disease_accuracy_penalty(self) -> float:
        penalty_percent = 0.0

        if 'простуда' in self.diseases:
            penalty_percent += 15.0

        if 'заражение_крови' in self.diseases:
            soft_left = getattr(self, 'blood_infection_soft_transitions', 0)
            if soft_left > 0:
                penalty_percent += 5.0
            else:
                penalty_percent += 25.0

        return max(0.0, 1.0 - penalty_percent / 100.0)

    # ==================== ОРУЖИЕ БЛИЖНЕГО БОЯ ====================

    def get_melee_weapon_data(self) -> dict:
        from ..melee_system import get_melee_weapon
        return get_melee_weapon(self.melee_weapon)

    def get_melee_damage(self) -> float:
        from ..melee_system import get_melee_weapon as gmw
        weapon_data = self.get_melee_weapon_data()
        if not weapon_data:
            return 0.0
        if self.melee_weapon_durability <= 0 and not weapon_data.get('indestructible', False):
            logger.warning(
                f"{self.name}: оружие ближнего боя '{self.melee_weapon}' сломано — "
                f"переход на кулаки"
            )
            self.melee_weapon = "кулаки"
            self.melee_weapon_durability = 999
            weapon_data = gmw("кулаки")

        base_damage = weapon_data.get('damage', 1.0)
        strength = self.skills.get("сила", 0)
        strength_bonus = BALANCE['skills'].get('strength_melee_damage_percent', 1) / 100.0

        raw = base_damage * (1.0 + strength * strength_bonus)
        return raw * self._get_disease_melee_penalty()

    def use_melee_weapon(self) -> bool:
        weapon_data = self.get_melee_weapon_data()
        if not weapon_data:
            return False
        if weapon_data.get('indestructible', False):
            return True
        self.melee_weapon_durability -= 1
        if self.melee_weapon_durability <= 0:
            self.melee_weapon_durability = 0
            logger.info(f"{self.name}: '{self.melee_weapon}' сломано (прочность 0)")
            self.melee_weapon = "кулаки"
            self.melee_weapon_durability = 999
            return False
        return True

    def get_melee_weapon_durability_percent(self) -> int:
        weapon_data = self.get_melee_weapon_data()
        if not weapon_data:
            return 100
        max_durability = weapon_data.get('max_durability', 999)
        if max_durability >= 999:
            return 100
        return int((self.melee_weapon_durability / max_durability) * 100)

    def get_melee_accuracy(self) -> int:
        weapon_data = self.get_melee_weapon_data()
        if not weapon_data:
            return 70
        base_accuracy = weapon_data.get('accuracy', 70)
        strength = self.skills.get("сила", 0)
        bonus = BALANCE['skills'].get('strength_accuracy_bonus', 2)
        raw = min(base_accuracy + strength * bonus, 95)
        return int(raw * self._get_disease_accuracy_penalty())

    def get_melee_stun_chance(self, target_part: str = "голова") -> int:
        weapon_data = self.get_melee_weapon_data()
        if not weapon_data:
            return 0
        if target_part != "голова":
            return 0
        if weapon_data.get('type') != "тупое":
            return 0
        base_stun = weapon_data.get('stun_chance', 0)
        strength = self.skills.get("сила", 0)
        bonus = BALANCE['skills'].get('strength_stun_bonus', 1)
        return min(base_stun + strength * bonus, 50)

    def get_block_damage_reduction(self) -> float:
        health_config = HEALTH.get('player', {})
        base_reduction = health_config.get('block', {}).get('damage_reduction_base', 50)
        per_toughness = BALANCE['skills'].get('toughness_block_percent', 2)
        toughness = self.skills.get("стойкость", 0)
        return min(base_reduction + (toughness * per_toughness), 90)

    # ==================== МОДУЛИ ====================

    def install_module(self, module_id: str) -> tuple:
        from ..weapon_system import can_install_module, get_module_slots

        if module_id not in self.modules_inventory:
            return False, "❌ У вас нет этого модуля в инвентаре!"

        can_install, reason = can_install_module(self.weapon, module_id)
        if not can_install:
            return False, f"❌ {reason}"

        slots = get_module_slots(module_id)
        if not slots:
            return False, "❌ Не удалось определить слот модуля!"

        for slot in slots:
            old_module = self.equipped_modules.get(slot)
            if old_module and old_module != module_id:
                self.modules_inventory.append(old_module)
                self.equipped_modules[slot] = None

        primary_slot = slots[0]
        self.equipped_modules[primary_slot] = module_id

        for slot in slots[1:]:
            self.equipped_modules[slot] = module_id

        self.modules_inventory.remove(module_id)

        module_data = MODULES['modules'][module_id]
        logger.info(f"{self.name}: установлен модуль '{module_id}' в слоты {slots}")
        return True, f"✅ Установлен **{module_data['name']}**!"

    def remove_module(self, slot: str) -> tuple:
        if slot not in self.equipped_modules:
            return False, f"❌ Неизвестный слот: {slot}"

        module_id = self.equipped_modules[slot]
        if not module_id:
            return False, "❌ В этом слоте нет модуля!"

        from ..weapon_system import get_module_slots
        all_slots = get_module_slots(module_id) or [slot]

        for s in all_slots:
            if self.equipped_modules.get(s) == module_id:
                self.equipped_modules[s] = None

        if module_id not in self.modules_inventory:
            self.modules_inventory.append(module_id)

        module_data = MODULES['modules'].get(module_id, {})
        logger.info(f"{self.name}: снят модуль '{module_id}' со слотов {all_slots}")
        return True, f"✅ Снят **{module_data.get('name', module_id)}**"

    def get_equipped_modules_list(self) -> list:
        result = []
        seen = set()
        for slot, module_id in self.equipped_modules.items():
            if module_id and module_id not in seen:
                result.append((slot, module_id))
                seen.add(module_id)
        return result

    # ==================== ТОЧНОСТЬ СТРЕЛЬБЫ ====================

    def get_weapon_accuracy_at_distance(self, distance: str) -> float:
        from ..weapon_system import get_weapon_accuracy
        skill = self.skills.get("меткость", 0)
        raw = get_weapon_accuracy(self.weapon, skill, distance, self)
        return raw * self._get_disease_accuracy_penalty()

    def get_headshot_accuracy(self) -> int:
        """
        0.4.8.7: базовая точность в голову + навык меткости +
        бонус прицелов (modules.headshot_accuracy) +
        бонус оружия (weapons.headshot_accuracy_bonus — пистолеты +30%).
        Потолок 90%.
        """
        from ..weapon_system._helpers import _get_headshot_accuracy_bonus

        base = BALANCE['skills']['headshot_accuracy_base']
        per_level = BALANCE['skills'].get('accuracy_headshot_percent', 3)
        raw = base + (self.skills.get("меткость", 0) * per_level)

        raw += _get_headshot_accuracy_bonus(self)

        # 0.4.8.7: бонус оружия (пистолеты +30%)
        try:
            from ..weapon_system.weapons import get_weapon
            wdata = get_weapon(self.weapon) or {}
            raw += int(wdata.get("headshot_accuracy_bonus", 0))
        except Exception as e:
            logger.error(f"[HEADSHOT] weapon bonus: {e}")

        raw = min(raw, 90)
        return int(raw * self._get_disease_accuracy_penalty())

    def get_fall_chance_reduction(self) -> int:
        reduction = BALANCE['skills'].get('toughness_fall_reduction', 10)
        return self.skills.get("стойкость", 0) * reduction

    def get_weapon_accuracy_with_skill(self, weapon_id: str, distance: str = "close") -> float:
        from ..weapon_system import get_weapon_accuracy
        raw = get_weapon_accuracy(weapon_id, self.skills.get("меткость", 0), distance, self)
        return raw * self._get_disease_accuracy_penalty()

    def get_damage_reduction(self) -> float:
        per_level = BALANCE['skills'].get('toughness_damage_reduction_percent', 2.5)
        return self.skills.get("стойкость", 0) * (per_level / 100.0)

    def get_accuracy(self) -> int:
        base = BALANCE['skills']['accuracy_base'] + (
                self.skills.get("меткость", 0) * BALANCE['skills']['accuracy_per_level']
        )
        return int(base * self._get_disease_accuracy_penalty())