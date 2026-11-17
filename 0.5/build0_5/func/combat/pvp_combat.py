# -*- coding: utf-8 -*-
# func/combat/pvp_combat.py - Логика PvP-боя (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.6     — базовый PvP 1v1
#   0.4.6.1   — групповой PvP: команда A (team_a_players) vs команда B (team_b_players)
#   0.4.7.2   — урон атакующего берётся через get_attacker_weapon_damage()
#               (учитывает бонус модуля «удлинённый ствол»)

import random
import uuid
from typing import Optional, List

import discord

from config.map_config import BALANCE, WEAPONS
from ..player import Player
from ..weapon_system import (
    get_weapon,
    get_current_ammo,
    get_weapon_max_ammo,
    is_shell_loaded_weapon,
    is_spec_weapon,
    is_shotgun,
    is_shotgun_far_blocked,
    get_shotgun_damage_multiplier,
    get_shotgun_close_bonus,
    get_shotgun_ammo_damage_bonus,
    is_incendiary,
    is_heavy_mg,
    get_shots_per_action,
)
from ..armor_system import apply_armor_protection, apply_armor_after_hit
from ..cold_system import apply_frostbite_damage
from ..melee_system import get_melee_weapon
from utils.logger import get_logger

from .player_combatant import PlayerCombatant
from .constants import DISTANCES, DISTANCE_NAMES, MAX_COMBAT_LOG

logger = get_logger()


class PvPCombat:
    """PvP-бой. Поддерживает 1v1 и групповой (A vs B)."""

    def __init__(self, player_a: Player, player_b: Player,
                 channel: discord.TextChannel,
                 team_a_players: List[Player] = None,
                 team_b_players: List[Player] = None):
        self.combat_id = uuid.uuid4().hex[:12]

        self.leader_a = PlayerCombatant(player_a)
        self.leader_b = PlayerCombatant(player_b)

        ta = [player_a] + list(team_a_players or [])
        tb = [player_b] + list(team_b_players or [])

        self.team_a: List[PlayerCombatant] = [PlayerCombatant(p) for p in ta]
        self.team_b: List[PlayerCombatant] = [PlayerCombatant(p) for p in tb]

        self.player_a = self.team_a[0]
        self.player_b = self.team_b[0]

        self.channel = channel
        self.message: Optional[discord.Message] = None

        self.is_active = True
        self.log: list[str] = []

        first_team = random.choice(['A', 'B'])
        if first_team == 'A':
            self.turn_order = list(self.team_a) + list(self.team_b)
        else:
            self.turn_order = list(self.team_b) + list(self.team_a)

        self.current_turn_index = 0
        self.distance = random.choice(DISTANCES)
        self.turn = 0
        self.last_player_action = None

    # ==================== СВОЙСТВА ====================

    @property
    def current_combatant(self) -> PlayerCombatant:
        self._skip_dead_in_turn_order()
        if self.current_turn_index >= len(self.turn_order):
            self.current_turn_index = 0
        return self.turn_order[self.current_turn_index]

    @property
    def opponent_combatant(self) -> Optional[PlayerCombatant]:
        current = self.current_combatant
        enemies = self.get_enemy_team(current)
        alive_enemies = [e for e in enemies if e.is_alive]
        return random.choice(alive_enemies) if alive_enemies else None

    def _skip_dead_in_turn_order(self):
        steps = 0
        while steps < len(self.turn_order):
            current = self.turn_order[self.current_turn_index]
            if current.is_alive:
                return
            self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
            steps += 1

    def get_team_of(self, combatant: PlayerCombatant) -> str:
        if combatant in self.team_a:
            return 'A'
        if combatant in self.team_b:
            return 'B'
        return '?'

    def get_team_members(self, team: str) -> List[PlayerCombatant]:
        return self.team_a if team == 'A' else self.team_b

    def get_enemy_team(self, combatant: PlayerCombatant) -> List[PlayerCombatant]:
        team = self.get_team_of(combatant)
        return self.team_b if team == 'A' else self.team_a

    def get_combatant_by_user(self, user_id: int) -> Optional[PlayerCombatant]:
        for c in self.turn_order:
            if c.user_id == user_id:
                return c
        return None

    def get_opponent(self, user_id: int) -> Optional[PlayerCombatant]:
        c = self.get_combatant_by_user(user_id)
        if not c:
            return None
        enemies = [e for e in self.get_enemy_team(c) if e.is_alive]
        return random.choice(enemies) if enemies else None

    def is_user_turn(self, user_id: int) -> bool:
        return self.current_combatant.user_id == user_id

    def get_distance_name(self) -> str:
        return DISTANCE_NAMES.get(self.distance, self.distance)

    def add_log(self, text: str):
        if not text:
            return
        self.log.append(text)
        if len(self.log) > MAX_COMBAT_LOG:
            self.log = self.log[-MAX_COMBAT_LOG:]

    def switch_turn(self):
        if not self.is_active:
            return
        steps = 0
        total = len(self.turn_order)
        while steps < total:
            self.current_turn_index = (self.current_turn_index + 1) % total
            if self.turn_order[self.current_turn_index].is_alive:
                self.turn += 1
                self.last_player_action = None
                return
            steps += 1
        self.is_active = False

    # ==================== ПРОВЕРКИ ====================

    def can_act(self, user_id: int) -> bool:
        if not self.is_active:
            return False
        if not self.is_user_turn(user_id):
            return False
        c = self.get_combatant_by_user(user_id)
        if not c or not c.is_alive:
            return False
        return True

    # ==================== ДЕЙСТВИЯ ====================

    def player_shoot(self, user_id: int, target_part: str) -> dict:
        if not self.can_act(user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        attacker = self.get_combatant_by_user(user_id)
        defender = self.get_opponent(user_id)
        if not defender:
            return {"success": False, "message": "❌ Нет живой цели!"}

        weapon_id = attacker.player.weapon
        weapon = get_weapon(weapon_id)
        if not weapon:
            return {"success": False, "message": "❌ Нет оружия!"}

        if is_spec_weapon(weapon_id):
            return self._fire_grenade_launcher(attacker, defender, target_part)

        if is_shotgun(weapon_id):
            return self._fire_shotgun(attacker, defender, target_part)

        current_ammo = get_current_ammo(weapon_id, attacker.player)
        if current_ammo <= 0:
            return {"success": False, "message": "❌ Нет патронов! Перезарядитесь."}

        shots = get_shots_per_action(weapon_id)
        shots = min(shots, current_ammo)

        if is_shell_loaded_weapon(weapon_id):
            attacker.player.consume_shell_ammo(shots)
        else:
            if attacker.player.equipped_magazine:
                attacker.player.consume_magazine_ammo(
                    attacker.player.equipped_magazine, shots
                )

        accuracy = attacker.player.get_weapon_accuracy_at_distance(self.distance)
        ammo_type = self._get_attacker_ammo_type(attacker)

        # 0.4.7.2: урон с бонусом модулей
        base_weapon_damage = attacker.get_attacker_weapon_damage()

        total_damage = 0.0
        lines = []
        killed = False
        part_destroyed = None

        for i in range(shots):
            if not defender.is_alive:
                defender = self.get_opponent(user_id)
                if not defender:
                    break

            roll = random.randint(1, 100)
            if roll > accuracy * 100:
                lines.append(f"❌ Промах ({i + 1})")
                continue

            hit_part = target_part
            if hit_part not in defender.body_parts or defender.body_parts[hit_part]['hp'] <= 0:
                available = defender.get_available_parts()
                if available:
                    hit_part = random.choice(available)

            result = defender.take_damage(
                base_weapon_damage, hit_part, ammo_type,
                is_melee=False, is_player_attacker=True,
                is_incendiary_shot=is_incendiary(ammo_type),
            )

            if result.get('ricochet'):
                lines.append(f"🔰 {defender.display_name}: рикошет!")
                continue

            dealt = result.get('damage', 0)
            absorbed = result.get('absorbed', 0)
            total_damage += dealt

            line = f"✅ {defender.display_name}: {hit_part} ({dealt:.1f})"
            if absorbed > 0:
                line += f" [броня -{absorbed:.1f}]"
            if result.get('bleeding', {}).get('applied'):
                label = "сильное" if result['bleeding'].get('strong') else "слабое"
                line += f" 🩸({label})"
            if is_incendiary(ammo_type) and dealt > 0:
                line += " 🔥"
            lines.append(line)

            if result.get('part_destroyed'):
                part_destroyed = result['part_destroyed']
            if result.get('killed'):
                killed = True

        action_name = {
            "mg": "Очередь (3)",
            "smg": "Очередь (4)",
            "assault": "Очередь (2)",
        }.get(weapon.get('type', ''), "Выстрел")

        msg = (
                f"🔫 **{attacker.display_name}** — {action_name} "
                f"(дист. «{self.get_distance_name()}», точность {accuracy * 100:.0f}%): "
                + ", ".join(lines)
        )
        if part_destroyed:
            msg += f"\n🎯 Уничтожена часть тела: {part_destroyed}"

        return {"success": True, "killed": killed, "damage": total_damage, "message": msg}

    def _get_attacker_ammo_type(self, attacker: PlayerCombatant) -> str:
        weapon_id = attacker.player.weapon
        if is_shell_loaded_weapon(weapon_id):
            atype = attacker.player.get_shell_first_ammo_type()
            return atype or "оболочечные"
        equipped = attacker.player.get_equipped_magazine_obj()
        if not equipped:
            return "оболочечные"
        for atype in equipped.get('ammo', {}).keys():
            return atype
        return "оболочечные"

    def _fire_shotgun(self, attacker: PlayerCombatant,
                      defender: PlayerCombatant, target_part: str) -> dict:
        weapon_id = attacker.player.weapon
        weapon = get_weapon(weapon_id)

        if is_shell_loaded_weapon(weapon_id):
            current_ammo = attacker.player.get_shell_ammo_count()
            if current_ammo <= 0:
                return {"success": False, "message": "❌ Нет патронов!"}
        else:
            current_ammo = get_current_ammo(weapon_id, attacker.player)
            if current_ammo <= 0:
                return {"success": False, "message": "❌ Нет патронов!"}

        ammo_type = self._get_attacker_ammo_type(attacker)

        if self.distance == "far" and is_shotgun_far_blocked(ammo_type):
            if is_shell_loaded_weapon(weapon_id):
                attacker.player.consume_shell_ammo(1)
            else:
                if attacker.player.equipped_magazine:
                    attacker.player.consume_magazine_ammo(
                        attacker.player.equipped_magazine, 1
                    )
            return {
                "success": True, "killed": False, "damage": 0,
                "message": "❌ Промах! Дробовик неэффективен вдаль.",
            }

        if is_shell_loaded_weapon(weapon_id):
            attacker.player.consume_shell_ammo(1)
        else:
            if attacker.player.equipped_magazine:
                attacker.player.consume_magazine_ammo(
                    attacker.player.equipped_magazine, 1
                )

        accuracy = attacker.player.get_weapon_accuracy_at_distance(self.distance)
        roll = random.randint(1, 100)
        if roll > accuracy * 100:
            return {
                "success": True, "killed": False, "damage": 0,
                "message": f"❌ Промах! (точность {accuracy * 100:.0f}%)",
            }

        hit_part = target_part
        if hit_part not in defender.body_parts or defender.body_parts[hit_part]['hp'] <= 0:
            available = defender.get_available_parts()
            if available:
                hit_part = random.choice(available)

        # 0.4.7.2: базовый урон + бонус модулей
        weapon_damage = attacker.get_attacker_weapon_damage()
        dist_mult = get_shotgun_damage_multiplier(self.distance, ammo_type)
        close_bonus = 1.0
        if self.distance == "close":
            close_bonus = get_shotgun_close_bonus(ammo_type)
        ammo_bonus = get_shotgun_ammo_damage_bonus(ammo_type)
        final_weapon_damage = weapon_damage * dist_mult * close_bonus + ammo_bonus

        result = defender.take_damage(
            final_weapon_damage, hit_part, ammo_type,
            is_melee=False, is_player_attacker=True,
            is_incendiary_shot=is_incendiary(ammo_type),
        )

        if result.get('ricochet'):
            return {"success": True, "killed": False, "damage": 0,
                    "message": f"🔰 {defender.display_name}: рикошет!"}

        dealt = result.get('damage', 0)
        line = f"🔫 **{attacker.display_name}** → {defender.display_name}: {hit_part} ({dealt:.1f})"
        if is_incendiary(ammo_type) and dealt > 0:
            line += " 🔥"

        killed = result.get('killed', False)
        if killed:
            line += f"\n💀 **{defender.display_name}** повержен!"

        return {"success": True, "killed": killed, "damage": dealt, "message": line}

    def _fire_grenade_launcher(self, attacker: PlayerCombatant,
                               defender: PlayerCombatant, target_part: str) -> dict:
        if attacker.player.get_shell_ammo_count() <= 0:
            return {"success": False, "message": "❌ ГП-25 не заряжен!"}
        if self.distance == "close":
            return {"success": False,
                    "message": "❌ На близкой дистанции граната заденет вас!"}

        from ..spec_weapons.grenade_launcher import fire_single_target
        skill = attacker.player.skills.get("меткость", 0)
        result = fire_single_target(self.distance, skill)

        attacker.player.consume_shell_ammo(1)

        dmg = result.get('damage', 0)
        dmg_res = defender.take_damage(dmg, "торс", None,
                                       is_melee=False, is_player_attacker=True)
        dealt = dmg_res.get('damage', 0)

        msg = result.get('message', '')
        msg += f"\n🎯 **{defender.display_name}**: {dealt:.1f} урона"

        killed = dmg_res.get('killed', False)
        return {"success": True, "killed": killed, "damage": dealt,
                "message": f"💥 **{attacker.display_name}** — ГП-25.\n{msg}"}

    def player_melee(self, user_id: int, target_part: str) -> dict:
        if not self.can_act(user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        attacker = self.get_combatant_by_user(user_id)
        defender = self.get_opponent(user_id)
        if not defender:
            return {"success": False, "message": "❌ Нет живой цели!"}

        if self.distance != "close":
            return {"success": False, "message": "❌ Рукопашная только на «Близко»!"}

        weapon_data = attacker.player.get_melee_weapon_data()
        if not weapon_data:
            return {"success": False, "message": "❌ Оружие не найдено!"}

        accuracy = attacker.player.get_melee_accuracy()
        if attacker.player.is_body_part_destroyed("руки"):
            accuracy -= 20

        roll = random.randint(1, 100)
        if roll > accuracy:
            return {"success": True, "killed": False, "damage": 0,
                    "message": f"❌ **{attacker.display_name}** промахнулся!"}

        hit_part = target_part
        if hit_part not in defender.body_parts or defender.body_parts[hit_part]['hp'] <= 0:
            available = defender.get_available_parts()
            if available:
                hit_part = random.choice(available)

        melee_damage = attacker.player.get_melee_damage()
        result = defender.take_damage(melee_damage, hit_part, None,
                                      is_melee=True, is_player_attacker=True)
        attacker.player.use_melee_weapon()

        killed = result.get('killed', False)
        dealt = result.get('damage', 0)

        msg = f"👊 **{attacker.display_name}** → {defender.display_name}: {hit_part} ({dealt:.1f})"
        if killed:
            msg += f"\n💀 **{defender.display_name}** повержен!"

        return {"success": True, "killed": killed, "damage": dealt, "message": msg}

    def player_reload(self, user_id: int) -> dict:
        if not self.can_act(user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        combatant = self.get_combatant_by_user(user_id)
        player = combatant.player
        weapon_id = player.weapon
        weapon = get_weapon(weapon_id)
        if not weapon:
            return {"success": False, "message": "❌ Нет оружия!"}

        if is_shell_loaded_weapon(weapon_id):
            caliber = weapon.get('caliber')
            from ..weapon_system import get_caliber_ammo_types
            ammo_types = get_caliber_ammo_types(caliber)
            capacity = weapon.get('shell_capacity', 0)
            current = player.get_shell_ammo_count()
            free = capacity - current
            if free <= 0:
                return {"success": False, "message": "✅ Ствол полный!"}

            loaded = 0
            for atype in ammo_types:
                if player.inventory.get(atype, 0) <= 0:
                    continue
                to_load = player.reload_shell(atype, free - loaded)
                loaded += to_load
                if loaded >= free:
                    break
            if loaded <= 0:
                return {"success": False, "message": "❌ Нет патронов в инвентаре!"}
            return {"success": True,
                    "message": f"🔄 **{combatant.display_name}** зарядил ствол ({loaded})."}

        weapon_mags = weapon.get('magazines', [])
        candidates = []
        for mag in player.get_uninstalled_magazines():
            if mag["type_id"] not in weapon_mags:
                continue
            ammo_count = sum(mag.get("ammo", {}).values())
            if ammo_count > 0:
                candidates.append((mag, ammo_count))

        if not candidates:
            return {"success": False, "message": "❌ Нет запасных магазинов!"}

        candidates.sort(key=lambda x: x[1], reverse=True)
        new_mag, new_ammo = candidates[0]
        player.uninstall_magazine()
        player.install_magazine(new_mag["uid"])

        from ..weapon_system import get_magazine
        mag_data = get_magazine(new_mag["type_id"])
        mag_name = mag_data.get('name', new_mag["type_id"]) if mag_data else new_mag["type_id"]

        return {"success": True,
                "message": f"🔄 **{combatant.display_name}** сменил магазин: **{mag_name}** ({new_ammo})"}

    def player_heal(self, user_id: int, medkit_id: str) -> dict:
        if not self.can_act(user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}

        combatant = self.get_combatant_by_user(user_id)
        from ..pharmacy_system import use_medkit
        result = use_medkit(combatant.player, medkit_id)
        if not result.get('success'):
            return result
        return {"success": True,
                "message": f"💊 **{combatant.display_name}** — {result.get('message', '')}"}

    def change_distance(self, user_id: int, new_distance: str) -> dict:
        if not self.can_act(user_id):
            return {"success": False, "message": "⏳ Не ваш ход!"}
        if new_distance not in DISTANCES:
            return {"success": False, "message": "❌ Неизвестная дистанция!"}
        if new_distance == self.distance:
            return {"success": False, "message": "❌ Вы уже на этой дистанции!"}

        combatant = self.get_combatant_by_user(user_id)
        old = self.get_distance_name()
        self.distance = new_distance
        return {"success": True,
                "message": f"🏃 **{combatant.display_name}** переместился с «{old}» на «{self.get_distance_name()}»!"}

    def end_turn(self):
        self.switch_turn()

    # ==================== ПРОВЕРКА КОНЦА ====================

    def _team_alive(self, team: List[PlayerCombatant]) -> bool:
        return any(c.is_alive for c in team)

    def check_end(self) -> Optional[dict]:
        a_alive = self._team_alive(self.team_a)
        b_alive = self._team_alive(self.team_b)

        if not a_alive and not b_alive:
            return {"winner_team": None, "loser_team": None, "draw": True}
        if not a_alive:
            return {"winner_team": 'B', "loser_team": 'A'}
        if not b_alive:
            return {"winner_team": 'A', "loser_team": 'B'}
        return None

    # ==================== LOOT ====================

    def transfer_all_loot(self, winner_team: str, loser_team: str):
        winners = self.get_team_members(winner_team)
        losers = self.get_team_members(loser_team)

        winner_leader = winners[0]
        w = winner_leader.player

        for loser in losers:
            l = loser.player
            for item_id, count in l.inventory.items():
                if isinstance(count, int):
                    w.inventory[item_id] = w.inventory.get(item_id, 0) + count
                elif isinstance(count, list):
                    if item_id not in w.inventory or not isinstance(w.inventory[item_id], list):
                        w.inventory[item_id] = []
                    w.inventory[item_id].extend(count)

            w.weapons_inventory.extend(l.weapons_inventory)
            w.melee_inventory.extend(l.melee_inventory)
            w.armor_inventory.extend(l.armor_inventory)
            w.modules_inventory.extend(l.modules_inventory)
            w.filters.extend(l.filters)
            w.food_inventory.extend(l.food_inventory)

            for gid, cnt in l.grenades_inventory.items():
                w.grenades_inventory[gid] = w.grenades_inventory.get(gid, 0) + cnt
            for kid, cnt in l.throwing_knives_inventory.items():
                w.throwing_knives_inventory[kid] = w.throwing_knives_inventory.get(kid, 0) + cnt

            for mag in l.magazines:
                new_uid = w._generate_magazine_uid()
                w.magazines.append({
                    "uid": new_uid,
                    "type_id": mag["type_id"],
                    "ammo": dict(mag.get("ammo", {})),
                    "installed": False,
                    "weapon": None,
                })

            for weapon_id, ammo_dict in l.shell_ammo.items():
                if not ammo_dict:
                    continue
                existing = w.shell_ammo.get(weapon_id, {})
                for atype, cnt in ammo_dict.items():
                    existing[atype] = existing.get(atype, 0) + cnt
                w.shell_ammo[weapon_id] = existing

            if l.weapon and l.weapon not in w.weapons_inventory and l.weapon != w.weapon:
                w.weapons_inventory.append(l.weapon)
            if l.armor and l.armor not in w.armor_inventory and l.armor != w.armor:
                w.armor_inventory.append(l.armor)
            if l.helmet and l.helmet not in w.armor_inventory and l.helmet != w.helmet:
                w.armor_inventory.append(l.helmet)
            if l.melee_weapon and l.melee_weapon != "кулаки" \
                    and l.melee_weapon not in w.melee_inventory \
                    and l.melee_weapon != w.melee_weapon:
                w.melee_inventory.append(l.melee_weapon)

            for slot, module_id in (l.equipped_modules or {}).items():
                if module_id:
                    w.modules_inventory.append(module_id)

            l.inventory = {
                "аптечка_аи2": 0, "патроны": 0, "никели": 0, "еда": 0,
                "крысы": 0, "хлам": [], "фильтры": 0, "антирад": 0, "мед_подсумок": 0,
            }
            l.weapons_inventory = []
            l.melee_inventory = []
            l.armor_inventory = []
            l.modules_inventory = []
            l.filters = []
            l.food_inventory = []
            l.grenades_inventory = {}
            l.throwing_knives_inventory = {}
            l.shell_ammo = {}
            l.magazines = []
            l.equipped_magazine = None
            l.weapon = "пистолет_макарова"
            l.armor = None
            l.helmet = None
            l.melee_weapon = "кулаки"
            l.melee_weapon_durability = 999
            l.equipped_modules = {"scope": None, "grip": None, "muzzle": None}
            l.is_alive = False

    # ==================== СТАТУС EMBED ====================

    def _build_team_block(self, team_name: str, members: List[PlayerCombatant]) -> str:
        lines = []
        for idx, c in enumerate(members):
            is_current = (c.user_id == self.current_combatant.user_id)
            marker = "🎯 " if is_current else ""
            role = "👑" if idx == 0 else "👤"
            hp = c.player.get_total_health()
            max_hp = c.player.get_max_total_health()
            status = "💀" if not c.is_alive else f"❤️ {hp:.0f}/{max_hp:.0f}"
            lines.append(f"{marker}{role} {c.display_name} — {status}")
        return "\n".join(lines)

    def get_status_embed(self) -> discord.Embed:
        a_count = sum(1 for c in self.team_a if c.is_alive)
        b_count = sum(1 for c in self.team_b if c.is_alive)

        embed = discord.Embed(
            title=f"⚔️ PvP: команда A ({a_count}) vs команда B ({b_count})",
            color=discord.Color.dark_red()
        )

        dist_emoji = {"close": "🟢", "medium": "🟡", "far": "🔴"}.get(self.distance, "⚪")
        embed.add_field(
            name="📏 Дистанция",
            value=f"{dist_emoji} **{self.get_distance_name()}**",
            inline=False
        )

        embed.add_field(
            name="🅰️ Команда A",
            value=self._build_team_block('A', self.team_a),
            inline=True,
        )
        embed.add_field(
            name="🅱️ Команда B",
            value=self._build_team_block('B', self.team_b),
            inline=True,
        )

        current = self.current_combatant
        embed.add_field(name="🔄 Ход", value=f"Раунд {self.turn + 1}", inline=True)
        embed.add_field(
            name="🎯 Сейчас ходит",
            value=f"**{current.display_name}** ({self.get_team_of(current)})",
            inline=True,
        )

        log_text = "\n".join(self.log[-5:]) if self.log else "Бой начинается..."
        embed.add_field(name="📋 Лог", value=log_text, inline=False)

        return embed