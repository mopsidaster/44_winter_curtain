# -*- coding: utf-8 -*-
# func/combat/combatant.py - Участник боя (0.4.7.6)
#
# ИСТОРИЯ:
#   0.4.4.7 — вынесено из combat.py
#   0.4.5   — кровотечение
#   0.4.7   — иммунитеты Мерзляков
#   0.4.7.3 — флаг knife_damage_immunity
#   0.4.7.6 — поля mutation_level, mutation_damage_bonus

import random
from typing import List

from config.map_config import BALANCE, WEAPONS, HEALTH, ITEMS
from ..weapon_system import (
    get_weapon,
    get_magazine,
    get_ammo_type,
    get_ammo_damage_multiplier,
    is_incendiary,
    get_incendiary_damage_per_tick,
    get_incendiary_turns_per_stack,
    is_bleeding_ammo,
    get_bleeding_config,
)
from ..armor_system import apply_armor_protection, is_zone_covered
from ..player import Player
from utils.logger import get_logger


logger = get_logger()


class Combatant:
    """Участник боя (мутант, человек или игрок)."""
    def __init__(self, player: Player, is_mutant: bool = False, mutant_id: str = None,
                 mutant_data: dict = None, is_human: bool = False, is_player: bool = False):
        if mutant_data is not None and not isinstance(mutant_data, dict):
            logger.warning(f"mutant_data для {mutant_id} имеет тип {type(mutant_data)} — обнуляем")
            mutant_data = {}

        self.player = player
        self.is_mutant = is_mutant
        self.is_human = is_human
        self.is_player = is_player
        self.mutant_id = mutant_id
        self.mutant_data = mutant_data
        self.is_alive = True
        # 0.4.8: фракция NPC
        self.faction_id = (mutant_data or {}).get('faction_id', '') if isinstance(mutant_data, dict) else ''

        self.weapon = None
        self.equipped_magazine = None
        self.ammo_inventory = {}
        self.weapon_ammo_type = None
        self.weapon_modules = {}

        self.equipped_armor_id = None
        self.equipped_helmet_id = None

        self.burning_stacks: List[int] = []
        self.medkits: List[str] = []
        self.max_lives = 0.0
        self.healed_this_turn = False

        self.bleeding_stacks: List[dict] = []

        # 0.4.7.6: Уровень Мутации
        self.mutation_level: int = 0
        self.mutation_damage_bonus: float = 0.0

        if is_player:
            self.lives = player.get_total_health()
            self.armor = player.armor
            self.has_armor = self.armor is not None
            self.display_name = player.name
            self.emoji = "👤"
            self.body_parts = self._init_player_body_parts(player)
            self.max_lives = player.get_max_total_health()
        elif is_mutant and mutant_data:
            self.lives = mutant_data.get('base_health', 6.0)
            self.armor = 0
            self.has_armor = False
            self.display_name = mutant_data.get('name', mutant_id)
            self.emoji = mutant_data.get('emoji', '🧟')
            self.body_parts = self._init_mutant_body_parts(mutant_data)
            self.max_lives = self.lives
        elif is_human and mutant_data:
            self.lives = mutant_data.get('base_health', 30.0)
            self.armor = 0
            self.has_armor = False
            self.display_name = mutant_data.get('name', mutant_id)
            self.emoji = mutant_data.get('emoji', '🔫')
            self.body_parts = self._init_human_body_parts(mutant_data)

            self._setup_npc_armor(mutant_data)
            self._setup_npc_weapon(mutant_data)
            self._setup_npc_medkits(mutant_data)

            self.max_lives = self.lives
        else:
            self.lives = 10.0
            self.armor = 0
            self.has_armor = False
            self.display_name = "Враг"
            self.emoji = "❓"
            self.body_parts = {}
            self.max_lives = self.lives

        self.last_damage = 0
        self.arms_destroyed = False
        self.legs_destroyed = False
        self.is_stunned = False
        self.stun_turns = 0

        self.surrendered = False
        self.spared = False

        self.armor_protection_percent = (mutant_data or {}).get('armor_protection', 0)
        self.head_immunity = (mutant_data or {}).get('head_immunity', False)
        self.is_boss = (mutant_data or {}).get('is_boss', False)

        self.pistol_immunity = (mutant_data or {}).get('pistol_immunity', False)
        self.melee_immunity = (mutant_data or {}).get('melee_immunity', False)
        self.knife_head_kill_chance = (mutant_data or {}).get('knife_head_kill_chance', 0)
        self.knife_head_kill_skill_bonus = (mutant_data or {}).get('knife_head_kill_skill_bonus', 0)
        self.knife_accuracy_penalty = (mutant_data or {}).get('knife_accuracy_penalty', 1.0)
        self.melee_accuracy_penalty = (mutant_data or {}).get('melee_accuracy_penalty', 1.0)

        self.knife_damage_immunity = (mutant_data or {}).get('knife_damage_immunity', False)

        self.pack_leader_id = None

    # ==================== НАСТРОЙКА NPC ====================

    def _setup_npc_medkits(self, mutant_data: dict):
        cfg = BALANCE.get('healing', {})
        if not isinstance(cfg, dict):
            return

        name = mutant_data.get('name', '')
        if mutant_data.get('is_boss') and 'Рейдер' in name:
            self.medkits = list(cfg.get('raider_medkits', []))
            return

        if 'Бандит' in name or 'бандит' in str(mutant_data).lower():
            self.medkits = list(cfg.get('bandit_medkits', []))
            return

        npc_medkits = mutant_data.get('medkits')
        if isinstance(npc_medkits, list):
            self.medkits = list(npc_medkits)

    def _setup_npc_armor(self, mutant_data: dict):
        armor_choices = mutant_data.get('armor_choices')
        if armor_choices and isinstance(armor_choices, list):
            roll = random.randint(1, 100)
            cumulative = 0
            chosen = None
            for entry in armor_choices:
                if not isinstance(entry, dict):
                    continue
                cumulative += entry.get('chance', 0)
                if roll <= cumulative:
                    chosen = entry
                    break

            if chosen is None:
                for e in reversed(armor_choices):
                    if isinstance(e, dict):
                        chosen = e
                        break

            if chosen and isinstance(chosen, dict):
                self.equipped_armor_id = chosen.get('armor')
                self.equipped_helmet_id = chosen.get('helmet')
                return

        self.equipped_armor_id = mutant_data.get('equipped_armor')
        self.equipped_helmet_id = mutant_data.get('equipped_helmet')

    def _setup_npc_weapon(self, mutant_data: dict):
        weapons = mutant_data.get('weapons', [])
        if not isinstance(weapons, list) or not weapons:
            return
        weapons = [w for w in weapons if isinstance(w, str)]
        if not weapons:
            return

        self.weapon = random.choice(weapons)
        weapon_data = get_weapon(self.weapon)
        if not isinstance(weapon_data, dict):
            return

        mags = weapon_data.get('magazines', [])
        if not isinstance(mags, list) or not mags:
            return

        self.equipped_magazine = mags[0]
        mag_data = get_magazine(self.equipped_magazine)
        if not isinstance(mag_data, dict):
            return

        caliber = mag_data.get('caliber')
        from ..weapon_system import get_caliber_ammo_types
        ammo_types = get_caliber_ammo_types(caliber)
        first_ammo = ammo_types[0] if ammo_types else "оболочечные"
        self.weapon_ammo_type = first_ammo

    def _init_mutant_body_parts(self, mutant_data: dict) -> dict:
        body_parts_config = mutant_data.get('body_parts', {})
        if not isinstance(body_parts_config, dict):
            return {}
        body_parts = {}
        for part_name, part_data in body_parts_config.items():
            if not isinstance(part_data, dict):
                continue
            body_parts[part_name] = {
                "hp": part_data.get('hp', 5),
                "max_hp": part_data.get('hp', 5),
                "multiplier": part_data.get('multiplier', 1.0)
            }
        return body_parts

    def _init_human_body_parts(self, human_data: dict) -> dict:
        return self._init_mutant_body_parts(human_data)

    def _init_player_body_parts(self, player: Player) -> dict:
        body_parts = {}
        for part_id, part_data in player.body_parts.items():
            body_parts[part_id] = {
                "hp": part_data.get('hp', 5),
                "max_hp": part_data.get('max_hp', 5),
                "multiplier": part_data.get('multiplier', 1.0),
                "name": part_data.get('name', part_id)
            }
        return body_parts

    def _npc_zone_covered(self, part: str) -> bool:
        from ..armor_system import get_armor_item
        if self.equipped_armor_id:
            a = get_armor_item(self.equipped_armor_id)
            if isinstance(a, dict) and part in a.get('zones', []):
                return True
        if self.equipped_helmet_id:
            h = get_armor_item(self.equipped_helmet_id)
            if isinstance(h, dict) and part in h.get('zones', []):
                return True
        return False

    # ==================== ГОРЕНИЕ ====================

    def add_burning_stack(self, turns: int = None):
        if turns is None:
            turns = get_incendiary_turns_per_stack()
        if turns > 0:
            self.burning_stacks.append(turns)

    def tick_burning(self) -> dict:
        if not self.burning_stacks:
            return {"damage": 0.0, "stacks": 0, "message": ""}

        dmg_per = get_incendiary_damage_per_tick()
        stacks_now = len(self.burning_stacks)
        total = dmg_per * stacks_now

        new_stacks = []
        for t in self.burning_stacks:
            t -= 1
            if t > 0:
                new_stacks.append(t)
        self.burning_stacks = new_stacks

        return {
            "damage": total,
            "stacks": stacks_now,
            "message": f"🔥 **{self.display_name}** горит: {total:.0f} урона ({stacks_now} стек.)",
        }

    def clear_burning(self):
        self.burning_stacks = []

    def is_burning(self) -> bool:
        return bool(self.burning_stacks)

    # ==================== КРОВОТЕЧЕНИЕ ====================

    def add_bleeding(self, part_id: str, strong: bool = False):
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
            "message": f"🩸 **{self.display_name}** кровотечение: {total:.0f} урона ({parts_str})",
        }

    def clear_bleeding(self) -> int:
        count = len(self.bleeding_stacks)
        self.bleeding_stacks = []
        return count

    def has_bleeding(self) -> bool:
        return bool(self.bleeding_stacks)

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

    # ==================== МЕДИКАМЕНТЫ ====================

    def can_use_medkit(self) -> bool:
        if not self.medkits:
            return False
        if self.healed_this_turn:
            return False
        if self.lives <= 0:
            return False
        return True

    def use_medkit(self) -> dict:
        if not self.can_use_medkit():
            return {"success": False, "message": "Нет медикаментов или уже использовано"}

        cfg = BALANCE.get('healing', {})
        threshold = cfg.get('enemy_use_threshold', 0.5)
        if self.max_lives > 0 and (self.lives / self.max_lives) >= threshold:
            return {"success": False, "message": "HP выше порога"}

        medkit_id = self.medkits.pop(0)

        from ..pharmacy_system import get_shop_item
        medkit = get_shop_item(medkit_id)
        heal_amount = medkit.get('heal', 5) if medkit else 5

        body_config = HEALTH.get('player', {}).get('body_parts', {})
        total_max = sum(p.get('max_hp', 5) for p in body_config.values())

        healed_total = 0.0
        for part_id, part in self.body_parts.items():
            if part.get('hp', 0) <= 0 and part_id in ('голова', 'торс'):
                continue
            share = part.get('max_hp', 5) / total_max if total_max > 0 else 0
            heal_part = heal_amount * share
            before = part.get('hp', 0)
            part['hp'] = min(part.get('max_hp', 5), before + heal_part)
            healed_total += (part['hp'] - before)

        self.lives = sum(p.get('hp', 0) for p in self.body_parts.values())
        self.healed_this_turn = True

        bleeding_removed = self.clear_bleeding()

        msg = f"💊 **{self.display_name}** использовал аптечку (+{healed_total:.1f} HP)"
        if bleeding_removed > 0:
            msg += f", остановил кровотечение ({bleeding_removed})"

        return {
            "success": True,
            "medkit_id": medkit_id,
            "healed": healed_total,
            "bleeding_removed": bleeding_removed,
            "message": msg,
        }

    # ==================== DAMAGE ====================

    def take_damage(self, damage: float, body_part: str = None, ammo_type: str = None,
                    is_melee: bool = False, is_player_attacker: bool = False,
                    is_incendiary_shot: bool = False) -> dict:
        if not self.is_alive:
            return {"damage": 0, "killed": False, "absorbed": 0, "ricochet": False}

        if body_part == "голова" and self.head_immunity:
            return {
                "damage": 0, "killed": False, "absorbed": damage, "ricochet": False,
                "immune": True,
                "message": "🦴 Голова покрыта хитином — урон не прошёл!",
            }

        part_multiplier = 1.0
        if body_part and body_part in self.body_parts:
            part_multiplier = self.body_parts[body_part].get('multiplier', 1.0)

        ammo_multiplier = 1.0
        if not is_melee and ammo_type:
            zone_covered = False
            if self.is_player:
                zone_covered = is_zone_covered(self.player, body_part or "торс")
            else:
                if self.equipped_armor_id or self.equipped_helmet_id:
                    zone_covered = self._npc_zone_covered(body_part or "торс")
                elif self.armor_protection_percent > 0:
                    zone_covered = True

            ammo_multiplier = get_ammo_damage_multiplier(ammo_type, target_has_armor=zone_covered)

        raw = damage * part_multiplier * ammo_multiplier

        absorbed_total = 0.0
        ricochet = False
        armor_msg = ""

        if self.armor_protection_percent > 0:
            reduction = min(self.armor_protection_percent, 100) / 100.0
            after = raw * (1.0 - reduction)
            absorbed_total += raw - after
            raw = after

        if is_player_attacker and (self.equipped_armor_id or self.equipped_helmet_id):
            proxy = _NpcArmorProxy(self.equipped_armor_id, self.equipped_helmet_id)
            result = apply_armor_protection(
                proxy, body_part or "торс", raw,
                damage_type="bullet" if not is_melee else "melee",
                ammo_type=ammo_type,
                is_melee=is_melee,
                       )
            raw = result.get('final_damage', raw)
            absorbed_total += result.get('absorbed', 0)
            ricochet = result.get('ricochet', False)
            armor_msg = result.get('message', '')

        final_damage = max(raw, 0.0)

        if ricochet:
            return {"damage": 0, "killed": False, "absorbed": absorbed_total,
                    "ricochet": True, "message": armor_msg}

        if is_incendiary_shot and final_damage > 0:
            self.add_burning_stack()

        if final_damage <= 0:
            return {"damage": 0, "killed": False, "absorbed": absorbed_total,
                    "ricochet": False, "message": armor_msg}

        hit_part = body_part if (body_part and body_part in self.body_parts) else (
            "торс" if "торс" in self.body_parts else None
        )

        if hit_part is None:
            self.is_alive = False
            self.spared = False
            return {"damage": final_damage, "killed": True, "absorbed": absorbed_total,
                    "ricochet": False}

        part = self.body_parts[hit_part]
        part["hp"] -= final_damage
        self.lives -= final_damage

        bleeding_result = self._try_apply_bleeding_on_hit(
            hit_part, ammo_type, is_melee, is_player_attacker
        )

        if part["hp"] <= 0:
            part["hp"] = 0
            if hit_part in ("голова", "торс"):
                self.is_alive = False
                self.lives = 0
                self.spared = False
                return {"damage": final_damage, "killed": True, "part_destroyed": hit_part,
                        "absorbed": absorbed_total, "ricochet": False,
                        "bleeding": bleeding_result}
            if hit_part == "руки":
                self.arms_destroyed = True
            if hit_part == "ноги":
                self.legs_destroyed = True

        if self.lives <= 0:
            self.is_alive = False
            self.spared = False
            return {"damage": final_damage, "killed": True, "absorbed": absorbed_total,
                    "ricochet": False, "bleeding": bleeding_result}

        return {"damage": final_damage, "killed": False, "absorbed": absorbed_total,
                "ricochet": False, "bleeding": bleeding_result}

    def _try_apply_bleeding_on_hit(self, hit_part: str, ammo_type: str,
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

        immunity = 0.0
        if self.is_player:
            from ..disease_system import get_immunity_reduction
            immunity = get_immunity_reduction(self.player)

        impact_protection = 0.0
        if is_melee:
            if self.is_player:
                from ..armor_system import _get_covering_items, get_armor_item
                covering = _get_covering_items(self.player, hit_part)
                for item_id in covering:
                    item = get_armor_item(item_id)
                    if item:
                        impact_protection = max(impact_protection,
                                                item.get('impact_protection', 0))
            else:
                from ..armor_system import get_armor_item
                if self.equipped_armor_id:
                    a = get_armor_item(self.equipped_armor_id)
                    if isinstance(a, dict) and hit_part in a.get('zones', []):
                        impact_protection = max(impact_protection,
                                                a.get('impact_protection', 0))
                if self.equipped_helmet_id:
                    h = get_armor_item(self.equipped_helmet_id)
                    if isinstance(h, dict) and hit_part in h.get('zones', []):
                        impact_protection = max(impact_protection,
                                                h.get('impact_protection', 0))

        modifier = (1.0 - immunity) * (1.0 - impact_protection / 100.0)
        modifier = max(0.0, modifier)

        weak_chance = float(source.get('weak_chance', 0)) * modifier
        strong_chance = float(source.get('strong_chance', 0)) * modifier

        roll = random.uniform(0, 100)

        if roll <= strong_chance:
            self.add_bleeding(hit_part, strong=True)
            return {"applied": True, "strong": True, "part": hit_part,
                    "chance": strong_chance}
        elif roll <= strong_chance + weak_chance:
            self.add_bleeding(hit_part, strong=False)
            return {"applied": True, "strong": False, "part": hit_part,
                    "chance": weak_chance}

        return {"applied": False}

    # ==================== ПРОЧЕЕ ====================

    def get_available_parts(self) -> list:
        return [pid for pid, pd in self.body_parts.items() if pd.get("hp", 0) > 0]

    def can_finish(self) -> bool:
        if not self.is_mutant:
            return False
        return self.legs_destroyed and self.is_alive

    def can_surrender(self) -> bool:
        if not self.is_human:
            return False
        if self.is_boss:
            return False
        return self.legs_destroyed and self.is_alive and not self.surrendered and not self.spared

    def can_be_spared(self) -> bool:
        if not self.is_human:
            return False
        if self.is_boss:
            return False
        return self.surrendered and self.is_alive and not self.spared

    def get_damage_multiplier(self) -> float:
        if self.arms_destroyed:
            return 0.5
        return 1.0

    def can_attack(self) -> bool:
        if not self.is_alive or self.is_stunned:
            return False
        if self.is_human and self.arms_destroyed:
            return False
        return True

    def get_accuracy_modifier(self) -> float:
        if self.is_human and self.legs_destroyed:
            human_config = BALANCE.get('human_combat', {})
            min_acc = human_config.get('legs_destroyed_min_accuracy', 10)
            return min_acc / 100.0
        return 1.0


class _NpcArmorProxy:
    def __init__(self, armor_id: str, helmet_id: str):
        self.armor = armor_id
        self.helmet = helmet_id
        self.armor_durability = {"armor": 100.0, "helmet": 100.0}