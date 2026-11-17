# -*- coding: utf-8 -*-
# func/views/look_around.py - Меню «Осмотреться» (0.4.8.3)
#
# ИСТОРИЯ:
#   0.4.8.3 — Кнопка "Торговля" перенесена в Главное меню.

import discord
import random
from .helpers import (
    game_manager, MAP_DATA, can_move, save_player, combat_manager,
    get_stamina_multiplier, BALANCE, is_workshop_station, is_celebration_station,
    ITEMS, get_filter_discount, check_tunnel, get_tunnel_zone_type,
    check_tunnel_contamination, enter_technical_tunnel
)
from ..station_utils import is_trade_station
from .technical_tunnel import TechnicalTunnelMenu
from ..food_system import get_food, can_cook, get_cooked_version, cook_food
from ..melee_system import get_melee_weapon


class LookAroundMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="🚇 Тех. тоннель", style=discord.ButtonStyle.primary)
    async def technical_tunnel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа командой /start", ephemeral=True)
                return
            if not player.is_alive:
                await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)
                return

            if not can_move(game_manager):
                await interaction.response.send_message(
                    "🌍 **Землетрясение!** Переходы временно заблокированы! Подождите немного.",
                    ephemeral=True
                )
                return

            current_station = MAP_DATA["станции"][player.location]
            tunnel_id = current_station.get("technical_tunnel")

            if not tunnel_id:
                await interaction.response.send_message(
                    "❌ На этой станции нет технического тоннеля!",
                    ephemeral=True
                )
                return

            if tunnel_id not in MAP_DATA.get("technical_tunnels", {}):
                await interaction.response.send_message("❌ Технический тоннель не найден!", ephemeral=True)
                return

            tunnel_data = MAP_DATA["technical_tunnels"][tunnel_id]

            embed = discord.Embed(
                title="🚇 Технический тоннель",
                description=f"**{tunnel_data['name']}**\n{tunnel_data['description']}",
                color=discord.Color.dark_orange()
            )

            destinations = []
            for conn in tunnel_data["connections"]:
                if conn != player.location:
                    station = MAP_DATA["станции"][conn]
                    destinations.append(f"{station['emoji']} **{station['name']}**")

            if destinations:
                embed.add_field(
                    name="📍 Выходы из тоннеля",
                    value="\n".join(destinations),
                    inline=False
                )

            embed.add_field(
                name="🔍 Статус неизвестен",
                value="Нажмите **'Проверить тоннель на заражение'** для получения информации о состоянии тоннеля!",
                inline=False
            )

            view = TechnicalTunnelMenu(tunnel_id, current_station=player.location)
            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🔥 Костёр", style=discord.ButtonStyle.danger)
    async def campfire_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа командой /start", ephemeral=True)
                return
            if not player.is_alive:
                await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)
                return

            location_data = MAP_DATA["станции"][player.location]
            is_dangerous = location_data.get("ruined", False) or location_data.get("danger", 0) >= 3

            # ИСПРАВЛЕНО: используем одно имя переменной rozzhig_count
            rozzhig_count = player.inventory.get('розжиг', 0)
            hlam_count = len(player.inventory.get('хлам', []) or [])

            if rozzhig_count <= 0 and hlam_count <= 0:
                embed = discord.Embed(
                    title="🔥 Костёр",
                    description=(
                        "❌ У вас нет ни розжига, ни хлама для разжигания костра.\n\n"
                        "💡 **Как разжечь костёр:**\n"
                        "• Купите **Розжиг** в торговой зоне (25 никелей)\n"
                        "• Или соберите **хлам** (падает с мутантов)"
                    ),
                    color=discord.Color.dark_red()
                )
                from .campfire import CampfireEmptyMenu
                view = CampfireEmptyMenu()
                await interaction.response.edit_message(embed=embed, view=view)
                return

            if is_dangerous:
                embed = discord.Embed(
                    title="🔥 Опасный костёр",
                    description=(
                        "⚠️ Вы находитесь на **опасной станции**.\n"
                        "🔥 Разведение костра может привлечь мутантов!\n\n"
                        f"🪵 Розжиг: **{rozzhig_count}** шт.\n"
                        f"📦 Хлам: **{hlam_count}** шт.\n\n"
                        "Вы хотите разжечь костёр здесь?"
                    ),
                    color=discord.Color.red()
                )
            else:
                embed = discord.Embed(
                    title="🔥 Костёр",
                    description=(
                        "Вы находитесь у места для костра.\n\n"
                        f"🪵 Розжиг: **{rozzhig_count}** шт.\n"
                        f"📦 Хлам: **{hlam_count}** шт.\n\n"
                        "Вы хотите разжечь костёр здесь?"
                    ),
                    color=discord.Color.orange()
                )

            from .campfire import CampfireStartMenu
            view = CampfireStartMenu(player, is_dangerous)
            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            from utils.logger import get_logger
            get_logger().error(f"Ошибка в campfire_button: {e}", exc_info=True)
            try:
                await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
            except:
                pass

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа командой /start", ephemeral=True)
                return

            station_data = MAP_DATA["станции"][player.location]

            embed = discord.Embed(
                title="🎮 Меню 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
                description=f"Добро пожаловать, **{player.name}**!\nУровень: **{player.level}**",
                color=discord.Color.blue()
            )
            total_hp = player.get_total_health()
            max_hp = player.get_max_total_health()

            embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
            embed.add_field(name="📍 Локация", value=station_data["name"], inline=True)
            embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)

            from .main_menu import MainMenu
            view = MainMenu(player)
            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)