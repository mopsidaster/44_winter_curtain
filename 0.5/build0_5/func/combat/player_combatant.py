# -*- coding: utf-8 -*-
# func/combat/player_combatant.py - Обёртка Player для PvP-боя (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.6   — новый файл. Используется для PvP: игрок как участник боя.
#   0.4.7.2 — get_weapon_damage_with_modules в take_damage;
#             метод get_attacker_weapon_damage для атакующего.

import random
from typing import List

from ..player import Player
from ..weapon_system import (
    get_weapon,
    get_magazine,
    get_current_ammo,
    get_weapon_max_ammo,
    is_shell_loaded_weapon,
    is_heavy_mg,
    is_mg,
    is_spec_weapon,
    get_shotgun_damage_multiplier,
    is_shotgun,
    is_shotgun_far_blocked,
    get_shotgun_close_bonus,
    get_shotgun_ammo_damage_bonus,
    is_incendiary,
    get_bleeding_config,
    is_bleeding_ammo,
    get_weapon_damage_with_modules,
)
from ..armor_system import apply_armor_protection, apply_armor_after_hit, is_zone_covered
from ..melee_system import (
    get_melee_weapon,
    can_cause_bleeding,
    get_melee_bleeding_chances,
)
from utils.logger import get_logger

logger = get_logger()


class PlayerCombatant:
    """
    Обёртка над Player для PvP-боя.

    Задача — предоставить тот же интерфейс, что и Combatant
    (get_available_parts, take_damage, can_attack, get_accuracy_modifier
    и т.д.), но с реальными характеристиками игрока.
    """

    def __init__(self, player: Player):
        self.player = player
        self.user_id = player.user_id

        # Основные поля
        self.display_name = player.name
        self.emoji = "👤"
        self.is_player = True
        self.is_mutant = False
        self.is_human = True
        self.is_boss = False
        self.mutant_id = None
        self.mutant_data = {}

        # Оружие/броня игрока (ссылки на реальные данные Player)
        self.weapon = player.weapon
        self.equipped_armor_id = player.armor
        self.equipped_helmet_id = player.helmet
        self.weapon_ammo_type = None

        # Состояния боя
        self.surrendered = False
        self.spared = False
        self.is_stunned = False
        self.stun_turns = 0
        self.healed_this_turn = False

        # Совместимость с логикой Combatant
        self.burning_stacks = []
        self.medkits = []
        self.last_damage = 0

    # ==================== БАЗОВЫЕ СВОЙСТВА ====================

    @property
    def is_alive(self) -> bool:
        return self.player.is_alive

    @is_alive.setter
    def is_alive(self, value: bool):
        self.player.is_alive = value

    @property
    def lives(self) -> float:
        return self.player.get_total_health()

    @lives.setter
    def lives(self, value: float):
        pass

    @property
    def max_lives(self) -> float:
        return self.player.get_max_total_health()

    @max_lives.setter
    def max_lives(self, value: float):
        pass

    @property
    def body_parts(self) -> dict:
        return self.player.body_parts

    @body_parts.setter
    def body_parts(self, value: dict):
        self.player.body_parts = value

    @property
    def arms_destroyed(self) -> bool:
        return self.player.is_body_part_destroyed("руки")

    @property
    def legs_destroyed(self) -> bool:
        return self.player.is_body_part_destroyed("ноги")

    @property
    def head_immunity(self) -> bool:
        return False

    @property
    def armor_protection_percent(self) -> int:
        return 0

    # ==================== СОВМЕСТИМОСТЬ С Combatant ====================

    def get_available_parts(self) -> list:
        return self.player.get_alive_body_parts()

    def get_damage_multiplier(self) -> float:
        """Если руки уничтожены — урон в рукопашной ×0.5 (как у NPC-людей)."""
        if self.arms_destroyed:
            return 0.5
        return 1.0

    def get_accuracy_modifier(self) -> float:
        """Штраф к точности, если ноги уничтожены."""
        if self.legs_destroyed:
            return 0.10
        return 1.0

    def can_attack(self) -> bool:
        if not self.is_alive or self.is_stunned:
            return False
        if self.arms_destroyed:
            return False
        return True

    def can_finish(self) -> bool:
        return False

    def can_surrender(self) -> bool:
        return False

    def can_be_spared(self) -> bool:
        return False

    def can_use_medkit(self) -> bool:
        return False

    def use_medkit(self) -> dict:
        return {"success": False, "message": "Аптечки в PvP — отдельным действием"}

    # ==================== УРОН АТАКУЮЩЕГО (0.4.7.2) ====================

    def get_attacker_weapon_damage(self) -> float:
        """
        0.4.7.2: базовый урон оружия + бонус от модулей (удлинённый ствол).
        Используется в PvPCombat при стрельбе.
        """
        return get_weapon_damage_with_modules(self.player, self.player.weapon)

    # ==================== ГОРЕНИЕ ====================

    def add_burning_stack(self, turns: int = None):
        self.player.add_burning_stack(turns)

    def tick_burning(self) -> dict:
        if not getattr(self.player, 'is_burning', None):
            return {"damage": 0.0, "stacks": 0, "message": ""}
        dmg = self.player.get_burning_damage_preview()
        stacks = len(self.player.is_burning)
        new_stacks = []
        for t in self.player.is_burning:
            t -= 1
            if t > 0:
                new_stacks.append(t)
        self.player.is_burning = new_stacks
        return {
            "damage": dmg,
            "stacks": stacks,
            "message": f"🔥 **{self.display_name}** горит: {dmg:.0f} урона",
        }

    def clear_burning(self):
        self.player.clear_burning()

    def is_burning(self) -> bool:
        return bool(getattr(self.player, 'is_burning', None))

    # ==================== КРОВОТЕЧЕНИЕ ====================

    def add_bleeding(self, part_id: str, strong: bool = False):
        self.player.add_bleeding(part_id, strong)

    def tick_bleeding(self) -> dict:
        return self.player.tick_bleeding()

    def clear_bleeding(self) -> int:
        return self.player.clear_bleeding()

    def has_bleeding(self) -> bool:
        return self.player.has_bleeding()

    def get_bleeding_preview(self) -> dict:
        return self.player.get_bleeding_preview()

    # ==================== УРОН ====================

    def take_damage(
            self,
            damage: float,
            body_part: str = None,
            ammo_type: str = None,
            is_melee: bool = False,
            is_player_attacker: bool = True,
            is_incendiary_shot: bool = False,
    ) -> dict:
        """
        Нанести урон игроку-цели.
        """
        result = {
            "damage": 0.0,
            "killed": False,
            "absorbed": 0.0,
            "ricochet": False,
            "immune": False,
            "part_destroyed": None,
            "bleeding": {"applied": False},
        }

        if not self.is_alive:
            return result

        hit_part = body_part if body_part else "торс"
        if hit_part not in self.body_parts:
            hit_part = "торс" if "торс" in self.body_parts else None
        if hit_part is None:
            return result

        part_mult = self.body_parts[hit_part].get('multiplier', 1.0)

        ammo_mult = 1.0
        if not is_melee and ammo_type:
            from ..weapon_system import get_ammo_damage_multiplier
            zone_covered = is_zone_covered(self.player, hit_part)
            ammo_mult = get_ammo_damage_multiplier(ammo_type, target_has_armor=zone_covered)

        raw = damage * part_mult * ammo_mult

        armor_result = apply_armor_protection(
            self.player, hit_part, raw,
            damage_type="melee" if is_melee else "bullet",
            ammo_type=ammo_type,
            is_melee=is_melee,
        )
        final_damage = armor_result.get('final_damage', raw)
        absorbed = armor_result.get('absorbed', 0)
        ricochet = armor_result.get('ricochet', False)

        result['absorbed'] = absorbed
        result['ricochet'] = ricochet

        if ricochet:
            return result

        absorbed = armor_result.get('absorbed', 0)
        if absorbed > 0:
            apply_armor_after_hit(self.player, hit_part, absorbed)

        dmg_result = self.player.take_body_part_damage(hit_part, final_damage)
        result['damage'] = final_damage

        if dmg_result.get("destroyed", False):
            result['part_destroyed'] = hit_part

        if final_damage > 0:
            bleeding_result = self._try_apply_bleeding(
                hit_part, ammo_type, is_melee, is_player_attacker
            )
            result['bleeding'] = bleeding_result

        if is_incendiary_shot and final_damage > 0:
            self.add_burning_stack()

        if not self.player.is_alive:
            result['killed'] = True

        return result

    def _try_apply_bleeding(self, hit_part: str, ammo_type: str,
                            is_melee: bool, is_player_attacker: bool) -> dict:
        if not is_player_attacker:
            return {"applied": False}

        cfg = get_bleeding_config()
        sources = cfg.get('sources', {})

        if is_melee:
            source = sources.get('melee_sharp', {})
        elif ammo_type and is_bleeding_ammo(ammo_type):
            source = sources.get('expansive_ammo', {})
        else:
            return {"applied": False}

        if not source:
            return {"applied": False}

        from ..disease_system import get_immunity_reduction
        immunity = get_immunity_reduction(self.player)

        impact_protection = 0.0
        if is_melee:
            from ..armor_system import _get_covering_items, get_armor_item
            for item_id in _get_covering_items(self.player, hit_part):
                item = get_armor_item(item_id)
                if item:
                    impact_protection = max(
                        impact_protection, item.get('impact_protection', 0)
                    )

        modifier = (1.0 - immunity) * (1.0 - impact_protection / 100.0)
        modifier = max(0.0, modifier)

        weak_chance = float(source.get('weak_chance', 0)) * modifier
        strong_chance = float(source.get('strong_chance', 0)) * modifier

        roll = random.uniform(0, 100)
        if roll <= strong_chance:
            self.add_bleeding(hit_part, strong=True)
            return {"applied": True, "strong": True, "part": hit_part}
        elif roll <= strong_chance + weak_chance:
            self.add_bleeding(hit_part, strong=False)
            return {"applied": True, "strong": False, "part": hit_part}

        return {"applied": False}