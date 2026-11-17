# -*- coding: utf-8 -*-
# func/combat/combat.py - Логика боя (0.4.9.0 Visual)
#
# ИСТОРИЯ:
#   ...
#   0.4.8.9 — ФИКС: замена {player_name} в текстах атак мутантов
#   0.4.9.0 — ВИЗУАЛ: добавлены иконки к урону и разделители в логах

import random
import discord
from typing import List, Tuple

from config.map_config import BALANCE, WEAPONS, HEALTH, ITEMS
from ..weapon_system import (
    get_weapon,
    get_magazine,
    get_ammo_type,
    get_current_ammo,
    get_weapon_max_ammo,
    get_ammo_damage_multiplier,
    get_weapon_type,
    is_spec_weapon,
    is_shotgun,
    is_shell_loaded_weapon,
    is_incendiary,
    get_incendiary_turns_per_stack,
    get_shots_per_action,
    is_shotgun_far_blocked,
    get_shotgun_damage_multiplier,
    get_shotgun_close_bonus,
    get_shotgun_ammo_damage_bonus,
    is_heavy_mg,
    is_mg,
    is_bleeding_ammo,
    get_bleeding_config,
    get_caliber_ammo_types,
    is_pistol_caliber,
    get_weapon_damage_with_modules,
    get_weapon_double_shot_config,
    is_sniper,
    is_semi_auto_sniper,
    get_sniper_subtype_config,
)
from ..melee_system import get_melee_weapon, can_cause_bleeding, get_melee_bleeding_chances
from ..player import Player
from ..armor_system import apply_armor_protection, apply_armor_after_hit, is_zone_covered
from ..cold_system import apply_frostbite_damage
from utils.logger import get_logger

from .constants import DISTANCES, DISTANCE_NAMES, MAX_COMBAT_LOG
from .combatant import Combatant, _NpcArmorProxy
from .helpers import get_mutant_data

from ..spec_weapons.grenades import throw_grenade
from ..spec_weapons.throwing_knives import throw_knife

from ..spec_weapons.raider import (
    get_raider_hit_chance,
    get_raider_damage,
)

logger = get_logger()


class Combat:
    def __init__(self, player: Player, enemies: List[Combatant], danger_level: int,
                 mutant_ids: List[str] = None):
        self.player = player
        self.extra_players: List[Player] = []
        self.enemies = enemies or []
        self.danger_level = danger_level
        self.mutant_ids = mutant_ids or []

        self.target_index = 0

        self.is_active = True
        self.log = []
        self.message = None
        self.channel = None
        self.waiting_for_enemy = False
        self.last_player_action = None
        self.turn = 0
        self.shots_this_turn = 0
        self.max_shots_per_turn = 1
        self.distance = random.choice(DISTANCES)

        self._grenade_mode = 'single'
        self._primary_part = None

        self.turn_queue: List[int] = []
        self.current_actor_user_id: int = player.user_id
        self.round_start_user_id: int = player.user_id

        player.combat_mode = True
        player.combat_target = id(self)

    # ==================== ГРУППА ====================

    def get_all_players(self) -> List[Player]:
        return [self.player] + self.extra_players

    def _build_turn_order(self) -> List[int]:
        return [p.user_id for p in self.get_all_players() if p.is_alive]

    def _ensure_turn_order(self):
        current_alive = {p.user_id for p in self.get_all_players() if p.is_alive}
        self.turn_queue = [uid for uid in self.turn_queue if uid in current_alive]
        for uid in current_alive:
            if uid not in self.turn_queue:
                self.turn_queue.append(uid)

    def get_current_actor(self) -> Player:
        self._ensure_turn_order()
        players = self.get_all_players()
        by_id = {p.user_id: p for p in players}

        if not self.turn_queue:
            return self.player

        if self.current_actor_user_id not in self.turn_queue:
            self.current_actor_user_id = self.turn_queue[0]

        actor = by_id.get(self.current_actor_user_id)
        if actor and actor.is_alive:
            return actor

        if self._advance_to_next_alive():
            actor = by_id.get(self.current_actor_user_id)
            if actor:
                return actor

        return self.player

    def _advance_to_next_alive(self) -> bool:
        self._ensure_turn_order()
        if not self.turn_queue:
            return False

        try:
            pos = self.turn_queue.index(self.current_actor_user_id)
        except ValueError:
            pos = -1

        players = self.get_all_players()
        by_id = {p.user_id: p for p in players}

        n = len(self.turn_queue)
        for offset in range(1, n + 1):
            idx = (pos + offset) % n
            uid = self.turn_queue[idx]
            actor = by_id.get(uid)
            if actor and actor.is_alive:
                self.current_actor_user_id = uid
                return True
        return False

    def is_current_actor(self, user_id: int) -> bool:
        current = self.get_current_actor()
        return current.user_id == user_id

    def advance_actor(self) -> bool:
        self._ensure_turn_order()
        if not self.turn_queue:
            return True

        players = self.get_all_players()
        by_id = {p.user_id: p for p in players}

        try:
            pos = self.turn_queue.index(self.current_actor_user_id)
        except ValueError:
            pos = -1

        n = len(self.turn_queue)

        for offset in range(1, n + 1):
            idx = (pos + offset) % n
            uid = self.turn_queue[idx]
            actor = by_id.get(uid)
            if not actor or not actor.is_alive:
                continue

            if uid == self.round_start_user_id:
                self.current_actor_user_id = uid
                return True

            self.current_actor_user_id = uid
            return False

        return True

    # ==================== СВОЙСТВА ====================

    @property
    def active_player(self) -> Player:
        try:
            return self.get_current_actor()
        except Exception:
            return self.player

    @property
    def enemy(self) -> Combatant:
        if not self.enemies:
            return None
        if self.target_index >= len(self.enemies):
            self.target_index = 0
        return self.enemies[self.target_index]

    @property
    def mutant_id(self) -> str:
        if self.mutant_ids and self.target_index < len(self.mutant_ids):
            return self.mutant_ids[self.target_index]
        return None

    def get_alive_enemies(self) -> List[Combatant]:
        return [e for e in self.enemies if e.is_alive]

    def all_enemies_dead(self) -> bool:
        return not any(e.is_alive for e in self.enemies)

    def _flee_pack_if_leader_dies(self, leader: Combatant) -> bool:
        logger.info(
            f"[COMBAT] _flee check: id={leader.mutant_id}, "
            f"is_boss={leader.is_boss}, is_alive={leader.is_alive}"
        )

        if not leader.is_boss or leader.mutant_id != 'мерзляк_вождь':
            return False

        fled = False
        for enemy in self.enemies:
            if enemy is leader:
                continue
            if not enemy.is_alive:
                continue
            if enemy.mutant_id in ('мерзляк', 'мерзляк_охотник'):
                enemy.is_alive = False
                enemy.lives = 0
                fled = True

        if fled:
            self.is_active = False
            for p in self.get_all_players():
                p.combat_mode = False
            logger.info(
                f"[COMBAT] Вождь мёртв — стая Мерзляков разбежалась "
                f"({len([e for e in self.enemies if not e.is_alive])} врагов)"
            )

        return fled

    def change_target(self, index: int) -> dict:
        if index < 0 or index >= len(self.enemies):
            return {"success": False, "message": "❌ Неверный индекс цели!"}
        if not self.enemies[index].is_alive:
            return {"success": False, "message": "❌ Эта цель уже мертва!"}
        if index == self.target_index:
            return {"success": False, "message": "❌ Вы уже выбрали эту цель!"}

        old_name = self.enemy.display_name if self.enemy else "?"
        self.target_index = index
        new_name = self.enemies[index].display_name
        return {"success": True, "message": f"🎯 Цель изменена: **{old_name}** → **{new_name}**"}

    def add_log(self, text: str):
        if not text:
            return
        self.log.append(text)
        if len(self.log) > MAX_COMBAT_LOG:
            self.log = self.log[-MAX_COMBAT_LOG:]

    def can_act(self) -> bool:
        if not self.is_active:
            return False
        if self.waiting_for_enemy:
            return False
        return True

    def can_act_for(self, user_id: int) -> bool:
        if not self.can_act():
            return False
        return self.is_current_actor(user_id)

    def can_shoot_again(self) -> bool:
        return self.shots_this_turn < self.max_shots_per_turn

    def can_shoot_now(self) -> bool:
        actor = self.active_player
        if is_heavy_mg(actor.weapon) and actor.mg_reload_progress == 2:
            return False
        return True

    def get_target_parts(self) -> list:
        if not self.enemy:
            return ["голова", "торс", "руки", "ноги"]
        return self.enemy.get_available_parts()

    def get_distance_name(self) -> str:
        return DISTANCE_NAMES.get(self.distance, self.distance)

    def _end_player_turn(self):
        if self.extra_players:
            all_done = self.advance_actor()
            if not all_done:
                self.shots_this_turn = 0
                self.last_player_action = None
                return

        self.waiting_for_enemy = True
        self.turn += 1

    def change_distance(self, new_distance: str, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}
        if new_distance not in DISTANCES:
            return {"success": False, "message": "❌ Неизвестная дистанция!"}
        if new_distance == self.distance:
            return {"success": False, "message": f"❌ Вы уже на дистанции «{self.get_distance_name()}»!"}

        old_distance = self.get_distance_name()
        self.distance = new_distance

        actor = self.active_player
        attack_chance = BALANCE['combat'].get('distance_change_enemy_attack_chance', 35)
        message = f"🏃 **{actor.name}** переместился с «{old_distance}» на «{self.get_distance_name()}»!"

        if random.randint(1, 100) <= attack_chance:
            alive = [e for e in self.enemies if e.is_alive and e.can_attack()]
            if alive:
                attacker = random.choice(alive)
                enemy_result = self._enemy_attack(attacker, target_player=actor)
                if enemy_result.get('killed'):
                    self._end_player_turn()
                    return {"success": True, "killed": True, "turn_ended": True,
                            "message": message + f"\n{enemy_result['message']}"}
                message += f"\n{enemy_result['message']}"

        self._end_player_turn()
        return {"success": True, "killed": False, "turn_ended": True, "message": message}

    # ==================== АТАКА ВРАГА ====================

    def _enemy_attack(self, enemy: Combatant, target_player: Player = None) -> dict:
        if target_player is None:
            target_player = self.player

        if not enemy.can_attack():
            return {"killed": False, "message": f"💫 {enemy.display_name} не может атаковать!"}

        action = self.get_enemy_action(enemy)
        enemy_is_melee = enemy.is_mutant

        roll = random.randint(1, 100)
        if roll <= action["hit_chance"]:
            final_damage = action["damage"]

            armor_result = apply_armor_protection(
                target_player, action["part"], final_damage,
                damage_type="melee" if enemy_is_melee else "bullet",
                ammo_type=None,
                is_melee=enemy_is_melee,
            )
            final_damage = armor_result.get('final_damage', final_damage)
            armor_msg = armor_result.get('message', '')
            ricochet = armor_result.get('ricochet', False)

            if ricochet:
                return {"killed": False,
                        "message": f"🔰 **РИКОШЕТ!** {enemy.display_name} атаковал **{target_player.name}** — броня отразила урон."}

            absorbed = armor_result.get('absorbed', 0)
            if absorbed > 0:
                apply_armor_after_hit(target_player, action["part"], absorbed)

            hit_part = action["part"]

            bleeding_msg = ""
            if enemy_is_melee and final_damage > 0:
                bleeding_result = self._try_mutant_bleeding(enemy, hit_part, target_player)
                if bleeding_result.get("applied"):
                    label = "сильное" if bleeding_result.get("strong") else "слабое"
                    bleeding_msg = f" 🩸 Наложено **{label}** кровотечение на {hit_part}!"

            damage_result = target_player.take_body_part_damage(hit_part, final_damage)

            if not target_player.is_alive:
                return {"killed": True,
                        "message": f"💀 {action['text']}! **{target_player.name}** погиб!"}

            part_destroyed = ""
            if damage_result.get("destroyed", False):
                part_names = {"голова": "Голова", "торс": "Торс", "руки": "Руки", "ноги": "Ноги"}
                part_destroyed = f" {part_names.get(hit_part, hit_part)} уничтожена!"

            armor_text = f" — {armor_msg}" if armor_msg else ""
            return {"killed": False,
                    "message": f"⚡ {action['text']} ({final_damage:.1f}) → **{target_player.name}**{part_destroyed}{armor_text}{bleeding_msg}"}

        return {"killed": False, "message": f"💨 {enemy.display_name} промахнулся!"}

    def _try_mutant_bleeding(self, enemy: Combatant, hit_part: str,
                             target_player: Player = None) -> dict:
        if not enemy.is_mutant:
            return {"applied": False}

        if target_player is None:
            target_player = self.player

        cfg = get_bleeding_config()
        source = cfg.get('sources', {}).get('mutant_claws', {})
        if not source:
            return {"applied": False}

        from ..disease_system import get_immunity_reduction
        immunity = get_immunity_reduction(target_player)

        from ..armor_system import _get_covering_items, get_armor_item
        impact_protection = 0.0
        for item_id in _get_covering_items(target_player, hit_part):
            item = get_armor_item(item_id)
            if item:
                impact_protection = max(impact_protection, item.get('impact_protection', 0))

        modifier = (1.0 - immunity) * (1.0 - impact_protection / 100.0)
        modifier = max(0.0, modifier)

        weak_chance = float(source.get('weak_chance', 0)) * modifier
        strong_chance = float(source.get('strong_chance', 0)) * modifier

        roll = random.uniform(0, 100)
        if roll <= strong_chance:
            target_player.add_bleeding(hit_part, strong=True)
            return {"applied": True, "strong": True, "part": hit_part}
        elif roll <= strong_chance + weak_chance:
            target_player.add_bleeding(hit_part, strong=False)
            return {"applied": True, "strong": False, "part": hit_part}
        return {"applied": False}

    def _try_player_melee_bleeding(self, hit_part: str) -> dict:
        actor = self.active_player
        source = get_melee_bleeding_chances(actor.melee_weapon)
        if not source:
            return {"applied": False}

        enemy = self.enemy
        if not enemy or not enemy.is_alive:
            return {"applied": False}

        immunity = 0.0
        impact_protection = 0.0
        if enemy.equipped_armor_id or enemy.equipped_helmet_id:
            from ..armor_system import get_armor_item
            if enemy.equipped_armor_id:
                a = get_armor_item(enemy.equipped_armor_id)
                if isinstance(a, dict) and hit_part in a.get('zones', []):
                    impact_protection = max(impact_protection, a.get('impact_protection', 0))
            if enemy.equipped_helmet_id:
                h = get_armor_item(enemy.equipped_helmet_id)
                if isinstance(h, dict) and hit_part in h.get('zones', []):
                    impact_protection = max(impact_protection, h.get('impact_protection', 0))

        modifier = (1.0 - immunity) * (1.0 - impact_protection / 100.0)
        modifier = max(0.0, modifier)

        weak_chance = float(source.get('weak_chance', 0)) * modifier
        strong_chance = float(source.get('strong_chance', 0)) * modifier

        roll = random.uniform(0, 100)
        if roll <= strong_chance:
            enemy.add_bleeding(hit_part, strong=True)
            return {"applied": True, "strong": True, "part": hit_part}
        elif roll <= strong_chance + weak_chance:
            enemy.add_bleeding(hit_part, strong=False)
            return {"applied": True, "strong": False, "part": hit_part}
        return {"applied": False}

    def _get_player_mg_penalty_bonus(self) -> int:
        mg_cfg = BALANCE.get('combat', {}).get('mg', {})
        bonus = 0
        actor = self.active_player
        if is_heavy_mg(actor.weapon):
            bonus += int(mg_cfg.get('heavy_enemy_hit_bonus', 15))
        eq = getattr(actor, 'equipped_modules', {})
        if eq.get('muzzle') == 'сошки' or eq.get('grip') == 'сошки':
            bonus += int(mg_cfg.get('soshki_enemy_hit_bonus', 15))
        return bonus

    def get_enemy_action(self, enemy: Combatant = None) -> dict:
        if enemy is None:
            enemy = self.enemy

        base_difficulty = min(self.danger_level / 5, 1.0)

        if enemy.is_boss and enemy.mutant_id == 'рейдер':
            hit_chance = get_raider_hit_chance(self.danger_level)
            base_damage = get_raider_damage(self.danger_level)
            raider_ammo_type = getattr(enemy, 'weapon_ammo_type', None)
            if raider_ammo_type:
                ammo_mult = get_ammo_damage_multiplier(raider_ammo_type, target_has_armor=False)
                base_damage *= ammo_mult
        else:
            mutant_data = enemy.mutant_data
            if isinstance(mutant_data, dict) and mutant_data:
                hit_chance_base = mutant_data.get('hit_chance_base', 50)
                hit_chance_per_danger = mutant_data.get('hit_chance_per_danger', 5)
                hit_chance = hit_chance_base + (hit_chance_per_danger * self.danger_level)
                base_damage_min = mutant_data.get('base_damage_min', 1.0)
                base_damage_max = mutant_data.get('base_damage_max', 1.8)
                damage_per_danger = mutant_data.get('damage_per_danger', 0.2)
                base_damage = random.uniform(base_damage_min, base_damage_max)
                base_damage += damage_per_danger * self.danger_level
            else:
                hit_chance = 50 + (base_difficulty * 30)
                base_damage = 1.5 + (base_difficulty * 1.5)

        mutation_bonus = getattr(enemy, 'mutation_damage_bonus', 0.0) or 0.0
        if mutation_bonus > 0:
            base_damage += mutation_bonus

        distance_config = BALANCE.get('distance', {}).get(self.distance, {})
        damage_mult = distance_config.get('enemy_damage_mult', 1.0)
        hit_chance_mult = distance_config.get('enemy_hit_chance_mult', 1.0)

        hit_chance = int(hit_chance * hit_chance_mult)
        accuracy_mod = enemy.get_accuracy_modifier() if hasattr(enemy, 'get_accuracy_modifier') else 1.0
        hit_chance = int(hit_chance * accuracy_mod)
        hit_chance += self._get_player_mg_penalty_bonus()
        hit_chance = min(hit_chance, 90)

        priorities = BALANCE['combat'].get('enemy_body_priorities', {
            "торс": 60, "руки": 15, "ноги": 15, "голова": 10
        })

        available_parts = enemy.get_available_parts()
        weighted_parts = []
        for part, weight in priorities.items():
            if part in available_parts:
                weighted_parts.extend([part] * weight)
        target_part = random.choice(weighted_parts) if weighted_parts else "торс"

        damage = base_damage * enemy.get_damage_multiplier() * damage_mult
        if random.random() < 0.2:
            damage *= 1.5

        mutant_data = enemy.mutant_data
        attack_texts = ["Враг атаковал {part}"]
        if isinstance(mutant_data, dict):
            attack_texts = mutant_data.get('attack_texts', ["Враг атаковал {part}"])
            if not isinstance(attack_texts, list) or not attack_texts:
                attack_texts = ["Враг атаковал {part}"]

        # 0.4.8.9: корректная замена {part} и {player_name}
        attack_text = random.choice(attack_texts).replace('{part}', target_part)
        attack_text = attack_text.replace('{player_name}', self.active_player.name)

        return {
            "part": target_part,
            "damage": damage,
            "hit_chance": hit_chance,
            "text": attack_text
        }

    # ==================== ВЫСТРЕЛ ====================

    def _get_first_ammo_type(self) -> str:
        actor = self.active_player
        if is_shell_loaded_weapon(actor.weapon):
            atype = actor.get_shell_first_ammo_type()
            return atype or "оболочечные"
        equipped = actor.get_equipped_magazine_obj()
        if not equipped:
            return "оболочечные"
        for ammo_type in equipped.get('ammo', {}).keys():
            return ammo_type
        return "оболочечные"

    def _consume_ammo(self, count: int):
        actor = self.active_player
        if is_shell_loaded_weapon(actor.weapon):
            actor.consume_shell_ammo(count)
            return
        if not actor.equipped_magazine:
            return
        actor.consume_magazine_ammo(actor.equipped_magazine, count)

    def _get_accuracy_for_part(self, target_part: str) -> float:
        actor = self.active_player
        base_accuracy = actor.get_weapon_accuracy_at_distance(self.distance)
        distance_config = BALANCE.get('distance', {}).get(self.distance, {})
        distance_modifier = distance_config.get('modifier', 1.0)
        if target_part == "голова":
            head_accuracy_base = actor.get_headshot_accuracy() / 100
            head_accuracy = head_accuracy_base * distance_modifier
            return min(base_accuracy, head_accuracy)
        return base_accuracy

    def _fire_single_shot(self, tgt_idx: int, part: str, ammo_type: str,
                          final_accuracy_percent: float) -> dict:
        actor = self.active_player
        result = {
            "line": "", "damage": 0.0, "killed": False,
            "part_destroyed": None, "immune": False, "ricochet": False,
        }

        if not (0 <= tgt_idx < len(self.enemies)):
            result["line"] = f"❌ Цель #{tgt_idx + 1} не найдена"
            return result

        target = self.enemies[tgt_idx]
        if not target.is_alive:
            result["line"] = f"❌ Цель #{tgt_idx + 1} ({target.display_name}) уже мертва"
            return result

        if getattr(target, 'pistol_immunity', False) and is_pistol_caliber(actor.weapon):
            result["line"] = f"🦴 {target.display_name}: иммунитет к пистолетным калибрам!"
            return result

        roll = random.randint(1, 100)
        if roll > final_accuracy_percent:
            result["line"] = f"❌ Промах по {target.display_name} #{tgt_idx + 1}"
            return result

        hit_part = part
        if hit_part in target.body_parts:
            if target.body_parts[hit_part]["hp"] <= 0:
                available = target.get_available_parts()
                if available:
                    hit_part = random.choice(available)
                else:
                    result["line"] = f"💀 {target.display_name}: все части разрушены"
                    return result

        if hasattr(actor, '_cached_weapon_damage'):
            weapon_damage = actor._cached_weapon_damage
        else:
            weapon_damage = get_weapon_damage_with_modules(actor, actor.weapon)

        if weapon_damage <= 0:
            weapon = get_weapon(actor.weapon)
            weapon_damage = weapon.get("damage", 1.0) if weapon else 1.0

        is_incendiary_shot = is_incendiary(ammo_type)

        damage_result = target.take_damage(
            weapon_damage, hit_part, ammo_type,
            is_melee=False, is_player_attacker=True,
            is_incendiary_shot=is_incendiary_shot,
        )

        if damage_result.get('immune'):
            result["immune"] = True
            result["line"] = f"🦴 {target.display_name}: урон не прошёл"
            return result

        if damage_result.get('ricochet'):
            result["ricochet"] = True
            result["line"] = f"🔰 {target.display_name}: рикошет!"
            return result

        absorbed = damage_result.get('absorbed', 0)
        dealt = damage_result['damage']
        result["damage"] = dealt

        # 0.4.9.0: сочный лог с эмодзи
        icon = "💥" if dealt > 5 else "🔫"
        line = f"{icon} **{target.display_name}** #{tgt_idx + 1} | _{hit_part}_ — **{dealt:.1f}** урона"

        if absorbed > 0:
            line += f" `(броня -{absorbed:.1f})`"
        if is_incendiary_shot and dealt > 0:
            line += " 🔥"

        bleeding_info = damage_result.get("bleeding", {})
        if bleeding_info.get("applied"):
            label = "сильное" if bleeding_info.get("strong") else "слабое"
            line += f" 🩸 ({label})"

        result["line"] = line

        if damage_result.get("part_destroyed"):
            result["part_destroyed"] = damage_result["part_destroyed"]

        torso_hp = target.body_parts.get("торс", {}).get("hp", 1)
        head_hp = target.body_parts.get("голова", {}).get("hp", 1)
        if torso_hp <= 0 or head_hp <= 0:
            target.is_alive = False
            target.lives = 0
            result["killed"] = True
            self._flee_pack_if_leader_dies(target)
            if self.all_enemies_dead():
                self.is_active = False
                for p in self.get_all_players():
                    p.combat_mode = False
            return result

        if damage_result["killed"]:
            result["killed"] = True
            self._flee_pack_if_leader_dies(target)
            if self.all_enemies_dead():
                self.is_active = False
                for p in self.get_all_players():
                    p.combat_mode = False

        return result

    def player_shoot(self, target_part: str,
                     secondary_shots: List[Tuple[int, str]] = None,
                     actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        if not self.can_shoot_again():
            return {"success": False, "message": "❌ Вы уже сделали действие в этом ходу!"}

        if not self.can_shoot_now():
            return {"success": False, "message": "🔧 **Перезарядка Heavy MG (2/2)!**"}

        actor = self.active_player

        weapon = get_weapon(actor.weapon)
        if not weapon:
            return {"success": False, "message": "❌ Нет оружия!"}

        if is_spec_weapon(actor.weapon):
            return self._player_fire_grenade_launcher_shell()

        if is_shotgun(actor.weapon):
            return self._player_shoot_shotgun(target_part)

        current_ammo = get_current_ammo(actor.weapon, actor)
        if current_ammo <= 0:
            return {"success": False, "message": "❌ Нет патронов в магазине!"}

        weapon_type = get_weapon_type(actor.weapon)
        requested_shots = get_shots_per_action(actor.weapon)

        semi_auto_available = False
        semi_auto_penalty = 0.0
        if is_semi_auto_sniper(actor.weapon) and current_ammo >= 2:
            sub_cfg = get_sniper_subtype_config(actor.weapon)
            chance = float(sub_cfg.get('second_shot_chance', 50))
            if random.uniform(0, 100) <= chance:
                semi_auto_available = True
                semi_auto_penalty = float(sub_cfg.get('second_shot_accuracy_penalty', 0.15))

        shots = min(requested_shots, current_ammo)
        ammo_cost = shots

        if current_ammo < ammo_cost:
            return {"success": False,
                    "message": f"❌ Не хватает патронов! Нужно {ammo_cost}, есть {current_ammo}"}

        self._consume_ammo(ammo_cost)
        self.shots_this_turn += 1

        base_accuracy_percent = self._get_accuracy_for_part(target_part) * 100

        primary_idx = self.target_index
        shots_plan: List[Tuple[int, str]] = [(primary_idx, target_part)] * shots

        if shots >= 2 and secondary_shots:
            for i, entry in enumerate(secondary_shots):
                if i + 1 >= shots:
                    break
                if not isinstance(entry, tuple) or len(entry) != 2:
                    continue
                tgt_idx, part = entry
                shots_plan[i + 1] = (tgt_idx, part)

        ammo_type = self._get_first_ammo_type()

        if not hasattr(actor, '_cached_weapon_damage'):
            actor._cached_weapon_damage = get_weapon_damage_with_modules(actor, actor.weapon)

        total_damage = 0.0
        shot_results = []
        part_destroyed = None
        killed_any = False

        for idx, (tgt_idx, part) in enumerate(shots_plan):
            res = self._fire_single_shot(tgt_idx, part, ammo_type, base_accuracy_percent)
            shot_results.append(res["line"])
            total_damage += res["damage"]
            if res["part_destroyed"]:
                part_destroyed = res["part_destroyed"]
            if res["killed"]:
                killed_any = True

        action_name = {
            "mg": "Очередь (3)",
            "smg": "Очередь (4)",
            "assault": "Очередь (2)",
        }.get(weapon_type, "Выстрел")

        # 0.4.9.0: красивый вывод результатов
        result_message = (
                f"**{action_name}** 🎯\n"
                f"📏 Дист: *{self.get_distance_name()}* | Точность: *{base_accuracy_percent:.0f}%*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                + "\n".join(shot_results)
        )
        if part_destroyed:
            result_message += f"\n🎯 {part_destroyed} уничтожена!"

        if semi_auto_available and not killed_any and self.get_alive_enemies():
            result_message += (
                f"\n\n🎯 **Semi-auto:** доступен второй выстрел! "
                f"(точность −{int(semi_auto_penalty * 100)}%)"
            )
            return {
                "success": True,
                "killed": False,
                "damage": total_damage,
                "turn_ended": False,
                "part_destroyed": part_destroyed,
                "semi_auto_pending": True,
                "semi_auto_penalty": semi_auto_penalty,
                "message": result_message,
            }

        self._end_player_turn()

        return {
            "success": True,
            "killed": killed_any,
            "damage": total_damage,
            "turn_ended": True,
            "part_destroyed": part_destroyed,
            "message": result_message,
        }

    # ==================== 0.4.8.7: ДУПЛЕТ ====================

    def player_shoot_double(self, target_part: str,
                            actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        actor = self.active_player
        double_cfg = get_weapon_double_shot_config(actor.weapon)

        if not double_cfg:
            return {"success": False,
                    "message": "❌ У этого оружия нет режима дуплета!"}

        ammo_cost = int(double_cfg.get("ammo_cost", 2))
        dmg_mult = float(double_cfg.get("damage_mult", 2.0))
        acc_penalty = float(double_cfg.get("accuracy_penalty", 0.10))

        # Проверка патронов
        if is_shell_loaded_weapon(actor.weapon):
            current_ammo = actor.get_shell_ammo_count()
        else:
            current_ammo = get_current_ammo(actor.weapon, actor)

        if current_ammo < ammo_cost:
            return {"success": False,
                    "message": (
                        f"❌ Для дуплета нужно {ammo_cost} патрона, "
                        f"в стволе {current_ammo}!"
                    )}

        if self.distance == "far":
            return {"success": False,
                    "message": "❌ Дуплет не работает на дальней дистанции!"}

        target = self.enemy
        if not target or not target.is_alive:
            return {"success": False, "message": "❌ Нет цели!"}

        # Списываем патроны
        if is_shell_loaded_weapon(actor.weapon):
            actor.consume_shell_ammo(ammo_cost)
        else:
            self._consume_ammo(ammo_cost)

        self.shots_this_turn += 1

        # Точность
        base_acc = self._get_accuracy_for_part(target_part)
        final_acc = max(0.05, base_acc - acc_penalty)
        final_acc_percent = final_acc * 100

        ammo_type = self._get_first_ammo_type()

        # Бросок
        roll = random.randint(1, 100)
        if roll > final_acc_percent:
            self._end_player_turn()
            return {
                "success": True, "killed": False, "damage": 0,
                "turn_ended": True,
                "message": (
                    f"❌ **Дуплет** — промах! "
                    f"(точность {final_acc_percent:.0f}%)"
                ),
            }

        # Урон
        if hasattr(actor, '_cached_weapon_damage'):
            weapon_damage = actor._cached_weapon_damage
        else:
            weapon_damage = get_weapon_damage_with_modules(actor, actor.weapon)
        if weapon_damage <= 0:
            weapon = get_weapon(actor.weapon)
            weapon_damage = weapon.get("damage", 1.0) if weapon else 1.0

        # Shotgun-множители
        dist_mult = get_shotgun_damage_multiplier(self.distance, ammo_type)
        close_bonus = 1.0
        if self.distance == "close":
            close_bonus = get_shotgun_close_bonus(ammo_type)
        ammo_bonus = get_shotgun_ammo_damage_bonus(ammo_type)

        # Итог: база × double × shotgun_mult × close_bonus + ammo_bonus
        final_damage = (
                weapon_damage * dmg_mult * dist_mult * close_bonus + ammo_bonus
        )

        hit_part = target_part
        if hit_part in target.body_parts \
                and target.body_parts[hit_part]["hp"] <= 0:
            available = target.get_available_parts()
            if available:
                hit_part = random.choice(available)

        is_incendiary_shot = is_incendiary(ammo_type)

        damage_result = target.take_damage(
            final_damage, hit_part, ammo_type,
            is_melee=False, is_player_attacker=True,
            is_incendiary_shot=is_incendiary_shot,
        )

        if damage_result.get('immune'):
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0,
                    "turn_ended": True,
                    "message": f"🦴 {target.display_name}: урон не прошёл"}

        if damage_result.get('ricochet'):
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0,
                    "turn_ended": True,
                    "message": f"🔰 {target.display_name}: рикошет!"}

        dealt = damage_result['damage']
        absorbed = damage_result.get('absorbed', 0)

        line = (
            f"💥💥 **ДУПЛЕТ** {target.display_name}: "
            f"{hit_part} ({dealt:.1f})"
        )
        if absorbed > 0:
            line += f" [броня -{absorbed:.1f}]"
        if is_incendiary_shot and dealt > 0:
            line += " 🔥"

        torso_hp = target.body_parts.get("торс", {}).get("hp", 1)
        head_hp = target.body_parts.get("голова", {}).get("hp", 1)
        if torso_hp <= 0 or head_hp <= 0:
            target.is_alive = False
            target.lives = 0
            damage_result['killed'] = True

        killed = damage_result.get('killed', False)
        if killed:
            self._flee_pack_if_leader_dies(target)
            if self.all_enemies_dead():
                self.is_active = False
                for p in self.get_all_players():
                    p.combat_mode = False

        self._end_player_turn()
        return {
            "success": True, "killed": killed, "damage": dealt,
            "turn_ended": True,
            "message": line + (
                f"\n💀 **{target.display_name}** уничтожен!" if killed else ""
            ),
        }

    # ==================== ДРОБОВИК ====================

    def _player_shoot_shotgun(self, target_part: str) -> dict:
        actor = self.active_player
        weapon = get_weapon(actor.weapon)
        if not weapon:
            return {"success": False, "message": "❌ Нет оружия!"}

        if is_shell_loaded_weapon(actor.weapon):
            current_ammo = actor.get_shell_ammo_count()
            if current_ammo <= 0:
                return {"success": False, "message": "❌ Нет патронов в стволе!"}
        else:
            current_ammo = get_current_ammo(actor.weapon, actor)
            if current_ammo <= 0:
                return {"success": False, "message": "❌ Нет патронов в магазине!"}

        ammo_type = self._get_first_ammo_type()

        if self.distance == "far":
            if is_shotgun_far_blocked(ammo_type):
                if is_shell_loaded_weapon(actor.weapon):
                    actor.consume_shell_ammo(1)
                else:
                    self._consume_ammo(1)
                self.shots_this_turn += 1
                self._end_player_turn()
                return {
                    "success": True, "killed": False, "damage": 0, "turn_ended": True,
                    "message": "❌ **Промах!** Дробовик неэффективен вдаль.",
                }

        if is_shell_loaded_weapon(actor.weapon):
            actor.consume_shell_ammo(1)
        else:
            self._consume_ammo(1)

        self.shots_this_turn += 1

        final_accuracy_percent = self._get_accuracy_for_part(target_part) * 100

        roll = random.randint(1, 100)
        if roll > final_accuracy_percent:
            self._end_player_turn()
            return {
                "success": True, "killed": False, "damage": 0, "turn_ended": True,
                "message": f"❌ Промах! (точность {final_accuracy_percent:.0f}%)"
            }

        hit_part = target_part
        target = self.enemy
        if not target:
            return {"success": False, "message": "❌ Нет цели!"}

        if hit_part in target.body_parts:
            if target.body_parts[hit_part]["hp"] <= 0:
                available = target.get_available_parts()
                if available:
                    hit_part = random.choice(available)

        if hasattr(actor, '_cached_weapon_damage'):
            weapon_damage = actor._cached_weapon_damage
        else:
            weapon_damage = get_weapon_damage_with_modules(actor, actor.weapon)

        if weapon_damage <= 0:
            weapon_damage = weapon.get("damage", 1.0)

        dist_mult = get_shotgun_damage_multiplier(self.distance, ammo_type)
        close_bonus = 1.0
        if self.distance == "close":
            close_bonus = get_shotgun_close_bonus(ammo_type)
        ammo_bonus = get_shotgun_ammo_damage_bonus(ammo_type)
        final_weapon_damage = weapon_damage * dist_mult * close_bonus + ammo_bonus

        is_incendiary_shot = is_incendiary(ammo_type)

        damage_result = target.take_damage(
            final_weapon_damage, hit_part, ammo_type,
            is_melee=False, is_player_attacker=True,
            is_incendiary_shot=is_incendiary_shot,
        )

        if damage_result.get('immune'):
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0, "turn_ended": True,
                    "message": f"🦴 {target.display_name}: урон не прошёл"}

        if damage_result.get('ricochet'):
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0, "turn_ended": True,
                    "message": f"🔰 {target.display_name}: рикошет!"}

        dealt = damage_result['damage']
        absorbed = damage_result.get('absorbed', 0)

        line = f"🔫 {target.display_name}: {hit_part} ({dealt:.1f})"
        if absorbed > 0:
            line += f" [броня -{absorbed:.1f}]"
        if is_incendiary_shot and dealt > 0:
            line += " 🔥"

        bleeding_info = damage_result.get("bleeding", {})
        if bleeding_info.get("applied"):
            label = "сильное" if bleeding_info.get("strong") else "слабое"
            line += f" 🩸 ({label})"

        torso_hp = target.body_parts.get("торс", {}).get("hp", 1)
        head_hp = target.body_parts.get("голова", {}).get("hp", 1)
        if torso_hp <= 0 or head_hp <= 0:
            target.is_alive = False
            target.lives = 0
            damage_result['killed'] = True

        killed = damage_result.get('killed', False)
        if killed:
            self._flee_pack_if_leader_dies(target)
            if self.all_enemies_dead():
                self.is_active = False
                for p in self.get_all_players():
                    p.combat_mode = False

        self._end_player_turn()
        return {"success": True, "killed": killed, "damage": dealt, "turn_ended": True,
                "message": line + (f"\n💀 **{target.display_name}** уничтожен!" if killed else "")}

    # ==================== ГП-25 ====================

    def _player_fire_grenade_launcher_shell(self) -> dict:
        actor = self.active_player
        weapon = get_weapon(actor.weapon)
        if not weapon:
            return {"success": False, "message": "❌ Нет оружия!"}

        if actor.get_shell_ammo_count() <= 0:
            return {"success": False, "message": "❌ ГП-25 не заряжен!"}

        mode = getattr(self, '_grenade_mode', 'single')
        if mode == 'group':
            return self._gp25_fire_group()
        return self._gp25_fire_single()

    def _gp25_fire_single(self) -> dict:
        from ..spec_weapons.grenade_launcher import fire_single_target, can_fire_grenade_launcher
        can_fire, reason = can_fire_grenade_launcher(self.distance)
        if not can_fire:
            return {"success": False, "message": reason}

        actor = self.active_player
        skill = actor.skills.get('меткость', 0)
        result = fire_single_target(self.distance, skill)

        actor.consume_shell_ammo(1)
        self.shots_this_turn += 1

        if not self.enemy:
            self._grenade_mode = 'single'
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0,
                    "turn_ended": True, "message": result.get('message', '')}

        dmg = result.get('damage', 0)
        dmg_res = self.enemy.take_damage(dmg, "торс", None,
                                         is_melee=False, is_player_attacker=True)
        dealt = dmg_res.get('damage', 0)
        absorbed = dmg_res.get('absorbed', 0)

        extra = ""
        if absorbed > 0:
            extra = f" [броня -{absorbed:.1f}]"
        if dmg_res.get('immune'):
            extra = " 🦴 урон не прошёл"

        msg = result.get('message', '') + f"\n🎯 **{self.enemy.display_name}**: {dealt:.1f} урона{extra}"
        self._grenade_mode = 'single'

        killed = dmg_res.get('killed', False)
        if killed:
            self._flee_pack_if_leader_dies(self.enemy)
            if self.all_enemies_dead():
                self.is_active = False
                for p in self.get_all_players():
                    p.combat_mode = False

        self._end_player_turn()
        return {"success": True, "killed": killed, "damage": dealt,
                "turn_ended": True, "message": msg}

    def _gp25_fire_group(self) -> dict:
        from ..spec_weapons.grenade_launcher import fire_group_target

        alive_enemies = self.get_alive_enemies()
        enemies_count = len(alive_enemies)
        if enemies_count <= 0:
            return {"success": False, "message": "❌ Нет врагов."}

        result = fire_group_target(enemies_count)

        self.active_player.consume_shell_ammo(1)
        self.shots_this_turn += 1

        total_dealt = 0.0
        for hit in result.get('hits', []):
            idx = hit['enemy_index']
            if hit['covered']:
                continue
            if idx < enemies_count:
                target = alive_enemies[idx]
                dmg_res = target.take_damage(hit['damage'], "торс", None,
                                             is_melee=False, is_player_attacker=True)
                total_dealt += dmg_res.get('damage', 0)
                if dmg_res.get('killed'):
                    self._flee_pack_if_leader_dies(target)

        self._grenade_mode = 'single'
        self._end_player_turn()
        return {"success": True, "killed": False, "damage": total_dealt,
                "turn_ended": True, "message": result.get('message', '')}

    def set_grenade_mode(self, mode: str):
        self._grenade_mode = mode

    # ==================== ГРАНАТЫ ====================

    def player_throw_grenade(self, grenade_id: str, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        actor = self.active_player

        if actor.get_grenade_count(grenade_id) <= 0:
            return {"success": False, "message": "❌ У вас нет этой гранаты!"}

        actor.consume_grenade(grenade_id)

        result = throw_grenade(
            actor, grenade_id, self.enemies,
            distance=self.distance, skills=actor.skills,
        )

        if result.get('self_exploded'):
            self_damage = result.get('self_damage', 0.0)
            zone = BALANCE.get('throwables', {}).get('grenade_self_hits_zone', 'торс')

            armor_result = apply_armor_protection(
                actor, zone, self_damage,
                damage_type="explosion", ammo_type=None, is_melee=False,
            )
            final_dmg = armor_result.get('final_damage', self_damage)
            armor_msg = armor_result.get('message', '')

            absorbed_self = armor_result.get('absorbed', 0)
            if absorbed_self > 0:
                apply_armor_after_hit(actor, zone, absorbed_self)

            actor.take_body_part_damage(zone, final_dmg)
            self.shots_this_turn += 1

            killed = not actor.is_alive
            if killed:
                self.is_active = False
                self.player.combat_mode = False

            msg = result.get('message', '')
            msg += f"\n💥 Урон себе: **{final_dmg:.1f}** в {zone}"
            if armor_msg:
                msg += f" — {armor_msg}"

            self._end_player_turn()
            return {"success": True, "killed": killed, "self_damage": final_dmg,
                    "turn_ended": True, "message": msg}

        if result.get('duds'):
            self.shots_this_turn += 1
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0,
                    "turn_ended": True, "message": result.get('message', '')}

        total_dealt = 0.0
        killed_any = False
        lines = []

        for hit in result.get('hits', []):
            idx = hit.get('enemy_index')
            if idx is None or not (0 <= idx < len(self.enemies)):
                continue
            target = self.enemies[idx]
            if not target.is_alive:
                continue

            if hit.get('covered'):
                lines.append(f"🛡️ {target.display_name} #{idx + 1}: укрылся")
                continue

            dmg = hit.get('damage', 0.0)
            if dmg <= 0:
                lines.append(f"💨 {target.display_name} #{idx + 1}: без урона")
                continue

            part = hit.get('part', 'торс')
            dmg_res = target.take_damage(dmg, part, None,
                                         is_melee=False, is_player_attacker=True)
            dealt = dmg_res.get('damage', 0)
            absorbed = dmg_res.get('absorbed', 0)
            total_dealt += dealt

            line = f"💥 {target.display_name} #{idx + 1}: {part} ({dealt:.1f})"
            if hit.get('explosive_applied'):
                line += " [экспансив ×2]"
            if absorbed > 0:
                line += f" [броня -{absorbed:.1f}]"
            if dmg_res.get('killed'):
                line += " 💀"
                killed_any = True
                self._flee_pack_if_leader_dies(target)
            lines.append(line)

        self.shots_this_turn += 1

        if killed_any and self.all_enemies_dead():
            self.is_active = False
            for p in self.get_all_players():
                p.combat_mode = False

        summary = result.get('message', '')
        if lines:
            summary += "\n" + "\n".join(lines)

        self._end_player_turn()
        return {"success": True, "killed": killed_any, "damage": total_dealt,
                "turn_ended": True, "message": summary}

    # ==================== НОЖИ ====================

    def player_throw_knife(self, knife_id: str, target_part: str,
                           actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        actor = self.active_player

        if actor.get_knife_count(knife_id) <= 0:
            return {"success": False, "message": "❌ У вас нет этого ножа!"}

        target = self.enemy
        if not target or not target.is_alive:
            return {"success": False, "message": "❌ Нет цели!"}

        skill = actor.skills.get('меткость', 0)

        if getattr(target, 'knife_damage_immunity', False):
            if target_part != "голова":
                self._end_player_turn()
                return {
                    "success": True, "killed": False, "damage": 0,
                    "turn_ended": True,
                    "message": (
                        f"🦴 **{target.display_name}** имеет иммунитет к метательным "
                        f"ножам! Попадание в {target_part} не наносит урона. "
                        f"💡 Цельтесь в голову — там есть шанс ваншота."
                    ),
                }

            base_chance = getattr(target, 'knife_head_kill_chance', 0)
            skill_bonus = getattr(target, 'knife_head_kill_skill_bonus', 0) * skill
            final_chance = base_chance + skill_bonus

            actor.consume_knife(knife_id)
            self.shots_this_turn += 1

            if random.uniform(0, 100) <= final_chance:
                target.is_alive = False
                target.lives = 0

                pack_fled = self._flee_pack_if_leader_dies(target)

                self._end_player_turn()
                msg = f"🎯 **{actor.name}** попал в шею Вождю и повалил его!"
                if pack_fled:
                    msg += "\n🐺 Остальные Мерзляки в ужасе убежали!"

                if self.all_enemies_dead():
                    self.is_active = False
                    for p in self.get_all_players():
                        p.combat_mode = False

                return {"success": True, "killed": True, "damage": 999,
                        "turn_ended": True, "message": msg}

            self._end_player_turn()
            return {
                "success": True, "killed": False, "damage": 0,
                "turn_ended": True,
                "message": (
                    f"🦴 **{actor.name}** метнул нож в голову **{target.display_name}**, "
                    f"но он лишь отскочил от кости!\n"
                    f"💡 Шанс ваншота был {final_chance:.1f}%."
                ),
            }

        if target_part == "голова" and getattr(target, 'knife_head_kill_chance', 0) > 0:
            base_chance = target.knife_head_kill_chance
            skill_bonus = target.knife_head_kill_skill_bonus * skill
            final_chance = base_chance + skill_bonus

            if random.uniform(0, 100) <= final_chance:
                actor.consume_knife(knife_id)
                self.shots_this_turn += 1
                target.is_alive = False
                target.lives = 0

                pack_fled = self._flee_pack_if_leader_dies(target)

                self._end_player_turn()
                msg = (
                    f"🎯 **{actor.name}** попал в шею Вождю и повалил его!"
                )
                if pack_fled:
                    msg += "\n🐺 Остальные Мерзляки в ужасе убежали!"

                if self.all_enemies_dead():
                    self.is_active = False
                    for p in self.get_all_players():
                        p.combat_mode = False

                return {"success": True, "killed": True, "damage": 999,
                        "turn_ended": True, "message": msg}

        result = throw_knife(
            actor, knife_id, target, target_part,
            distance=self.distance, player_skill=skill,
        )

        knife_penalty = getattr(target, 'knife_accuracy_penalty', 1.0)
        if knife_penalty < 1.0:
            result['accuracy'] = result.get('accuracy', 1.0) * knife_penalty
            if random.random() > result['accuracy']:
                result['hit'] = False

        actor.consume_knife(knife_id)
        self.shots_this_turn += 1

        if not result.get('hit'):
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0,
                    "turn_ended": True, "message": result.get('message', '❌ Промах!')}

        hit_part = result.get('part', target_part)
        base_damage = result.get('damage', 0.0)

        dmg_res = target.take_damage(base_damage, hit_part, None,
                                     is_melee=True, is_player_attacker=True)
        dealt = dmg_res.get('damage', 0)
        absorbed = dmg_res.get('absorbed', 0)

        line = result.get('message', '')
        line += f"\n⚔️ Нанесено: **{dealt:.1f}**"
        if absorbed > 0:
            line += f" [противоудар -{absorbed:.1f}]"
        if dmg_res.get('part_destroyed'):
            line += f" 🎯 {dmg_res['part_destroyed']} уничтожена!"

        bleeding_info = dmg_res.get("bleeding", {})
        if bleeding_info.get("applied"):
            label = "сильное" if bleeding_info.get("strong") else "слабое"
            line += f" 🩸 ({label})"

        killed = dmg_res.get('killed', False)
        if killed:
            line += f"\n💀 **{target.display_name}** уничтожен!"
            self._flee_pack_if_leader_dies(target)
            if self.all_enemies_dead():
                self.is_active = False
                for p in self.get_all_players():
                    p.combat_mode = False

        self._end_player_turn()
        return {"success": True, "killed": killed, "damage": dealt,
                "turn_ended": True, "message": line}

    # ==================== РУКОПАШНАЯ ====================

    def player_melee(self, target_part: str, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        if self.distance != "close":
            return {"success": False,
                    "message": f"❌ Рукопашная только на «Близко»! Сейчас: **{self.get_distance_name()}**."}

        actor = self.active_player

        melee_weapon_data = actor.get_melee_weapon_data() or {}
        ignores_melee_immunity = bool(melee_weapon_data.get('ignores_melee_immunity', False))

        if getattr(self.enemy, 'melee_immunity', False) and not ignores_melee_immunity:
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0, "turn_ended": True,
                    "message": f"🦴 **{self.enemy.display_name}** имеет иммунитет к рукопашным атакам!"}

        weapon_data = actor.get_melee_weapon_data()
        if not weapon_data:
            return {"success": False, "message": "❌ Ошибка: оружие не найдено!"}

        if actor.melee_weapon_durability <= 0 and not weapon_data.get('indestructible', False):
            old_weapon = actor.melee_weapon
            actor.melee_weapon = "кулаки"
            actor.melee_weapon_durability = 999
            self.add_log(f"⚠️ {old_weapon} сломался! Переход на кулаки.")
            weapon_data = actor.get_melee_weapon_data()

        final_accuracy = actor.get_melee_accuracy()

        melee_penalty = getattr(self.enemy, 'melee_accuracy_penalty', 1.0)
        if melee_penalty < 1.0:
            final_accuracy = int(final_accuracy * melee_penalty)

        if actor.is_body_part_destroyed("руки"):
            final_accuracy -= 20

        roll = random.randint(1, 100)
        if roll <= final_accuracy:
            hit_part = target_part
            if hit_part in self.enemy.body_parts:
                if self.enemy.body_parts[hit_part]["hp"] <= 0:
                    available = self.enemy.get_available_parts()
                    if available:
                        hit_part = random.choice(available)
                    else:
                        self.is_active = False
                        self.player.combat_mode = False
                        self._end_player_turn()
                        return {"success": True, "killed": True, "damage": 0,
                                "turn_ended": True,
                                "message": "💀 Враг уничтожен! Все части тела разрушены!"}

            melee_damage = actor.get_melee_damage()
            damage_result = self.enemy.take_damage(melee_damage, hit_part, None,
                                                   is_melee=True, is_player_attacker=True)
            actor.use_melee_weapon()

            part_destroyed = damage_result.get("part_destroyed", None)

            bleeding_msg = ""
            if can_cause_bleeding(actor.melee_weapon) and damage_result.get("damage", 0) > 0:
                bleeding_result = self._try_player_melee_bleeding(hit_part)
                if bleeding_result.get("applied"):
                    label = "сильное" if bleeding_result.get("strong") else "слабое"
                    bleeding_msg = f" 🩸 Наложено **{label}** кровотечение на {hit_part}!"

            if damage_result.get('immune'):
                self._end_player_turn()
                return {"success": True, "killed": False, "damage": 0, "turn_ended": True,
                        "message": damage_result.get('message', '🦴 урон не прошёл')}

            is_stunned = False
            if hit_part == "голова" and not self.enemy.is_mutant:
                stun_chance = actor.get_melee_stun_chance(hit_part)
                if random.randint(1, 100) <= stun_chance:
                    self.enemy.is_stunned = True
                    self.enemy.stun_turns = 2
                    is_stunned = True

            torso_hp = self.enemy.body_parts.get("торс", {}).get("hp", 1)
            head_hp = self.enemy.body_parts.get("голова", {}).get("hp", 1)
            if torso_hp <= 0 or head_hp <= 0:
                self.enemy.is_alive = False
                self.enemy.lives = 0
                damage_result["killed"] = True

            if damage_result["killed"]:
                self._flee_pack_if_leader_dies(self.enemy)
                if self.all_enemies_dead():
                    self.is_active = False
                    for p in self.get_all_players():
                        p.combat_mode = False
                self._end_player_turn()
                return {"success": True, "killed": True, "damage": damage_result["damage"],
                        "turn_ended": True,
                        "message": f"💀 **{self.enemy.display_name}** уничтожен!"}

            absorbed = damage_result.get('absorbed', 0)
            result_msg = f"👊 Попадание в {hit_part} ({damage_result['damage']:.1f} урона)"
            if absorbed > 0:
                result_msg += f" [броня -{absorbed:.1f}]"
            if part_destroyed:
                result_msg += f" 🎯 {part_destroyed} уничтожена!"
            if is_stunned:
                result_msg += f" 💫 ОГЛУШЕН на 2 хода!"
            if bleeding_msg:
                result_msg += bleeding_msg

            self._end_player_turn()
            return {"success": True, "killed": False, "damage": damage_result["damage"],
                    "turn_ended": True, "part_destroyed": part_destroyed,
                    "is_stunned": is_stunned, "message": result_msg}
        else:
            self._end_player_turn()
            return {"success": True, "killed": False, "damage": 0,
                    "turn_ended": True, "message": "❌ Промах!"}

    # ==================== АПТЕЧКА ====================

    def player_heal_in_combat(self, medkit_id: str, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        cfg = BALANCE.get('healing', {})
        if not cfg.get('in_combat_allowed', True):
            return {"success": False, "message": "❌ В бою нельзя использовать аптечку."}

        actor = self.active_player

        from ..pharmacy_system import use_medkit, get_available_medkits
        available = get_available_medkits(actor)
        available_ids = [e['item_id'] for e in available]

        if medkit_id not in available_ids:
            return {"success": False, "message": f"❌ У вас нет **{medkit_id}**!"}

        had_bleeding = actor.has_bleeding()
        result = use_medkit(actor, medkit_id)

        if not result.get('success'):
            return {"success": False, "message": result.get('message', '❌ Не удалось')}

        bleeding_removed = 0
        if had_bleeding:
            bleeding_removed = actor.clear_bleeding()

        self.shots_this_turn += 1

        msg = f"💊 **{actor.name}** использовал аптечку!\n{result.get('message', '')}"
        if bleeding_removed > 0:
            msg += f"\n🩸 Остановлено кровотечений: **{bleeding_removed}**"

        self._end_player_turn()
        return {"success": True, "turn_ended": True, "message": msg}

    # ==================== ДОБИВАНИЕ / ПОЩАДА ====================

    def player_finish(self, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}
        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}
        if not self.enemy.can_finish():
            return {"success": False, "message": "❌ Враг ещё может сопротивляться!"}

        self.enemy.is_alive = False
        self.enemy.lives = 0
        self.enemy.spared = False
        try:
            from ..factions import on_kill_member
            actor = self.active_player
            fid = getattr(self.enemy, 'faction_id', '')
            if fid:
                on_kill_member(actor, fid)
        except Exception as e:
            logger.error(f"[FACTIONS] finish: {e}")
        self._flee_pack_if_leader_dies(self.enemy)

        if self.all_enemies_dead():
            self.is_active = False
            for p in self.get_all_players():
                p.combat_mode = False

        self._end_player_turn()
        return {"success": True, "killed": True, "turn_ended": True,
                "message": f"⚔️ **ДОБИТ!** Вы добили **{self.enemy.display_name}**!"}

    def player_spare(self, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}
        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        enemy = self.enemy
        if not enemy.can_be_spared():
            return {"success": False, "message": "❌ Враг не сдался!"}

        enemy.surrendered = True
        enemy.spared = True
        enemy.is_alive = False
        try:
            from ..factions import on_spare_member
            actor = self.active_player
            fid = getattr(enemy, 'faction_id', '')
            if fid:
                on_spare_member(actor, fid)
        except Exception as e:
            logger.error(f"[FACTIONS] spare: {e}")
        if self.all_enemies_dead():
            self.is_active = False
            for p in self.get_all_players():
                p.combat_mode = False

        self._end_player_turn()
        return {"success": True, "killed": False, "spared": True, "turn_ended": True,
                "message": f"🕊️ Вы пощадили **{enemy.display_name}**."}

    # ==================== ПЕРЕЗАРЯДКА ====================

    def player_reload(self, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}
        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        actor = self.active_player
        if is_heavy_mg(actor.weapon):
            return self._player_reload_heavy_mg()
        if is_mg(actor.weapon):
            return self._player_reload_mg_light()
        if is_shell_loaded_weapon(actor.weapon):
            return self._player_reload_shell()
        return self._player_reload_normal()

    def _player_reload_heavy_mg(self) -> dict:
        actor = self.active_player
        weapon = get_weapon(actor.weapon)
        weapon_mags = weapon.get('magazines', []) if weapon else []

        candidates = []
        for mag in actor.get_uninstalled_magazines():
            if mag["type_id"] not in weapon_mags:
                continue
            ammo_count = sum(mag.get("ammo", {}).values())
            if ammo_count > 0:
                candidates.append((mag, ammo_count))

        if not candidates:
            return {"success": False, "message": "❌ Нет запасных магазинов с патронами!"}

        candidates.sort(key=lambda x: x[1], reverse=True)
        new_mag, new_ammo_count = candidates[0]

        actor.uninstall_magazine()
        actor.install_magazine(new_mag["uid"])

        if hasattr(actor, '_cached_weapon_damage'):
            del actor._cached_weapon_damage

        new_mag_data = get_magazine(new_mag["type_id"])
        new_name = new_mag_data.get("name", new_mag["type_id"]) if new_mag_data else new_mag["type_id"]

        actor.start_mg_reload()
        self._end_player_turn()

        return {
            "success": True, "turn_ended": True,
            "message": (
                f"🔧 **Перезарядка Heavy MG (1/2)**\n"
                f"📀 Установлен: **{new_name}** ({new_ammo_count} патр.)\n"
                f"⚠️ На следующем ходу стрелять нельзя."
            ),
        }

    def _player_reload_mg_light(self) -> dict:
        actor = self.active_player
        weapon = get_weapon(actor.weapon)
        weapon_mags = weapon.get('magazines', []) if weapon else []

        candidates = []
        for mag in actor.get_uninstalled_magazines():
            if mag["type_id"] not in weapon_mags:
                continue
            ammo_count = sum(mag.get("ammo", {}).values())
            if ammo_count > 0:
                candidates.append((mag, ammo_count))

        if not candidates:
            return {"success": False, "message": "❌ Нет запасных магазинов с патронами!"}

        candidates.sort(key=lambda x: x[1], reverse=True)
        new_mag, new_ammo_count = candidates[0]

        actor.uninstall_magazine()
        actor.install_magazine(new_mag["uid"])

        if hasattr(actor, '_cached_weapon_damage'):
            del actor._cached_weapon_damage

        new_mag_data = get_magazine(new_mag["type_id"])
        new_name = new_mag_data.get("name", new_mag["type_id"]) if new_mag_data else new_mag["type_id"]

        self._end_player_turn()
        return {
            "success": True, "turn_ended": True,
            "message": f"🔄 **Смена магазина!** Установлен **{new_name}** ({new_ammo_count} патр.)",
        }

    def _player_reload_shell(self) -> dict:
        actor = self.active_player
        weapon = get_weapon(actor.weapon)
        if not weapon:
            return {"success": False, "message": "❌ Нет оружия!"}

        caliber = weapon.get('caliber')
        ammo_types = get_caliber_ammo_types(caliber)
        current = actor.get_shell_ammo_count()
        capacity = weapon.get('shell_capacity', 0)
        free = capacity - current

        if free <= 0:
            return {"success": False, "message": "✅ Ствол уже полный!"}

        loaded_total = 0
        loaded_types = []

        for atype in ammo_types:
            if actor.inventory.get(atype, 0) <= 0:
                continue
            to_load = actor.reload_shell(atype, free - loaded_total)
            if to_load > 0:
                loaded_total += to_load
                loaded_types.append(f"{atype} ×{to_load}")
            if loaded_total >= free:
                break

        if loaded_total <= 0:
            return {"success": False, "message": "❌ Нет патронов в инвентаре!"}

        if hasattr(actor, '_cached_weapon_damage'):
            del actor._cached_weapon_damage

        self._end_player_turn()
        return {
            "success": True, "turn_ended": True,
            "message": (
                f"🔄 **Заряжено в ствол:** {', '.join(loaded_types)}\n"
                f"🔋 В стволе: {actor.get_shell_ammo_count()}/{capacity}"
            ),
        }

    def _player_reload_normal(self) -> dict:
        actor = self.active_player
        weapon = get_weapon(actor.weapon)
        if not weapon:
            return {"success": False, "message": "❌ Нет оружия!"}

        weapon_mags = weapon.get('magazines', [])
        candidates = []
        for mag in actor.get_uninstalled_magazines():
            if mag["type_id"] not in weapon_mags:
                continue
            ammo_count = sum(mag.get("ammo", {}).values())
            if ammo_count > 0:
                candidates.append((mag, ammo_count))

        if not candidates:
            return {"success": False, "message": "❌ Нет запасных магазинов с патронами!"}

        candidates.sort(key=lambda x: x[1], reverse=True)
        new_mag, new_ammo_count = candidates[0]

        actor.uninstall_magazine()
        actor.install_magazine(new_mag["uid"])

        if hasattr(actor, '_cached_weapon_damage'):
            del actor._cached_weapon_damage

        new_mag_data = get_magazine(new_mag["type_id"])
        new_name = new_mag_data.get("name", new_mag["type_id"]) if new_mag_data else new_mag["type_id"]
        new_capacity = new_mag_data.get("capacity", 0) if new_mag_data else 0

        self._end_player_turn()
        return {
            "success": True, "turn_ended": True,
            "message": f"🔄 **Смена магазина!** Установлен **{new_name}** ({new_ammo_count}/{new_capacity})",
        }

    def player_defend(self, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}
        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        if self.last_player_action == "defend":
            return {"success": False, "message": "❌ Вы уже в защите!"}

        self.last_player_action = "defend"
        actor = self.active_player
        block_reduction = actor.get_block_damage_reduction()
        self._end_player_turn()
        return {"success": True, "turn_ended": True,
                "message": f"🛡️ **{actor.name}** приготовился к защите! Урон уменьшен на {block_reduction:.0f}%"}

    def player_retreat(self, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}
        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        actor = self.active_player
        leg_multiplier = 1.0
        if actor.is_body_part_destroyed("ноги"):
            leg_multiplier = 0.5

        distance_bonus = {"close": 0.7, "medium": 1.0, "far": 1.3}.get(self.distance, 1.0)
        stamina_chance = min(actor.stamina / 5, 1.0) * 100 * leg_multiplier * distance_bonus
        roll = random.randint(1, 100)

        if roll <= stamina_chance:
            self.is_active = False
            for p in self.get_all_players():
                p.combat_mode = False
            return {"success": True, "retreated": True, "turn_ended": True,
                    "message": f"🏃 **{actor.name}** успешно отступил!"}
        else:
            self._end_player_turn()
            return {"success": False, "retreated": False, "turn_ended": True,
                    "message": "❌ Отступление не удалось!"}

    # ==================== ХОД ВРАГА ====================

    def enemy_turn(self) -> List[dict]:
        results = []

        is_defending = self.last_player_action == "defend"
        defending_user_id = None
        if is_defending:
            try:
                defending_user_id = self.current_actor_user_id
            except Exception:
                defending_user_id = None

        all_players = self.get_all_players()
        alive_players = [p for p in all_players if p.is_alive]
        if not alive_players:
            return results

        for e in self.enemies:
            e.healed_this_turn = False

        for idx, enemy in enumerate(self.enemies):
            if not enemy.is_alive:
                continue

            torso_hp = enemy.body_parts.get("торс", {}).get("hp", 1)
            head_hp = enemy.body_parts.get("голова", {}).get("hp", 1)
            if torso_hp <= 0 or head_hp <= 0:
                enemy.is_alive = False
                enemy.lives = 0
                continue

            if not enemy.get_available_parts():
                enemy.is_alive = False
                enemy.lives = 0
                continue

            bleed_result = enemy.tick_bleeding()
            if bleed_result.get("total_damage", 0) > 0:
                for part_id, dmg in bleed_result.get("damage_by_part", {}).items():
                    if part_id in enemy.body_parts:
                        enemy.body_parts[part_id]["hp"] = max(
                            0, enemy.body_parts[part_id]["hp"] - dmg
                        )
                        enemy.lives -= dmg

                torso_hp = enemy.body_parts.get("торс", {}).get("hp", 1)
                head_hp = enemy.body_parts.get("голова", {}).get("hp", 1)
                if (enemy.lives <= 0
                        or not enemy.get_available_parts()
                        or torso_hp <= 0
                        or head_hp <= 0):
                    enemy.is_alive = False
                    enemy.lives = 0

                results.append({
                    "hit": False, "damage": bleed_result["total_damage"],
                    "part": None, "killed": not enemy.is_alive,
                    "enemy_index": idx,
                    "message": bleed_result["message"],
                })

                if not enemy.is_alive:
                    continue

            burn_result = enemy.tick_burning()
            if burn_result.get("damage", 0) > 0:
                dmg = burn_result["damage"]
                enemy_part = "торс" if "торс" in enemy.body_parts else None
                if enemy_part:
                    enemy.body_parts[enemy_part]["hp"] = max(0, enemy.body_parts[enemy_part]["hp"] - dmg)
                    enemy.lives -= dmg
                    torso_hp = enemy.body_parts.get("торс", {}).get("hp", 1)
                    head_hp = enemy.body_parts.get("голова", {}).get("hp", 1)
                    if (enemy.body_parts[enemy_part]["hp"] <= 0
                            or enemy.lives <= 0
                            or torso_hp <= 0
                            or head_hp <= 0):
                        enemy.is_alive = False
                        enemy.lives = 0

                results.append({
                    "hit": False, "damage": dmg, "part": None, "killed": not enemy.is_alive,
                    "enemy_index": idx,
                    "message": burn_result["message"],
                })

                if not enemy.is_alive:
                    continue

            if enemy.is_human and enemy.can_use_medkit():
                cfg = BALANCE.get('healing', {})
                threshold = cfg.get('enemy_use_threshold', 0.5)
                chance = cfg.get('enemy_use_chance', 40)
                if enemy.max_lives > 0 and (enemy.lives / enemy.max_lives) < threshold:
                    if random.randint(1, 100) <= chance:
                        medkit_result = enemy.use_medkit()
                        if medkit_result.get("success"):
                            results.append({
                                "hit": False, "damage": 0, "part": None, "killed": False,
                                "enemy_index": idx,
                                "message": medkit_result["message"],
                            })
                            continue

            if enemy.is_human and enemy.can_surrender():
                human_config = BALANCE.get('human_combat', {})
                surrender_chance = human_config.get('surrender_chance_legs_destroyed', 50)
                if random.randint(1, 100) <= surrender_chance:
                    enemy.surrendered = True
                    results.append({
                        "hit": False, "damage": 0, "part": None, "killed": False,
                        "enemy_index": idx,
                        "message": f"🏳️ **{enemy.display_name}** сдаётся!"
                    })
                    continue

            if enemy.is_stunned:
                enemy.stun_turns -= 1
                if enemy.stun_turns <= 0:
                    enemy.is_stunned = False
                results.append({
                    "hit": False, "damage": 0, "part": None, "killed": False,
                    "enemy_index": idx,
                    "message": f"💫 {enemy.display_name} оглушён!"
                })
                continue

            if not enemy.can_attack():
                results.append({
                    "hit": False, "damage": 0, "part": None, "killed": False,
                    "enemy_index": idx,
                    "message": f"💫 {enemy.display_name} не может атаковать!"
                })
                continue

            target_player = random.choice(alive_players)

            action = self.get_enemy_action(enemy)
            enemy_is_melee = enemy.is_mutant

            enemy_attacks = [action]
            if not enemy_is_melee and enemy.weapon:
                try:
                    from ..weapon_system import (
                        is_semi_auto_sniper,
                        get_sniper_subtype_config,
                    )
                    if is_semi_auto_sniper(enemy.weapon):
                        sub_cfg = get_sniper_subtype_config(enemy.weapon)
                        chance = float(sub_cfg.get('second_shot_chance', 50))
                        if random.uniform(0, 100) <= chance:
                            penalty = float(sub_cfg.get('second_shot_accuracy_penalty', 0.15))
                            second = dict(action)
                            second["hit_chance"] = int(action["hit_chance"] * (1.0 - penalty))
                            enemy_attacks.append(second)
                except Exception as e:
                    logger.error(f"[COMBAT] semi-auto enemy check: {e}")

            for attack_idx, action in enumerate(enemy_attacks):
                if not enemy.is_alive:
                    break
                if not target_player.is_alive:
                    break

                roll = random.randint(1, 100)
                if roll <= action["hit_chance"]:
                    final_damage = action["damage"]

                    if is_defending and defending_user_id is not None \
                            and target_player.user_id == defending_user_id:
                        block_reduction = target_player.get_block_damage_reduction()
                        final_damage = final_damage * (1.0 - block_reduction / 100.0)

                    enemy_ammo_type = getattr(enemy, 'weapon_ammo_type', None) if not enemy_is_melee else None

                    armor_result = apply_armor_protection(
                        target_player, action["part"], final_damage,
                        damage_type="melee" if enemy_is_melee else "bullet",
                        ammo_type=enemy_ammo_type,
                        is_melee=enemy_is_melee,
                    )
                    final_damage = armor_result.get('final_damage', final_damage)
                    armor_msg = armor_result.get('message', '')
                    ricochet = armor_result.get('ricochet', False)

                    if ricochet:
                        prefix = "🔁 " if attack_idx > 0 else ""
                        results.append({
                            "hit": True, "damage": 0, "part": action["part"], "killed": False,
                            "enemy_index": idx,
                            "message": f"{prefix}🔰 **РИКОШЕТ!** {enemy.display_name} атаковал **{target_player.name}** — броня отразила урон."
                        })
                        continue

                    absorbed = armor_result.get('absorbed', 0)
                    if absorbed > 0:
                        apply_armor_after_hit(target_player, action["part"], absorbed)

                    hit_part = action["part"]

                    bleeding_msg = ""
                    if enemy_is_melee and final_damage > 0:
                        bleeding_result = self._try_mutant_bleeding(enemy, hit_part, target_player)
                        if bleeding_result.get("applied"):
                            label = "сильное" if bleeding_result.get("strong") else "слабое"
                            bleeding_msg = f" 🩸({label})"

                    damage_result = target_player.take_body_part_damage(hit_part, final_damage)

                    if hit_part == "голова" and target_player.has_gas_mask \
                            and target_player.gas_mask.get("надет", False):
                        mask_damage = final_damage
                        current_dur = target_player.gas_mask.get("прочность", 0)
                        new_dur = max(0.0, current_dur - mask_damage)
                        target_player.gas_mask["прочность"] = new_dur
                        if new_dur <= 0:
                            target_player.gas_mask["состояние"] = "разбитый"
                            target_player.gas_mask["фильтр_вставлен"] = False
                            target_player.gas_mask["фильтр_прочность"] = 0.0
                            target_player.equipped_filter = None

                    if not target_player.is_alive:
                        prefix = "🔁 " if attack_idx > 0 else ""
                        results.append({
                            "hit": True, "damage": final_damage, "part": hit_part, "killed": True,
                            "enemy_index": idx,
                            "message": f"{prefix}💀 **{enemy.display_name}**: {action['text']}! **{target_player.name}** погиб!"
                        })
                        alive_players = [p for p in all_players if p.is_alive]
                        if not alive_players:
                            self.is_active = False
                            for p in all_players:
                                p.combat_mode = False
                            self.last_player_action = None
                            return results
                        break

                    part_destroyed = ""
                    if damage_result.get("destroyed", False):
                        part_names = {"голова": "Голова", "торс": "Торс", "руки": "Руки", "ноги": "Ноги"}
                        part_destroyed = f" {part_names.get(hit_part, hit_part)} уничтожена!"

                    armor_text = f" — {armor_msg}" if armor_msg else ""
                    prefix = "🔁 " if attack_idx > 0 else ""
                    results.append({
                        "hit": True, "damage": final_damage, "part": hit_part, "killed": False,
                        "enemy_index": idx,
                        "message": f"{prefix}💢 **{enemy.display_name}**: {action['text']} ({final_damage:.1f}) → **{target_player.name}**{part_destroyed}{armor_text}{bleeding_msg}"
                    })
                else:
                    prefix = "🔁 " if attack_idx > 0 else ""
                    results.append({
                        "hit": False, "damage": 0, "part": None, "killed": False,
                        "enemy_index": idx,
                        "message": f"{prefix}💨 **{enemy.display_name}** промахнулся!"
                    })

        self.last_player_action = None

        for p in self.get_all_players():
            if not p.is_alive:
                continue

            bleed_player = p.tick_bleeding()
            if bleed_player.get("total_damage", 0) > 0:
                for part_id, dmg in bleed_player.get("damage_by_part", {}).items():
                    if part_id in p.body_parts:
                        p.take_body_part_damage(part_id, dmg)

                results.append({
                    "hit": False, "damage": bleed_player["total_damage"],
                    "part": None, "killed": not p.is_alive,
                    "enemy_index": -1,
                    "message": f"🩸 **{p.name}**: {bleed_player['message']}",
                })

                if not p.is_alive:
                    results.append({
                        "hit": False, "damage": 0, "part": None, "killed": True,
                        "enemy_index": -1,
                        "message": f"💀 **{p.name}** погиб от кровотечения!",
                    })

            if hasattr(p, 'is_burning') and p.is_burning:
                burn_dmg = p.get_burning_damage_preview()
                if burn_dmg > 0:
                    part = "торс" if "торс" in p.body_parts else None
                    if part:
                        p.body_parts[part]["hp"] = max(0, p.body_parts[part]["hp"] - burn_dmg)
                        if p.body_parts[part]["hp"] <= 0:
                            p.is_alive = False

                    new_stacks = []
                    for t in p.is_burning:
                        t -= 1
                        if t > 0:
                            new_stacks.append(t)
                    p.is_burning = new_stacks

                    results.append({
                        "hit": False, "damage": burn_dmg, "part": None,
                        "killed": not p.is_alive,
                        "enemy_index": -1,
                        "message": f"🔥 **{p.name}** горит: {burn_dmg:.0f} урона",
                    })

            cold_result = apply_frostbite_damage(p)
            if cold_result.get('total_damage', 0) > 0:
                results.append({
                    "hit": False, "damage": 0, "part": None, "killed": False,
                    "enemy_index": -1,
                    "message": f"🥶 **{p.name}**: {cold_result.get('message', '')}",
                })

        if not any(p.is_alive for p in self.get_all_players()):
            self.is_active = False
            for p in self.get_all_players():
                p.combat_mode = False

        return results

    def advance_mg_reload_after_turn(self):
        for p in self.get_all_players():
            if is_heavy_mg(p.weapon) and p.mg_reload_progress == 2:
                p.mg_reload_progress = 0

    # ==================== STATUS EMBED ====================

    def _build_player_block(self, player: Player) -> str:
        parts_lines = []
        for part_id, part_data in player.body_parts.items():
            hp = part_data.get('hp', 0)
            max_hp = part_data.get('max_hp', 0)
            name = part_data.get('name', part_id)
            if hp <= 0:
                parts_lines.append(f"💀 {name}")
            else:
                parts_lines.append(f"{name}: {hp:.1f}/{max_hp:.1f}")
        hp_text = "\n".join(parts_lines)

        weapon = get_weapon(player.weapon)
        weapon_name = weapon.get("name", "Нет") if weapon else "Нет"

        if is_shell_loaded_weapon(player.weapon):
            current_ammo = player.get_shell_ammo_count()
            max_ammo = player.get_weapon_shell_capacity()
        else:
            current_ammo = get_current_ammo(player.weapon, player)
            max_ammo = get_weapon_max_ammo(player.weapon, player)

        melee_data = player.get_melee_weapon_data()
        melee_name = melee_data.get('name', 'Кулаки') if melee_data else 'Кулаки'

        from ..armor_system import get_armor_item, get_item_durability
        armor_text = "❌"
        if player.armor:
            a = get_armor_item(player.armor)
            dur = get_item_durability(player, player.armor)
            max_d = a.get('max_durability', 100) if a else 100
            armor_text = f"{a.get('emoji','')} {a.get('name','')} ({dur:.0f}/{max_d})" if a else "❌"

        helmet_text = "❌"
        if player.helmet:
            h = get_armor_item(player.helmet)
            dur = get_item_durability(player, player.helmet)
            max_d = h.get('max_durability', 100) if h else 100
            helmet_text = f"{h.get('emoji','')} {h.get('name','')} ({dur:.0f}/{max_d})" if h else "❌"

        status_lines = []
        if player.has_bleeding():
            preview = player.get_bleeding_preview()
            status_lines.append(
                f"🩸 Кровотечение: {preview['stacks']} стек. → {preview['total']:.0f}/ход"
            )
        if hasattr(player, 'is_burning') and player.is_burning:
            status_lines.append(f"🔥 Горит ({len(player.is_burning)} стек.)")

        extra = "\n" + "\n".join(status_lines) if status_lines else ""

        return (
            f"❤️ Части:\n{hp_text}\n"
            f"🧥 {armor_text}\n"
            f"⛑️ {helmet_text}\n"
            f"🔫 {weapon_name} ({current_ammo}/{max_ammo})\n"
            f"🗡️ {melee_name}"
            f"{extra}"
        )

    def get_status_embed(self) -> discord.Embed:
        total_players = len(self.get_all_players())
        title_suffix = f" (группа {total_players})" if total_players > 1 else ""

        embed = discord.Embed(
            title=f"⚔️ БОЙ ({len(self.get_alive_enemies())}/{len(self.enemies)} врагов){title_suffix}",
            color=discord.Color.red()
        )

        distance_emoji = {"close": "🟢", "medium": "🟡", "far": "🔴"}.get(self.distance, "⚪")
        embed.add_field(name="📏 Дистанция", value=f"{distance_emoji} **{self.get_distance_name()}**", inline=False)

        all_players = self.get_all_players()
        current_actor = self.get_current_actor()

        for idx, p in enumerate(all_players):
            is_current = (p.user_id == current_actor.user_id)
            marker = "🎯 " if is_current else ""
            role = "👑" if idx == 0 and total_players > 1 else "👤"
            value = self._build_player_block(p)
            embed.add_field(
                name=f"{marker}{role} {p.name}",
                value=value,
                inline=False,
            )

        for idx, enemy in enumerate(self.enemies):
            if not enemy.is_alive:
                continue

            is_target = (idx == self.target_index)
            target_marker = "🎯 " if is_target else ""

            parts_status = []
            for part, data in enemy.body_parts.items():
                if data["hp"] > 0:
                    parts_status.append(f"{part}: {int(data['hp'])}")
                else:
                    parts_status.append(f"{part}: 💀")
            parts_text = " | ".join(parts_status)

            enemy_extra = []
            if hasattr(enemy, 'burning_stacks') and enemy.burning_stacks:
                enemy_extra.append(f"🔥 ×{len(enemy.burning_stacks)}")
            if hasattr(enemy, 'bleeding_stacks') and enemy.bleeding_stacks:
                enemy_extra.append(f"🩸 ×{len(enemy.bleeding_stacks)}")
            if getattr(enemy, 'medkits', None):
                enemy_extra.append(f"💊 x{len(enemy.medkits)}")
            enemy_extra_text = ("\n" + " | ".join(enemy_extra)) if enemy_extra else ""

            mutation_level = getattr(enemy, 'mutation_level', 0) or 0
            mutation_text = f"\n🧬 УМ{mutation_level}" if mutation_level > 0 else ""

            if enemy.is_mutant:
                status_text = f"❤️ {enemy.lives:.1f} HP\n🎯 {parts_text}{mutation_text}"
                if enemy.armor_protection_percent > 0:
                    status_text += f"\n🛡️ Броня: {enemy.armor_protection_percent}%"
                if enemy.head_immunity:
                    status_text += "\n🦴 Иммунитет головы"
                if getattr(enemy, 'pistol_immunity', False):
                    status_text += "\n🔫 Иммунитет: пистолеты"
                if getattr(enemy, 'melee_immunity', False):
                    status_text += "\n👊 Иммунитет: рукопашная"
                if getattr(enemy, 'knife_damage_immunity', False):
                    status_text += "\n🔪 Иммунитет: метательные ножи"
                if enemy.arms_destroyed:
                    status_text += "\n⚠️ Руки уничтожены!"
                if enemy.legs_destroyed:
                    status_text += "\n⚠️ Ноги уничтожены!"
                if enemy.is_stunned:
                    status_text += f"\n💫 ОГЛУШЕН ({enemy.stun_turns})"
                status_text += enemy_extra_text
            else:
                weapon_name = "🔫"
                if enemy.weapon:
                    wdata = get_weapon(enemy.weapon)
                    if isinstance(wdata, dict):
                        weapon_name = wdata.get('name', '🔫')

                from ..armor_system import get_armor_item
                armor_line = ""
                helmet_line = ""
                if getattr(enemy, 'equipped_armor_id', None):
                    a_data = get_armor_item(enemy.equipped_armor_id)
                    if isinstance(a_data, dict):
                        armor_line = f"\n🧥 {a_data.get('name', '')}"
                if getattr(enemy, 'equipped_helmet_id', None):
                    h_data = get_armor_item(enemy.equipped_helmet_id)
                    if isinstance(h_data, dict):
                        helmet_line = f"\n⛑️ {h_data.get('name', '')}"

                status_text = (
                    f"❤️ {enemy.lives:.1f} HP\n"
                    f"🎯 {parts_text}\n"
                    f"🔫 {weapon_name}"
                    f"{armor_line}{helmet_line}"
                )
                fid = getattr(enemy, 'faction_id', '')
                if fid:
                    try:
                        from ..factions import get_faction_name, get_faction_emoji
                        faction_name = get_faction_name(fid)
                        faction_emoji = get_faction_emoji(fid)
                        status_text = f"{faction_emoji} **{faction_name}**\n" + status_text
                    except Exception:
                        pass
                if enemy.is_boss:
                    status_text = "☠️ **БОСС**\n" + status_text
                if enemy.surrendered and not enemy.spared:
                    status_text += "\n🏳️ СДАЁТСЯ"
                status_text += enemy_extra_text

            embed.add_field(
                name=f"{target_marker}{enemy.emoji} {enemy.display_name} #{idx + 1}",
                value=status_text,
                inline=False,
            )

        embed.add_field(name="🔄 Ход", value=f"Раунд: {self.turn + 1}", inline=True)

        if self.waiting_for_enemy:
            embed.add_field(name="⏳ Ожидание", value="Ход врагов...", inline=True)
        else:
            actor = self.get_current_actor()
            embed.add_field(name="🎯 Ваш ход", value=f"Ходит: **{actor.name}**", inline=True)

        log_text = "\n".join(self.log[-5:]) if self.log else "Бой начинается..."
        embed.add_field(name="📋 Лог боя", value=log_text, inline=False)

        return embed

    # ==================== SEMI-AUTO ====================

    def player_shoot_second_semi(self, target_part: str,
                                 target_idx: int = None,
                                 actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        if not self.can_act():
            return {"success": False, "message": "⏳ Дождитесь хода врага!"}

        actor = self.active_player
        weapon_id = actor.weapon

        if not is_semi_auto_sniper(weapon_id):
            return {"success": False,
                    "message": "❌ Второй выстрел доступен только semi-auto sniper."}

        current_ammo = get_current_ammo(weapon_id, actor)
        if current_ammo <= 0:
            return {"success": False,
                    "message": "❌ Нет патронов для второго выстрела!"}

        if target_idx is not None:
            if not (0 <= target_idx < len(self.enemies)):
                return {"success": False, "message": "❌ Неверный индекс цели!"}
            if not self.enemies[target_idx].is_alive:
                return {"success": False, "message": "❌ Эта цель уже мертва!"}
            self.target_index = target_idx

        sub_cfg = get_sniper_subtype_config(weapon_id)
        penalty = float(sub_cfg.get('second_shot_accuracy_penalty', 0.15))

        self._consume_ammo(1)

        base_accuracy_percent = self._get_accuracy_for_part(target_part) * 100
        second_accuracy = max(5.0, base_accuracy_percent * (1.0 - penalty))

        ammo_type = self._get_first_ammo_type()
        primary_idx = self.target_index

        res = self._fire_single_shot(primary_idx, target_part, ammo_type, second_accuracy)

        target_name = "?"
        if 0 <= primary_idx < len(self.enemies):
            target_name = self.enemies[primary_idx].display_name

        result_message = (
            f"🔁 **Второй выстрел semi-auto** по **{target_name}** "
            f"(точность {second_accuracy:.0f}%): {res['line']}"
        )
        if res["part_destroyed"]:
            result_message += f" 🎯 {res['part_destroyed']} уничтожена!"

        killed_any = res["killed"]

        self.shots_this_turn += 1
        self._end_player_turn()

        return {
            "success": True,
            "killed": killed_any,
            "damage": res["damage"],
            "turn_ended": True,
            "part_destroyed": res["part_destroyed"],
            "message": result_message,
        }

    def player_skip_second_semi(self, actor_user_id: int = None) -> dict:
        if actor_user_id is not None and not self.is_current_actor(actor_user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        self._end_player_turn()

        return {
            "success": True,
            "killed": False,
            "damage": 0,
            "turn_ended": True,
            "message": "🎯 Вы отказались от второго выстрела.",
        }