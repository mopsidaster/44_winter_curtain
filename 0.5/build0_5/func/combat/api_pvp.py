# -*- coding: utf-8 -*-
# func/combat/api_pvp.py - Хендлер PvP-действий (0.4.6)
#
# ИСТОРИЯ:
#   0.4.6   — базовый PvP 1v1
#   0.4.6.1 — групповой PvP (команды)

import discord

from .pvp_manager import pvp_manager
from ..player import Player
from database.db import save_player
from utils.logger import get_logger

logger = get_logger()


async def handle_pvp_action(interaction: discord.Interaction,
                            combat_id: str,
                            action: str,
                            target_part: str = None):
    """Обработать PvP-действие. Возвращает (embed, view)."""
    from ..views.combat_views.pvp_combat_view import PvPCombatView

    combat = pvp_manager.get_combat(combat_id)
    if not combat or not combat.is_active:
        embed = discord.Embed(
            title="❌ Ошибка", description="Бой завершён.",
            color=discord.Color.red()
        )
        return embed, None

    if interaction.user.id != combat.current_combatant.user_id:
        embed = discord.Embed(
            title="⏳ Не ваш ход", description="Дождитесь хода противника.",
            color=discord.Color.orange()
        )
        return embed, PvPCombatView(combat_id)

    user_id = interaction.user.id

    result = None
    if action == "shoot":
        if not target_part:
            embed = combat.get_status_embed()
            embed.add_field(
                name="🎯 Выберите часть тела",
                value="Нажмите на кнопку в панели.",
                inline=False,
            )
            return embed, PvPCombatView(combat_id)
        result = combat.player_shoot(user_id, target_part)

    elif action == "melee":
        if not target_part:
            embed = combat.get_status_embed()
            embed.add_field(
                name="👊 Выберите часть тела",
                value="Нажмите на кнопку в панели.",
                inline=False,
            )
            return embed, PvPCombatView(combat_id)
        result = combat.player_melee(user_id, target_part)

    elif action == "reload":
        result = combat.player_reload(user_id)

    elif action == "heal":
        if not target_part:
            return combat.get_status_embed(), PvPCombatView(combat_id)
        result = combat.player_heal(user_id, target_part)

    elif action == "change_distance":
        if not target_part:
            return combat.get_status_embed(), PvPCombatView(combat_id)
        result = combat.change_distance(user_id, target_part)

    else:
        result = {"success": False, "message": f"❌ Неизвестное действие: {action}"}

    # Публичный лог
    if result and result.get("message"):
        combat.add_log(result["message"])
        try:
            if combat.channel:
                log_embed = discord.Embed(
                    description=result["message"],
                    color=discord.Color.dark_orange(),
                )
                await combat.channel.send(embed=log_embed)
        except Exception as e:
            logger.error(f"Ошибка отправки PvP-лога: {e}")

    # Передаём ход и проверяем конец
    if result and result.get("success"):
        combat.end_turn()
        end_info = combat.check_end()
        if end_info:
            return await _finish_pvp(interaction, combat, end_info)

    # Сохранение
    try:
        for c in combat.turn_order:
            await save_player(c.player)
    except Exception as e:
        logger.error(f"Ошибка сохранения игроков в PvP: {e}")

    embed = combat.get_status_embed()
    return embed, PvPCombatView(combat_id)


async def _finish_pvp(interaction: discord.Interaction, combat, end_info: dict):
    from ..views.main_menu import MainMenu

    combat.is_active = False

    winner_team = end_info.get("winner_team")
    loser_team = end_info.get("loser_team")
    draw = end_info.get("draw", False)

    if winner_team and loser_team:
        combat.transfer_all_loot(winner_team, loser_team)

    for c in combat.turn_order:
        c.player.combat_mode = False

    try:
        for c in combat.turn_order:
            await save_player(c.player)
    except Exception as e:
        logger.error(f"Ошибка сохранения после PvP: {e}")

    pvp_manager.end_combat(combat.combat_id)

    embed = discord.Embed(
        title="🏆 PvP завершён",
        color=discord.Color.gold() if winner_team else discord.Color.dark_gray(),
    )
    if winner_team and loser_team:
        winners = [c.display_name for c in combat.get_team_members(winner_team) if c.is_alive]
        losers = [c.display_name for c in combat.get_team_members(loser_team)]

        embed.description = (
            f"🏆 Победила команда **{winner_team}**!\n"
            f"Убиты: {', '.join(losers)}\n"
            f"Выжили: {', '.join(winners)}"
        )
        embed.add_field(
            name="🎁 Лут",
            value="Весь инвентарь побеждённых передан лидеру победившей команды.",
            inline=False,
        )
    elif draw:
        embed.description = "☠️ Все погибли. Никто не получил лут."

    try:
        if combat.channel:
            await combat.channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Ошибка отправки результата PvP: {e}")

    return embed, None