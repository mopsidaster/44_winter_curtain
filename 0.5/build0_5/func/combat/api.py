# -*- coding: utf-8 -*-
# func/combat/api.py - Публичный API боя (0.4.9.0 Visual)
#
# ИСТОРИЯ:
#   0.4.8   — оптимизация
#   0.4.8.7 — action == "shoot_double" (Дуплет)
#   0.4.8.7.5 — ЦВЕТНЫЕ ПОЛОСКИ HP
#   0.4.9.0 — ВИЗУАЛ: Анимация броска инициативы, красивые полоски, обновленное меню после боя.

import asyncio
import random
import discord
from typing import List, Tuple

from config.map_config import BALANCE
from ..weapon_system import get_weapon, get_weapon_double_shot_config
from ..player import Player
from ..map_data import MAP_DATA
from database.db import save_player
from ..global_events import get_xp_multiplier, is_event_active
from utils.logger import get_logger

from .manager import combat_manager
from .helpers import get_mutant_data, LOOT_ITEMS

logger = get_logger()


# ==================== ХЕЛПЕРЫ ====================

def _is_surface_station(station_id: str) -> bool:
    return MAP_DATA["станции"].get(station_id, {}).get("type") == "на_поверхности"


def _build_hp_bar(current: float, maximum: float, length: int = 10) -> str:
    """0.4.9.0: цветная полоска HP."""
    if maximum <= 0:
        return "░" * length
    pct = max(0.0, min(1.0, current / maximum))
    filled = int(round(pct * length))
    return "█" * filled + "░" * (length - filled)


async def _return_to_main_menu(interaction: discord.Interaction, player: Player, title: str, desc: str) -> Tuple[discord.Embed, discord.ui.View]:
    from ..views.main_menu import MainMenu, build_main_embed

    station_data = MAP_DATA["станции"][player.location]

    # Используем новую красивую функцию из main_menu
    embed = build_main_embed(player, station_data)

    # Перезаписываем заголовок для отображения результата
    embed.title = f"🏆 {title}"
    embed.description = f"> **{desc}**\n\n" + (embed.description or "")

    return embed, MainMenu(player)


# ==================== СТАРТ БОЯ ====================

async def start_combat(interaction: discord.Interaction, player: Player, danger_level: int, hostile_station: bool = False, extra_players: list = None, forced_enemy_ids: list = None):
    from ..views.combat_views import CombatView

    # 0.4.9.0: Анимация броска инициативы
    channel = interaction.channel
    try:
        anim_msg = await channel.send("🎲 *Враги приближаются... Бросок инициативы!*")
        await asyncio.sleep(0.6)
        await anim_msg.edit(content="⚔️ **БОЙ НАЧАЛСЯ!**")
        await asyncio.sleep(0.4)
        await anim_msg.delete()
    except Exception:
        pass # Если не удалось отправить анимацию (нет прав), просто продолжаем

    combat = combat_manager.start_combat(
        player, danger_level, channel, hostile_station=hostile_station,
        extra_players=extra_players or [], forced_enemy_ids=forced_enemy_ids or [],
    )
    embed = combat.get_status_embed()
    current = combat.get_current_actor()
    view = CombatView(current.user_id)
    message = await channel.send(embed=embed, view=view)
    combat.message = message
    combat_manager.combat_messages[player.user_id] = message
    return embed, view


async def start_combat_no_interaction(player: Player, danger_level: int, channel: discord.TextChannel, hostile_station: bool = False, extra_players: list = None, forced_enemy_ids: list = None):
    from ..views.combat_views import CombatView

    try:
        anim_msg = await channel.send("🎲 *Засада! Бросок инициативы...*")
        await asyncio.sleep(0.6)
        await anim_msg.delete()
    except Exception:
        pass

    combat = combat_manager.start_combat(
        player, danger_level, channel, hostile_station=hostile_station,
        extra_players=extra_players or [], forced_enemy_ids=forced_enemy_ids or [],
    )
    embed = combat.get_status_embed()
    current = combat.get_current_actor()
    view = CombatView(current.user_id)
    message = await channel.send(embed=embed, view=view)
    combat.message = message
    combat_manager.combat_messages[player.user_id] = message
    return embed, view


# ==================== ЛОГИ ====================

async def send_combat_log(user_id: int, text: str):
    combat = combat_manager.get_combat(user_id)
    if not combat or not combat.channel or not text.strip():
        return
    embed = discord.Embed(description=text[:3900], color=discord.Color.orange())
    try:
        await combat.channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Ошибка отправки лога: {e}")


async def send_combat_logs(user_id: int, lines: List[str]):
    combat = combat_manager.get_combat(user_id)
    if not combat or not combat.channel:
        return
    clean = [l for l in lines if l and l.strip()]
    if not clean:
        return
    text = "\n".join(clean)[:3900]
    embed = discord.Embed(description=text, color=discord.Color.orange())
    try:
        await combat.channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Ошибка отправки батч-лога: {e}")


async def update_combat_status(user_id: int = None):
    from ..views.combat_views import CombatView
    if user_id is None: return
    combat = combat_manager.get_combat(user_id)
    if not combat or not combat.message: return

    embed = combat.get_status_embed()
    view = CombatView(combat.get_current_actor().user_id) if combat.is_active else None
    try:
        await combat.message.edit(embed=embed, view=view)
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статуса: {e}")


# ==================== НАГРАДА ====================

async def give_combat_reward(players, rewards_data: List[dict] = None, is_surface: bool = False) -> List[dict]:
    if not players:
        return []
    alive_players = [p for p in players if p.is_alive]
    if not alive_players: return []
    n = len(alive_players)

    party_bonus = float(BALANCE.get('party', {}).get('xp_bonus_multiplier', 1.15))
    share = 1.0 if n == 1 else (0.5 if n == 2 else 1.0 / n)

    if not rewards_data:
        rewards_data = [{"mutant_id": "упырь", "display_name": "Враг"}]

    leader = alive_players[0]
    mutation_cfg = BALANCE.get('mutation', {}) or {}
    xp_bonus_per_level = float(mutation_cfg.get('xp_bonus_per_level', 25))
    nickels_bonus_per_level = float(mutation_cfg.get('nickels_bonus_per_level', 25))

    total_xp_pool = 0
    total_nickels = 0
    loot_items = []
    weapon_drop = None
    has_boss = False

    for entry in rewards_data:
        if not isinstance(entry, dict): continue
        mutant_id = entry.get('mutant_id', 'упырь')
        mutant_data = get_mutant_data(mutant_id)
        is_spared = entry.get('spared', False)
        mut_lvl = int(entry.get('mutation_level', 0) or 0)

        if mutant_data:
            base_xp = random.randint(mutant_data.get('xp_min', 10), mutant_data.get('xp_max', 25))
            if mutant_data.get('is_boss', False):
                has_boss = True
        else:
            base_xp = random.randint(BALANCE['combat']['mutant_xp_min'], BALANCE['combat']['mutant_xp_max'])

        if is_spared:
            base_xp = max(1, base_xp // 2)
        if mut_lvl > 0:
            base_xp = int(base_xp * (1.0 + xp_bonus_per_level * mut_lvl / 100.0))

        xp_mult = get_xp_multiplier(leader)
        if is_event_active('loot_boost', leader):
            xp_mult *= 1.5
        total_xp_pool += int(base_xp * xp_mult)

        if mutant_data and not is_spared:
            loot = mutant_data.get('loot', {})
            if isinstance(loot, dict):
                for item_id, item_data in loot.items():
                    if item_id != "никели" and isinstance(item_data, dict):
                        if random.randint(1, 100) <= item_data.get('chance', 50):
                            count = random.randint(item_data.get('min', 1), item_data.get('max', 1))
                            loot_items.extend([item_id] * count)

        if mutant_data and mutant_data.get('is_human', False) and not is_spared:
            wd = mutant_data.get('weapon_drop', {})
            if isinstance(wd, dict) and random.randint(1, 100) <= wd.get('weapon', {}).get('chance', 0):
                enemy_weapon = entry.get('weapon')
                if enemy_weapon and enemy_weapon not in leader.weapons_inventory and enemy_weapon != leader.weapon:
                    leader.weapons_inventory.append(enemy_weapon)
                    weapon_drop = enemy_weapon

        if not is_spared:
            nickels = random.randint(mutant_data.get('nickels_min', 5), mutant_data.get('nickels_max', 15)) if mutant_data else random.randint(5, 15)
            if mut_lvl > 0:
                nickels = int(nickels * (1.0 + nickels_bonus_per_level * mut_lvl / 100.0))
            total_nickels += nickels

    nickels_cfg = BALANCE.get('nickels', {})
    multiplier = float(nickels_cfg.get('combat_multiplier', 1.25))
    if has_boss:
        multiplier *= float(nickels_cfg.get('boss_multiplier', 1.5))
    total_nickels = int(total_nickels * multiplier)

    leader.inventory["никели"] = leader.inventory.get("никели", 0) + total_nickels
    if loot_items:
        leader.inventory.setdefault("хлам", []).extend(loot_items)

    results = []
    loot_display = [f"{LOOT_ITEMS.get(i, {}).get('emoji', '📦')} {LOOT_ITEMS.get(i, {}).get('name', i)}" for i in loot_items]
    if weapon_drop and (wdata := get_weapon(weapon_drop)):
        loot_display.append(f"🔫 {wdata.get('name', weapon_drop)}")

    xp_per_player = int(total_xp_pool * (party_bonus if n > 1 else 1.0) * share)

    for idx, p in enumerate(alive_players):
        leveled_up = p.add_xp(xp_per_player, is_surface=is_surface)
        is_leader = (idx == 0)
        results.append({
            "user_id": p.user_id, "name": p.name, "xp": xp_per_player,
            "nickels": total_nickels if is_leader else 0,
            "loot_display": loot_display if is_leader else [],
            "weapon_drop": weapon_drop if is_leader else None,
            "leveled_up": leveled_up, "new_level": p.level if leveled_up else None,
            "is_leader": is_leader, "is_surface": is_surface,
        })
    return results


# ==================== ЗАРАЖЕНИЕ КРОВИ ====================

def _try_apply_blood_infection(player) -> bool:
    if not player.is_alive or 'заражение_крови' in player.diseases:
        return False
    if not (player.is_body_part_destroyed("руки") or player.is_body_part_destroyed("ноги")):
        return False
    player.diseases.append('заражение_крови')
    player.blood_infection_soft_transitions = 0
    return True


# ==================== ДЕЙСТВИЕ В БОЮ ====================

async def handle_combat_action(interaction: discord.Interaction, action: str, target_part: str = None):
    from ..views.combat_views import CombatView

    try:
        if not interaction.response.is_done():
            await interaction.response.defer()
    except discord.errors.NotFound:
        return None, None
    except discord.errors.InteractionResponded:
        pass

    try:
        combat = combat_manager.get_combat(interaction.user.id)
        if not combat:
            return discord.Embed(title="❌ Ошибка", description="Нет активного боя!", color=discord.Color.red()), None
        if not combat.is_active:
            return discord.Embed(title="❌ Ошибка", description="Бой уже завершён!", color=discord.Color.red()), None
        if hasattr(combat, 'is_current_actor') and not combat.is_current_actor(interaction.user.id):
            current = combat.get_current_actor()
            return discord.Embed(title="⏳ Не ваш ход", description=f"Сейчас ходит **{current.name}**.", color=discord.Color.orange()), CombatView(current.user_id)
        if not combat.can_act():
            return discord.Embed(title="⏳ Ожидание", description="Дождитесь хода врага!", color=discord.Color.orange()), CombatView(interaction.user.id)

        result = None
        actor_id = interaction.user.id

        if action == "shoot":
            if not target_part:
                embed = combat.get_status_embed().add_field(name="🎯 Выберите часть тела", value="Нажмите на кнопку:", inline=False)
                return embed, CombatView(interaction.user.id)
            result = combat.player_shoot(target_part, actor_user_id=actor_id)

        # 0.4.8.7: Дуплет
        elif action == "shoot_double":
            if not target_part:
                embed = combat.get_status_embed().add_field(
                    name="💥 Дуплет — выберите часть тела",
                    value="Нажмите на кнопку:", inline=False,
                )
                return embed, CombatView(interaction.user.id)
            result = combat.player_shoot_double(
                target_part, actor_user_id=actor_id
            )

        elif action == "shoot_second_semi":
            if not target_part:
                return combat.get_status_embed(), None
            tgt_idx, part = (target_part.split(":", 1) + [None])[:2] if ":" in target_part else (None, target_part)
            result = combat.player_shoot_second_semi(part, target_idx=int(tgt_idx) if tgt_idx else None, actor_user_id=actor_id)
        elif action == "skip_second_semi":
            result = combat.player_skip_second_semi(actor_user_id=actor_id)
        elif action == "shoot_secondary":
            secondary_shots = []
            primary_part = getattr(combat, '_primary_part', None) or "торс"
            if target_part:
                for chunk in target_part.split(","):
                    if ":" in chunk:
                        idx_str, part_str = chunk.split(":", 1)
                        try: secondary_shots.append((int(idx_str), part_str or primary_part))
                        except ValueError: pass
            result = combat.player_shoot(primary_part, secondary_shots=secondary_shots, actor_user_id=actor_id)
        elif action == "melee":
            if not target_part:
                return combat.get_status_embed(), CombatView(interaction.user.id)
            result = combat.player_melee(target_part, actor_user_id=actor_id)
        elif action == "throw_grenade":
            result = combat.player_throw_grenade(target_part, actor_user_id=actor_id)
        elif action == "throw_knife":
            knife_id, part = target_part.split(":", 1)
            result = combat.player_throw_knife(knife_id, part, actor_user_id=actor_id)
        elif action == "heal_in_combat":
            result = combat.player_heal_in_combat(target_part, actor_user_id=actor_id)
        elif action == "grenade_single":
            combat.set_grenade_mode('single')
            result = combat.player_shoot("торс", actor_user_id=actor_id)
        elif action == "grenade_group":
            combat.set_grenade_mode('group')
            result = combat.player_shoot("торс", actor_user_id=actor_id)
        elif action == "reload":
            result = combat.player_reload(actor_user_id=actor_id)
        elif action == "finish":
            result = combat.player_finish(actor_user_id=actor_id)
        elif action == "spare":
            result = combat.player_spare(actor_user_id=actor_id)
        elif action == "defend":
            result = combat.player_defend(actor_user_id=actor_id)
        elif action == "retreat":
            result = combat.player_retreat(actor_user_id=actor_id)
        elif action == "change_distance":
            result = combat.change_distance(target_part, actor_user_id=actor_id)
        elif action == "change_target":
            try: result = combat.change_target(int(target_part))
            except ValueError: result = {"success": False, "message": "❌ Неверный индекс цели!"}
        else:
            return discord.Embed(title="❌ Ошибка", description="Неизвестное действие!", color=discord.Color.red()), None

        if result:
            if result.get("success", False):
                combat.add_log(result.get("message", ""))
                await send_combat_log(interaction.user.id, result.get("message", ""))
            else:
                await send_combat_log(interaction.user.id, f"❌ {result.get('message', 'Ошибка')}")

        # Победа
        if combat.all_enemies_dead() or (result and result.get("killed", False) and not combat.get_alive_enemies()):
            combat.is_active = False
            all_players = combat.get_all_players()
            for p in all_players: p.combat_mode = False

            blood_infection_applied = [p.name for p in all_players if p.is_alive and _try_apply_blood_infection(p)]
            killed_ids = [e.mutant_id for e in combat.enemies if not e.is_alive]

            try:
                from ..game_manager import game_manager as _gm
                await _gm.check_raider_raid_early_end(combat.player, killed_ids)
            except Exception as e: logger.error(f"Ошибка проверки raider_raid: {e}")

            rewards_data = [{"mutant_id": e.mutant_id, "display_name": e.display_name, "weapon": e.weapon, "magazine": e.equipped_magazine, "spared": e.spared, "surrendered": e.surrendered, "mutation_level": getattr(e, 'mutation_level', 0) or 0} for e in combat.enemies]

            combat_manager.end_combat(interaction.user.id)
            is_surface = _is_surface_station(combat.player.location)
            rewards = await give_combat_reward([p for p in all_players if p.is_alive], rewards_data, is_surface=is_surface)

            reward_embed = discord.Embed(title="🎉 ПОБЕДА В БОЮ!", color=discord.Color.gold())
            for reward in rewards:
                val = f"⭐ +{reward['xp']} опыта"
                if reward.get('nickels', 0) > 0: val += f" | 💰 +{reward['nickels']} никелей"
                if reward.get('loot_display'): val += f"\n📦 Лут: {', '.join(reward['loot_display'])}"
                if reward.get('leveled_up'): val += f"\n🎉 **НОВЫЙ УРОВЕНЬ {reward['new_level']}!**"
                reward_embed.add_field(name=f"{'👑' if reward.get('is_leader') else '👤'} {reward['name']}", value=val, inline=False)

            if blood_infection_applied:
                reward_embed.add_field(name="🩸 **ЗАРАЖЕНИЕ КРОВИ**", value=f"Ранены: {', '.join(blood_infection_applied)}", inline=False)

            for p in all_players:
                p.clear_bleeding()
                await save_player(p)

            try:
                from ..factions import register_kill_for_tasks, on_spare_member
                for enemy in combat.enemies:
                    if not enemy.is_alive and not getattr(enemy, 'spared', False):
                        register_kill_for_tasks(combat.player, enemy.mutant_id)
                    elif getattr(enemy, 'spared', False) and (fid := getattr(enemy, 'faction_id', '')):
                        on_spare_member(combat.player, fid)
            except Exception as e: logger.error(f"[FACTIONS/TASKS]: {e}")

            if combat.channel:
                try: await combat.channel.send(embed=reward_embed)
                except Exception: pass

            return await _return_to_main_menu(interaction, combat.player, "БОЙ ЗАВЕРШЕН — ПОБЕДА!", "Все враги повержены. Возврат в меню.")

        # Отступление
        if result and result.get("retreated", False):
            combat.is_active = False
            for p in combat.get_all_players(): p.combat_mode = False
            combat_manager.end_combat(interaction.user.id)
            for p in combat.get_all_players(): await save_player(p)
            await update_combat_status(interaction.user.id)
            return await _return_to_main_menu(interaction, combat.player, "ОТСТУПЛЕНИЕ", f"**{combat.player.name}** успешно отступил.")

        # Semi-Auto
        if result and result.get("semi_auto_pending", False):
            from ..views.combat_views.semi_auto_menu import SemiAutoMenu
            embed = combat.get_status_embed()
            embed.add_field(name="🎯 Semi-auto", value=f"Второй выстрел доступен!\nТочность: **−{int(result.get('semi_auto_penalty', 0.15) * 100)}%**", inline=False)
            return embed, SemiAutoMenu(interaction.user.id)

        # Конец хода и ход врага
        if result and result.get("turn_ended", False):
            combat.advance_mg_reload_after_turn()
            combat.shots_this_turn = 0

            if combat.is_active and combat.waiting_for_enemy:
                try: enemy_results = combat.enemy_turn()
                except Exception as e:
                    logger.error(f"❌ Ошибка enemy_turn: {e}")
                    enemy_results = []

                log_lines = [er["message"] for er in enemy_results if er and er.get("message")]
                if log_lines: await send_combat_logs(interaction.user.id, log_lines)

                if any(er.get("killed") for er in enemy_results) and not any(p.is_alive for p in combat.get_all_players()):
                    combat.is_active = False
                    for p in combat.get_all_players(): p.combat_mode = False
                    combat_manager.end_combat(interaction.user.id)
                    for p in combat.get_all_players(): await save_player(p)
                    await update_combat_status(interaction.user.id)
                    embed = combat.get_status_embed()
                    embed.title = "💀 ВЫ ПОГИБЛИ"
                    embed.color = discord.Color.red()
                    return embed, None

                combat.waiting_for_enemy = False
                combat.shots_this_turn = 0
                combat.last_player_action = None
                combat._ensure_turn_order()

                by_id = {p.user_id: p for p in combat.get_all_players()}
                for uid in combat.turn_queue:
                    if (actor := by_id.get(uid)) and actor.is_alive:
                        combat.current_actor_user_id = uid
                        combat.round_start_user_id = uid
                        break

        for p in combat.get_all_players(): await save_player(p)

        try:
            if combat.message:
                new_embed = combat.get_status_embed()
                new_view = CombatView(combat.get_current_actor().user_id) if combat.is_active else None
                await combat.message.edit(embed=new_embed, view=new_view)
        except Exception as e: logger.error(f"Ошибка обновления сообщения боя: {e}")

        return combat.get_status_embed(), CombatView(combat.get_current_actor().user_id if combat.is_active else interaction.user.id)

    except discord.errors.NotFound:
        return None, None
    except Exception as e:
        logger.error(f"❌ ОШИБКА в handle_combat_action: {e}")
        return discord.Embed(title="❌ Ошибка", description=str(e), color=discord.Color.red()), None