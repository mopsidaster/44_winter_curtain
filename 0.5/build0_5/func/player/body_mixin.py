# -*- coding: utf-8 -*-
# func/player/body_mixin.py - Части тела, стамина, холод, горение, MG reload, кровотечение (0.4.7.3)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено из player.py
#   0.4.5   — секция «Кровотечение»
#   0.4.7.2 — поддержка бонуса max_stamina_percent (сет Кузнеца)
#   0.4.7.3 — уточнение порядка: base + skill + flat → +percent → -penalty

import random

from config.map_config import BALANCE, HEALTH

from utils.logger import get_logger

logger = get_logger()


class BodyMixin:
    """Части тела + стамина + холод + горение + Heavy MG reload + кровотечение."""

    # ==================== ЧАСТИ ТЕЛА ====================

    def _get_health_bonus_percent(self) -> float:
        from ..armor_system import get_active_set
        active_set = get_active_set(self)
        if not active_set:
            return 0.0
        bonus = 0.0
        for b in active_set.get('bonuses', []):
            if b.get('type') == 'max_health_percent':
                bonus += float(b.get('value', 0))
        return bonus

    def _init_body_parts(self):
        body_config = HEALTH.get('player', {}).get('body_parts', {})

        base_parts = {}
        for part_id, part_data in body_config.items():
            base_parts[part_id] = {
                "hp": part_data.get('max_hp', 5),
                "max_hp": part_data.get('max_hp', 5),
                "name": part_data.get('name', part_id),
                "multiplier": part_data.get('multiplier', 1.0)
            }

        health_skill = self.skills.get("здоровье", 0)
        health_bonus_total = health_skill * BALANCE['skills'].get('health_per_level', 2)

        set_bonus_percent = self._get_health_bonus_percent()
        total_base_hp = sum(p["max_hp"] for p in base_parts.values())
        set_bonus_total = total_base_hp * (set_bonus_percent / 100.0)

        total_bonus = health_bonus_total + set_bonus_total

        if total_bonus > 0 and total_base_hp > 0:
            for part_id, part in base_parts.items():
                share = part["max_hp"] / total_base_hp
                part["max_hp"] = part["max_hp"] + total_bonus * share
                part["hp"] = part["max_hp"]

        self.body_parts = base_parts

    def recalc_body_parts_max_hp(self):
        body_config = HEALTH.get('player', {}).get('body_parts', {})

        health_skill = self.skills.get("здоровье", 0)
        health_bonus_total = health_skill * BALANCE['skills'].get('health_per_level', 2)

        base_parts = {}
        for part_id, part_data in body_config.items():
            base_parts[part_id] = {
                "base_max_hp": part_data.get('max_hp', 5),
                "name": part_data.get('name', part_id),
                "multiplier": part_data.get('multiplier', 1.0)
            }

        total_base_hp = sum(p["base_max_hp"] for p in base_parts.values())

        set_bonus_percent = self._get_health_bonus_percent()
        set_bonus_total = total_base_hp * (set_bonus_percent / 100.0)

        total_bonus = health_bonus_total + set_bonus_total

        for part_id, part in base_parts.items():
            share = part["base_max_hp"] / total_base_hp if total_base_hp > 0 else 0
            new_max_hp = part["base_max_hp"] + (total_bonus * share)

            if part_id in self.body_parts:
                old_max = self.body_parts[part_id]["max_hp"]
                diff = new_max_hp - old_max
                self.body_parts[part_id]["max_hp"] = new_max_hp
                self.body_parts[part_id]["hp"] = min(
                    new_max_hp,
                    self.body_parts[part_id]["hp"] + diff
                )
            else:
                self.body_parts[part_id] = {
                    "hp": new_max_hp,
                    "max_hp": new_max_hp,
                    "name": part["name"],
                    "multiplier": part["multiplier"]
                }

    def _recalc_body_parts_max_hp_silent(self):
        body_config = HEALTH.get('player', {}).get('body_parts', {})

        health_skill = self.skills.get("здоровье", 0)
        health_bonus_total = health_skill * BALANCE['skills'].get('health_per_level', 2)

        base_parts = {}
        for part_id, part_data in body_config.items():
            base_parts[part_id] = part_data.get('max_hp', 5)

        total_base_hp = sum(base_parts.values())

        for part_id, part in self.body_parts.items():
            base_max = base_parts.get(part_id, 5)
            share = base_max / total_base_hp if total_base_hp > 0 else 0
            new_max_hp = base_max + (health_bonus_total * share)
            part["max_hp"] = new_max_hp
            if part["hp"] > new_max_hp:
                part["hp"] = new_max_hp

    def get_body_part_hp(self, part_id: str) -> float:
        return self.body_parts.get(part_id, {}).get('hp', 0)

    def get_body_part_max_hp(self, part_id: str) -> float:
        return self.body_parts.get(part_id, {}).get('max_hp', 0)

    def get_body_part_multiplier(self, part_id: str) -> float:
        return self.body_parts.get(part_id, {}).get('multiplier', 1.0)

    def take_body_part_damage(self, part_id: str, damage: float) -> dict:
        if part_id not in self.body_parts:
            return {"damage": 0, "destroyed": False}

        part = self.body_parts[part_id]
        part["hp"] -= damage

        if part["hp"] <= 0:
            part["hp"] = 0
            if part_id in ["голова", "торс"]:
                self.is_alive = False
                logger.info(f"{self.name}: погиб от урона в '{part_id}'")
            elif part_id in ["руки", "ноги"]:
                # 0.4.8.2: Заражение крови при выбитых конечностях
                if 'заражение_крови' not in getattr(self, 'diseases', []):
                    if not hasattr(self, 'diseases'):
                        self.diseases = []
                    self.diseases.append('заражение_крови')
                    self.blood_infection_soft_transitions = 0
                    logger.info(f"{self.name}: наложено заражение крови (выбита часть тела: {part_id})")
            return {"damage": damage, "destroyed": True}

        return {"damage": damage, "destroyed": False}

    def get_total_health(self) -> float:
        return sum(p.get('hp', 0) for p in self.body_parts.values())

    def get_max_total_health(self) -> float:
        return sum(p.get('max_hp', 0) for p in self.body_parts.values())

    def heal_body_part(self, part_id: str, amount: float):
        if part_id not in self.body_parts:
            return
        part = self.body_parts[part_id]
        part["hp"] = min(part["max_hp"], part["hp"] + amount)

    def heal_all_body_parts(self, amount: float):
        for part_id in self.body_parts:
            self.heal_body_part(part_id, amount)

    def restore_full_health(self):
        for part_id, part in self.body_parts.items():
            part["hp"] = part["max_hp"]
        self.is_alive = True

    def get_body_parts_status(self) -> str:
        status = []
        for part_id, part in self.body_parts.items():
            hp = part.get('hp', 0)
            max_hp = part.get('max_hp', 0)
            name = part.get('name', part_id)
            if hp <= 0:
                status.append(f"💀 {name}")
            elif hp <= max_hp * 0.3:
                status.append(f"🟡 {name}: {hp:.1f}/{max_hp:.1f}")
            else:
                status.append(f"🟢 {name}: {hp:.1f}/{max_hp:.1f}")
        return "\n".join(status)

    def is_body_part_destroyed(self, part_id: str) -> bool:
        return self.body_parts.get(part_id, {}).get('hp', 0) <= 0

    def get_alive_body_parts(self) -> list:
        return [pid for pid, p in self.body_parts.items() if p.get('hp', 0) > 0]

    # ==================== СТАМИНА ====================

    def recalc_max_stamina(self):
        """
        0.4.7.3:
          Порядок:
            1. base + skill_bonus + flat_bonus   ← flat в единицах
            2. +percent_bonus (max_stamina_percent)
            3. -penalty_pct (stamina_penalty_percent)
        """
        from ..armor_system import get_active_set

        base = BALANCE['player'].get('base_stamina', 10.0)
        per_level = BALANCE['skills'].get('endurance_stamina_bonus', 2)
        endurance_level = self.skills.get("выносливость", 0)

        skill_bonus = endurance_level * per_level

        flat_bonus = 0.0
        percent_bonus = 0.0
        penalty_pct = 0.0
        try:
            active_set = get_active_set(self)
            if active_set:
                for bonus in active_set.get('bonuses', []):
                    btype = bonus.get('type')
                    if btype == 'max_stamina_flat':
                        flat_bonus += float(bonus.get('value', 0))
                    elif btype == 'max_stamina_percent':
                        percent_bonus += float(bonus.get('value', 0))
                    elif btype == 'stamina_penalty_percent':
                        penalty_pct += float(bonus.get('value', 0))
        except Exception as e:
            logger.error(
                f"{getattr(self, 'name', '?')}: ошибка get_active_set "
                f"в recalc_max_stamina — {e}"
            )

        raw_max = base + skill_bonus + flat_bonus

        if percent_bonus > 0:
            raw_max = raw_max * (1.0 + percent_bonus / 100.0)

        if penalty_pct > 0:
            raw_max = raw_max * (1.0 - penalty_pct / 100.0)

        self.max_stamina = max(raw_max, 1.0)

        if self.stamina > self.max_stamina:
            self.stamina = self.max_stamina

    def _recalc_max_stamina(self):
        self.recalc_max_stamina()

    def use_stamina(self, amount: float = 0.5) -> bool:
        if self.stamina >= amount:
            self.stamina -= amount
            return True
        return False

    def restore_stamina(self, amount: float):
        self.stamina = min(self.max_stamina, self.stamina + amount)

    # ==================== ХОЛОД ====================

    def get_thermal_resistance(self) -> int:
        from ..cold_system import get_thermal_resistance
        return get_thermal_resistance(self)

    def add_cold(self, amount: float) -> dict:
        from ..cold_system import add_cold
        return add_cold(self, amount)

    def reduce_cold(self, amount: float) -> dict:
        from ..cold_system import reduce_cold
        return reduce_cold(self, amount)

    def is_frozen(self) -> bool:
        return 'обморожение' in getattr(self, 'diseases', [])

    # ==================== ГОРЕНИЕ (0.4.4.6) ====================

    def add_burning_stack(self, turns: int = None):
        from ..weapon_system import get_incendiary_turns_per_stack
        if turns is None:
            turns = get_incendiary_turns_per_stack()
        if turns > 0:
            self.is_burning.append(turns)

    def tick_burning(self) -> dict:
        from ..weapon_system import get_incendiary_damage_per_tick

        if not self.is_burning:
            return {"damage": 0.0, "stacks_left": 0, "message": ""}

        dmg_per = get_incendiary_damage_per_tick()
        stacks = len(self.is_burning)
        total_damage = dmg_per * stacks

        new_stacks = []
        for t in self.is_burning:
            t -= 1
            if t > 0:
                new_stacks.append(t)
        self.is_burning = new_stacks

        return {
            "damage": total_damage,
            "stacks_left": len(self.is_burning),
            "message": f"🔥 Горение: {total_damage:.0f} урона ({stacks} стек.)",
        }

    def clear_burning(self):
        self.is_burning = []

    def get_burning_damage_preview(self) -> float:
        if not self.is_burning:
            return 0.0
        from ..weapon_system import get_incendiary_damage_per_tick
        return get_incendiary_damage_per_tick() * len(self.is_burning)

    # ==================== КРОВОТЕЧЕНИЕ (0.4.5) ====================

    def add_bleeding(self, part_id: str, strong: bool = False):
        from ..weapon_system import get_bleeding_config
        cfg = get_bleeding_config()

        turns = cfg.get('strong_turns', 4) if strong else cfg.get('weak_turns', 2)
        damage = cfg.get('damage_per_tick', 1.0)

        if turns <= 0:
            return

        self.bleeding_stacks.append({
            "part": part_id,
            "turns": int(turns),
            "damage": float(damage),
            "strong": bool(strong),
        })
        logger.info(
            f"{self.name}: наложено {'сильное' if strong else 'слабое'} "
            f"кровотечение на '{part_id}' ({turns} ходов)"
        )

    def tick_bleeding(self) -> dict:
        if not self.bleeding_stacks:
            return {"total_damage": 0.0, "damage_by_part": {}, "stacks_left": 0, "message": ""}

        damage_by_part = {}
        stacks_now = len(self.bleeding_stacks)

        for stack in self.bleeding_stacks:
            part = stack.get("part", "торс")
            dmg = float(stack.get("damage", 1.0))
            damage_by_part[part] = damage_by_part.get(part, 0.0) + dmg

        new_stacks = []
        for stack in self.bleeding_stacks:
            stack["turns"] = int(stack.get("turns", 0)) - 1
            if stack["turns"] > 0:
                new_stacks.append(stack)
        self.bleeding_stacks = new_stacks

        total = sum(damage_by_part.values())
        parts_str = ", ".join(f"{p} -{d:.0f}" for p, d in damage_by_part.items())

        return {
            "total_damage": total,
            "damage_by_part": damage_by_part,
            "stacks_left": len(self.bleeding_stacks),
            "message": f"🩸 Кровотечение: {total:.0f} урона ({parts_str})",
        }

    def clear_bleeding(self) -> int:
        count = len(self.bleeding_stacks)
        self.bleeding_stacks = []
        if count > 0:
            logger.info(f"{self.name}: снято кровотечений — {count}")
        return count

    def get_bleeding_preview(self) -> dict:
        damage_by_part = {}
        for stack in self.bleeding_stacks:
            part = stack.get("part", "торс")
            dmg = float(stack.get("damage", 1.0))
            damage_by_part[part] = damage_by_part.get(part, 0.0) + dmg
        return {
            "damage_by_part": damage_by_part,
            "total": sum(damage_by_part.values()),
            "stacks": len(self.bleeding_stacks),
        }

    def has_bleeding(self) -> bool:
        return bool(self.bleeding_stacks)

    # ==================== HEAVY MG RELOAD (0.4.4.6) ====================

    def start_mg_reload(self):
        self.mg_reload_progress = 1
        logger.debug(f"{self.name}: начало перезарядки Heavy MG")

    def advance_mg_reload(self) -> bool:
        if self.mg_reload_progress <= 0:
            return False
        self.mg_reload_progress += 1
        if self.mg_reload_progress >= 2:
            self.mg_reload_progress = 0
            logger.debug(f"{self.name}: перезарядка Heavy MG завершена")
            return True
        return False

    def is_reloading_mg(self) -> bool:
        return self.mg_reload_progress > 0

    def mg_reload_step(self) -> int:
        return self.mg_reload_progress