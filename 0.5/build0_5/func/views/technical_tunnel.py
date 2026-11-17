# -*- coding: utf-8 -*-
# func/views/technical_tunnel.py - Меню технического тоннеля (0.4.7.5)
#
# ИСТОРИЯ:
#   0.4.2.8 — базовое меню
#   0.4.7.3 — после успешного перехода открываем MainMenu
#   0.4.7.5 — исключаем текущую станцию из списка выходов;
#             защита от 'contaminated' KeyError

import discord
import random
from .helpers import (
    game_manager, MAP_DATA, can_move, save_player, BALANCE,
    get_stamina_multiplier, check_tunnel, get_tunnel_zone_type,
    check_tunnel_contamination, enter_technical_tunnel
)


class TechnicalTunnelMenu(discord.ui.View):
    def __init__(self, tunnel_id: str, current_station: str = None):
        super().__init__(timeout=60)
        self.tunnel_id = tunnel_id
        self.current_station = current_station
        self.used = False

        tunnel_data = MAP_DATA["technical_tunnels"][tunnel_id]

        check_button = discord.ui.Button(
            label="🔍 Проверить тоннель на заражение",
            style=discord.ButtonStyle.secondary,
            custom_id="check_tunnel"
        )
        check_button.callback = self.check_callback
        self.add_item(check_button)

        # 0.4.7.5: исключаем текущую станцию
        for conn in tunnel_data["connections"]:
            if current_station and conn == current_station:
                continue

            station = MAP_DATA["станции"][conn]
            button = discord.ui.Button(
                label=f"{station['emoji']} {station['name']}",
                style=discord.ButtonStyle.success,
                custom_id=f"tunnel_{conn}"
            )
            button.callback = self.create_callback(conn)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def check_callback(self, interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)

            info = check_tunnel(self.tunnel_id)
            if not info or not info.get("exists", False):
                await interaction.response.send_message(
                    "❌ Тоннель не найден.", ephemeral=True
                )
                return

            zone_type = info.get("zone_type", "mixed")
            contaminated = info.get("contaminated", False)

            zone_descriptions = {
                "безопасные": "🌿 Спокойная местность, радиационный фон в норме",
                "mixed": "⚠️ Нестабильная зона, показатели скачут",
                "опасные": "☢️ Критическая зона, высокий уровень радиации"
            }

            if contaminated:
                status_text = "☢️ **ЗАГРЯЗНЕН** - Противогаз обязателен!"
                status_color = "🔴"
                status_emoji = "☢️"
            else:
                status_text = "✅ **ЧИСТ** - Проход безопасен."
                status_color = "🟢"
                status_emoji = "✅"

            if contaminated:
                rad_level = random.randint(60, 99)
                if zone_type == "опасные":
                    rad_level = random.randint(80, 120)
            else:
                rad_level = random.randint(0, 15)
                if zone_type == "безопасные":
                    rad_level = random.randint(0, 8)

            embed = discord.Embed(
                title="📟 Результаты радиационной разведки",
                description=f"**{MAP_DATA['technical_tunnels'][self.tunnel_id]['name']}**",
                color=discord.Color.blue()
            )
            embed.add_field(name=f"{status_emoji} Состояние", value=f"{status_color} {status_text}", inline=False)
            embed.add_field(name="🌍 Радиационный фон", value=f"{rad_level} мкЗв/ч", inline=True)
            embed.add_field(name="📍 Зона", value=zone_descriptions.get(zone_type, "❓"), inline=False)

            if contaminated:
                embed.add_field(name="⚠️ Рекомендация", value="Используйте противогаз с фильтром!", inline=False)
            else:
                embed.add_field(name="✅ Рекомендация", value="Тоннель безопасен.", inline=False)

            if player:
                total_health = player.get_total_health()
                max_health = player.get_max_total_health()
                embed.add_field(name="❤️ Ваше здоровье", value=f"{total_health:.1f}/{max_health:.1f}", inline=True)

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка проверки: {str(e)}", ephemeral=True)

    def create_callback(self, destination: str):
        async def callback(interaction: discord.Interaction):
            if self.used:
                await interaction.response.send_message("❌ Уже сделан выбор!", ephemeral=True)
                return
            self.used = True

            try:
                player = game_manager.get_player(interaction.user.id)
                if not player:
                    await interaction.response.send_message("❌ Персонаж не найден!", ephemeral=True)
                    return

                if not can_move(game_manager):
                    await interaction.response.send_message("🌍 Землетрясение! Переходы заблокированы!", ephemeral=True)
                    return

                if destination == player.location:
                    await interaction.response.send_message(
                        "❌ Нельзя перейти в тоннель на ту же станцию!", ephemeral=True
                    )
                    self.used = False
                    return

                stamina_mult = get_stamina_multiplier(game_manager)
                stamina_cost = BALANCE['player']['stamina_per_move'] * 1.5 * stamina_mult
                if player.stamina < stamina_cost:
                    await interaction.response.send_message(f"❌ Нет выносливости! Нужно {stamina_cost:.1f}.", ephemeral=True)
                    self.used = False
                    return

                result = await enter_technical_tunnel(
                    player, self.tunnel_id, destination, game_manager, interaction
                )

                await save_player(player)

                if "погиб" in result:
                    await interaction.response.send_message(result, ephemeral=True)
                    try:
                        await interaction.message.delete()
                    except Exception:
                        pass
                    return

                if "Бой" in result or "бой" in result.lower():
                    await interaction.response.send_message(result, ephemeral=True)
                    try:
                        await interaction.message.delete()
                    except Exception:
                        pass
                    return

                from .main_menu import MainMenu
                from ..map_data import MAP_DATA as _MAP_DATA

                station_data = _MAP_DATA["станции"][player.location]
                total_hp = player.get_total_health()
                max_hp = player.get_max_total_health()

                embed = discord.Embed(
                    title="🚇 Переход через тоннель",
                    description=result,
                    color=discord.Color.dark_orange()
                )
                embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
                embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
                embed.add_field(name="📍 Локация", value=station_data["name"], inline=True)

                view = MainMenu(player)
                await interaction.response.edit_message(embed=embed, view=view)

            except Exception as e:
                self.used = False
                await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        from .look_around import LookAroundMenu
        from .helpers import game_manager

        player = game_manager.get_player(interaction.user.id)
        if not player:
            await interaction.response.send_message("❌ Ошибка!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔍 Осмотреться",
            description="Что вы хотите сделать?",
            color=discord.Color.blue()
        )
        view = LookAroundMenu()

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)