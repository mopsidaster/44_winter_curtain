# -*- coding: utf-8 -*-
# func/views/social/sleep_view.py - UI сна (0.4.6)

import discord

from ...social.sleep import wake_up
from ...game_manager import game_manager
from utils.logger import get_logger

logger = get_logger()


class SleepingMenuView(discord.ui.View):
    """
    Меню спящего игрока.
    Показывает только кнопку «Проснуться».
    """

    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="☀️ Проснуться", style=discord.ButtonStyle.success)
    async def wake_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш персонаж!", ephemeral=True)
            return

        player = game_manager.get_player(self.user_id)
        if not player:
            await interaction.response.send_message("❌ Персонаж не найден.", ephemeral=True)
            return

        await interaction.response.defer()

        result = await wake_up(player)

        from ..main_menu import MainMenu
        from ...map_data import MAP_DATA

        station_data = MAP_DATA["станции"][player.location]
        total_hp = player.get_total_health()
        max_hp = player.get_max_total_health()

        embed = discord.Embed(
            title="☀️ Вы проснулись!",
            description=result,
            color=discord.Color.green(),
        )
        embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
        embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
        embed.add_field(name="📍 Локация", value=station_data["name"], inline=True)

        try:
            await interaction.edit_original_response(embed=embed, view=MainMenu())
        except Exception as e:
            logger.error(f"Ошибка при пробуждении: {e}")


def build_sleeping_embed(player) -> discord.Embed:
    """Embed, показываемый спящему игроку."""
    station_name = "?"

    from ...map_data import MAP_DATA
    station = MAP_DATA["станции"].get(player.location)
    if station:
        station_name = station.get("name", "?")

    embed = discord.Embed(
        title="😴 Вы спите",
        description=(
            f"**{player.name}** мирно спит на станции **{station_name}**.\n\n"
            f"💤 Пока вы спите:\n"
            f"• Ивенты и переходы не действуют\n"
            f"• Вас нельзя атаковать\n"
            f"• Группа в режиме «Расход»\n\n"
            f"🔔 Нажмите кнопку ниже, чтобы проснуться."
        ),
        color=discord.Color.dark_blue(),
    )

    total_hp = player.get_total_health()
    max_hp = player.get_max_total_health()
    embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
    embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)

    return embed