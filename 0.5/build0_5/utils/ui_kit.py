# -*- coding: utf-8 -*-
# utils/ui_kit.py - Безопасные компоненты UI

import discord
from utils.logger import get_logger

logger = get_logger()

class SafeButton(discord.ui.Button):
    """Кнопка, которая сама ловит ошибки и делает defer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
            await self.handle_click(interaction)
        except discord.errors.NotFound:
            pass # Interaction истек
        except Exception as e:
            logger.error(f"Ошибка в кнопке {self.custom_id}: {e}", exc_info=True)
            try:
                await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
            except:
                pass

    async def handle_click(self, interaction: discord.Interaction):
        """Переопределите этот метод в наследниках вместо callback."""
        raise NotImplementedError