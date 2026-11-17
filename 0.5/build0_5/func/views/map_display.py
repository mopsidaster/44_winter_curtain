# -*- coding: utf-8 -*-
# func/views/map_display.py - Обёртка показа карты (0.4.7.4)

import discord

from .map_render import MapPaginationView
from utils.logger import get_logger

logger = get_logger()


async def show_map(interaction: discord.Interaction):
    try:
        from ..game_manager import game_manager
        player = game_manager.get_player(interaction.user.id)

        view = MapPaginationView(player, page=0)
        embed = view.build_embed()

        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    except Exception as e:
        logger.error(f"Ошибка show_map: {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Ошибка отображения карты: {str(e)}", ephemeral=True
                )
        except Exception:
            pass