# -*- coding: utf-8 -*-
# func/views/equipment/melee_change.py - Меню смены ближнего боя (0.4.4.7.1)
#
# Рефакторинг без изменения логики.

import discord

from utils.logger import get_logger

logger = get_logger()


class MeleeChangeMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = __import__("uuid").uuid4().hex[:8]

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()

            from .main_menu import EquipmentMenu
            from ._helpers import _build_equipment_embed

            view = EquipmentMenu(self.player)
            embed = _build_equipment_embed(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка back (melee change): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back (melee change): {e}")