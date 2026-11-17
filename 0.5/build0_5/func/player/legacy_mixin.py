# -*- coding: utf-8 -*-
# func/player/legacy_mixin.py - Опыт, статус (0.4.8 Оптимизация)
#
# Удалены устаревшие методы take_damage и get_hunt_chance.

import random
from config.map_config import WEAPONS, MAGAZINES, BALANCE
from utils.calculations import calculate_xp_to_level
from ..map_data import MAP_DATA
from utils.logger import get_logger

logger = get_logger()

MAX_CHARACTER_LEVEL = 50

class LegacyMixin:
    """Опыт, статус игрока."""

    def add_xp(self, amount: int, is_surface: bool = False) -> bool:
        if amount is None:
            amount = 0

        if is_surface:
            surface_mult = float(BALANCE.get('xp_on_surface_multiplier', 1.5))
            amount = int(amount * surface_mult)

        self.xp += amount
        leveled_up = False

        while self.xp >= self.xp_to_next and self.level < MAX_CHARACTER_LEVEL:
            self.level += 1
            self.xp -= self.xp_to_next
            self.xp_to_next = calculate_xp_to_level(self.level)
            self.skill_points += 1
            leveled_up = True
            self.recalc_body_parts_max_hp()
            self.recalc_max_stamina()
            self.restore_full_health()
            self.stamina = self.max_stamina
            logger.info(
                f"{self.name}: новый уровень {self.level} "
                f"(xp={self.xp}/{self.xp_to_next}, skill_points={self.skill_points})"
            )

        return leveled_up

    def add_debuff(self, debuff: str, duration: int = 3):
        self.debuffs.append({"name": debuff, "duration": duration})

    def add_buff(self, buff: str, duration: int = 3):
        self.buffs.append({"name": buff, "duration": duration})

    def update_effects(self):
        for debuff in self.debuffs[:]:
            debuff["duration"] -= 1
            if debuff["duration"] <= 0:
                self.debuffs.remove(debuff)
        for buff in self.buffs[:]:
            buff["duration"] -= 1
            if buff["duration"] <= 0:
                self.buffs.remove(buff)

    def get_status(self) -> dict:
        mask_status = {
            "целый": "🟢 Целый",
            "поношенный": "🟡 Поношенный",
            "разбитый": "🔴 Разбитый"
        }

        melee_data = self.get_melee_weapon_data()
        melee_name = melee_data.get('name', 'Кулаки') if melee_data else 'Кулаки'
        melee_emoji = melee_data.get('emoji', '👊') if melee_data else '👊'
        melee_durability = self.get_melee_weapon_durability_percent()

        equipped_obj = self.get_equipped_magazine_obj()
        if equipped_obj:
            current_mag = MAGAZINES.get(equipped_obj["type_id"])
            current_ammo = sum(equipped_obj["ammo"].values())
            mag_name = current_mag.get('name', 'Нет') if current_mag else 'Нет'
            mag_capacity = current_mag.get('capacity', 0) if current_mag else 0
        else:
            mag_name = 'Нет'
            mag_capacity = 0
            current_ammo = 0

        armor_name = "Нет"
        if self.armor:
            from ..armor_system import get_armor_item
            armor_data = get_armor_item(self.armor)
            armor_name = armor_data.get('name', self.armor)

        helmet_name = "Нет"
        if self.helmet:
            from ..armor_system import get_armor_item
            helmet_data = get_armor_item(self.helmet)
            helmet_name = helmet_data.get('name', self.helmet)

        bleeding_stacks = getattr(self, 'bleeding_stacks', [])
        bleeding_info = []
        for stack in bleeding_stacks:
            part = stack.get('part', '?')
            turns = stack.get('turns', 0)
            strong = stack.get('strong', False)
            label = "сильное" if strong else "слабое"
            bleeding_info.append(f"{part} ({label}, {turns} х.)")

        return {
            "имя": self.name,
            "уровень": self.level,
            "макс_уровень": MAX_CHARACTER_LEVEL,
            "опыт": f"{self.xp}/{self.xp_to_next}",
            "жизни": self.get_total_health(),
            "макс_жизни": self.get_max_total_health(),
            "выносливость": f"{self.stamina:.1f}/{self.max_stamina}",
            "еда": len(self.food_inventory),
            "локация": MAP_DATA["станции"][self.location]["name"],
            "оружие": WEAPONS[self.weapon]["name"] if self.weapon in WEAPONS else "Нет",
            "патроны": self.inventory.get("патроны", 0),
            "никели": self.inventory.get("никели", 0),
            "сила": self.skills.get("сила", 0),
            "выносливость_навык": self.skills.get("выносливость", 0),
            "стойкость": self.skills.get("стойкость", 0),
            "меткость": self.skills.get("меткость", 0),
            "здоровье": self.skills.get("здоровье", 0),
            "инженерия": self.skills.get("инженерия", 0),
            "дебаффы": [d["name"] for d in self.debuffs],
            "баффы": [b["name"] for b in self.buffs],
            "аптечки": self.inventory.get("аптечка_аи2", 0),
            "подсумки": self.inventory.get("мед_подсумок", 0),
            "антирад": self.inventory.get("антирад", 0),
            "противогаз": mask_status.get(self.gas_mask.get("состояние", "поношенный"), "❓ Неизвестно"),
            "прочность_маски": self.gas_mask.get("прочность", 0),
            "фильтры": len(self.filters),
            "надет_ли": "✅ Надет" if self.gas_mask.get("надет", False) else "❌ Снят",
            "предыстория": self.backstory,
            "магазинов": len(self.magazines),
            "еды_в_инвентаре": len(self.food_inventory),
            "защита_станции": self.station_defense,
            "текущий_магазин": mag_name,
            "патронов_в_магазине": f"{current_ammo}/{mag_capacity}",
            "оружие_ближнего_боя": f"{melee_emoji} {melee_name} ({melee_durability}%)",
            "части_тела": self.get_body_parts_status(),
            "модули": self.get_equipped_modules_list(),
            "модули_в_инвентаре": len(self.modules_inventory),
            "оружие_в_инвентаре": len(self.weapons_inventory),
            "ближний_бой_в_инвентаре": len(self.melee_inventory),
            "броня": armor_name,
            "шлем": helmet_name,
            "радиация": self.radiation,
            "химия": self.chemical,
            "болезни": self.diseases,
            "холод": self.cold,
            "термостойкость": self.get_thermal_resistance(),
            "патронов_в_стволе": self.get_shell_ammo_count(),
            "гранаты": self.get_grenades_total(),
            "ножи": self.get_knives_total(),
            "горит": len(self.is_burning) > 0,
            "стеков_горения": len(self.is_burning),
            "кровотечение": bleeding_info,
            "стеков_кровотечения": len(bleeding_stacks),
        }

    def get_engineering_level(self) -> int:
        try:
            return int(self.skills.get("инженерия", 0))
        except (TypeError, ValueError):
            return 0

    def get_repair_success_chance(self) -> int:
        from ..repair_system import get_repair_success_chance
        return get_repair_success_chance(self)