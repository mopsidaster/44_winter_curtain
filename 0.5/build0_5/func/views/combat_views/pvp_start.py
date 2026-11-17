# -*- coding: utf-8 -*-
# func/views/combat_views/pvp_start.py - Старт PvP из приглашения (0.4.6)
#
# ИСТОРИЯ:
#   0.4.6   — базовый 1v1
#   0.4.6.1 — групповой PvP: если игрок в бригаде, его союзники тоже в бой

import discord

from utils.logger import get_logger

logger = get_logger()


def _get_brigade_allies_for_pvp(player, station_id: str) -> list:
    """
    Собрать живых союзников игрока из его бригады, которые на той же станции.
    Работает только в режиме «Вместе».
    """
    from ...social.brigade_manager import brigade_manager
    from ...game_manager import game_manager

    brigade = brigade_manager.get_user_brigade(player.user_id)
    if not brigade or not brigade.is_active():
        return []

    allies = []
    for uid in brigade.get_member_ids():
        if uid == player.user_id:
            continue
        ally = game_manager.get_player(uid)
        if ally and ally.is_alive and ally.location == station_id \
                and not getattr(ally, 'is_sleeping', False):
            allies.append(ally)
    return allies


async def start_pvp_from_invite(interaction: discord.Interaction, invite):
    """Старт PvP после принятия приглашения. Поддерживает команды."""
    from ...game_manager import game_manager
    from ...combat.pvp_manager import pvp_manager
    from ...combat.pvp_combat import PvPCombat
    from ...combat.combat_manager import combat_manager
    from .pvp_combat_view import PvPCombatView

    initiator = game_manager.get_player(invite.initiator_id)
    target = game_manager.get_player(invite.target_id)

    if not initiator or not target:
        await interaction.followup.send("❌ Один из игроков не найден.", ephemeral=True)
        return

    if not initiator.is_alive or not target.is_alive:
        await interaction.followup.send("❌ Один из игроков мёртв.", ephemeral=True)
        return

    if combat_manager.get_combat(initiator.user_id) or combat_manager.get_combat(target.user_id):
        await interaction.followup.send("❌ Один из игроков уже в PvE-бою.", ephemeral=True)
        return
    if pvp_manager.is_user_in_combat(initiator.user_id) or pvp_manager.is_user_in_combat(target.user_id):
        await interaction.followup.send("❌ Один из игроков уже в PvP-бою.", ephemeral=True)
        return

    station_id = initiator.location

    # Союзники
    team_a_allies = _get_brigade_allies_for_pvp(initiator, station_id)
    team_b_allies = _get_brigade_allies_for_pvp(target, station_id)

    # Проверка, что все союзники не в боях
    all_allies = team_a_allies + team_b_allies
    for ally in all_allies:
        if combat_manager.get_combat(ally.user_id) or pvp_manager.is_user_in_combat(ally.user_id):
            await interaction.followup.send(
                f"❌ **{ally.name}** уже в бою.", ephemeral=True
            )
            return

    combat = PvPCombat(
        initiator, target, interaction.channel,
        team_a_players=team_a_allies,
        team_b_players=team_b_allies,
    )
    pvp_manager.register_combat(combat)

    # Все участники в combat_mode
    for c in combat.turn_order:
        c.player.combat_mode = True

    embed = combat.get_status_embed()
    view = PvPCombatView(combat.combat_id)

    first = combat.current_combatant
    msg = await interaction.followup.send(
        content=(
            f"⚔️ **PvP-бой начался!**\n"
            f"🅰️ Команда A: {', '.join(c.display_name for c in combat.team_a)}\n"
            f"🅱️ Команда B: {', '.join(c.display_name for c in combat.team_b)}\n"
            f"🎯 Первый ход: **{first.display_name}**"
        ),
        embed=embed,
        view=view,
    )
    try:
        combat.message = msg
    except Exception:
        pass

    logger.info(
        f"[PvP] Бой {combat.combat_id} начат: "
        f"A={[c.display_name for c in combat.team_a]} vs "
        f"B={[c.display_name for c in combat.team_b]}"
    )