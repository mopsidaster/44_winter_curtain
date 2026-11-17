# -*- coding: utf-8 -*-
# func/views/social/brigade_view.py - Список всех групп (0.4.6)

import discord

from ...social.brigade_manager import brigade_manager
from ...social.brigade import STATE_ACTIVE
from ...map_data import MAP_DATA
from utils.logger import get_logger

logger = get_logger()


def build_brigade_list_embed(game_manager) -> discord.Embed:
    embed = discord.Embed(
        title="🤝 Все бригады Метро",
        color=discord.Color.blue(),
    )

    brigades = brigade_manager.get_all_brigades()
    if not brigades:
        embed.description = "Пока ни одной бригады не создано.\n\n💡 Создайте первую: `/brigada new`"
        return embed

    for brigade in brigades:
        state_text = "🚶 Вместе" if brigade.is_active() else "🔀 Расход"
        leader = game_manager.get_player(brigade.leader_id)
        leader_name = leader.name if leader else f"ID {brigade.leader_id}"

        members_lines = []
        for m in sorted(brigade.members, key=lambda x: x.joined_at):
            p = game_manager.get_player(m.user_id)
            if p:
                role = "👑" if m.user_id == brigade.leader_id else "👤"
                loc = MAP_DATA["станции"].get(p.location, {}).get("name", "?")
                members_lines.append(f"{role} {p.name} — 📍{loc}")

        embed.add_field(
            name=f"**{brigade.name}** ({brigade.member_count()}/3) — {state_text}",
            value=(
                    f"📝 {brigade.description or '_без описания_'}\n"
                    f"👑 Лидер: **{leader_name}**\n"
                    + "\n".join(members_lines)
            ),
            inline=False,
        )

    return embed