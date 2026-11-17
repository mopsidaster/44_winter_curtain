# -*- coding: utf-8 -*-
# func/views/status.py - Меню статуса (0.4.7.6.1)
#
# ИСТОРИЯ:
#   0.4.3   — базовое
#   0.4.7.6.1 — Инженерия как полноценный навык

import discord
from .helpers import (
    game_manager, BALANCE, MAP_DATA, get_active_effects, current_event,
    GLOBAL_EVENTS_ENABLED, get_event_color, get_event_icon, save_player,
    get_current_filter_info
)
from .skills import SkillsUpgradeView
from ..melee_system import get_melee_weapon


class StatusView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        if not hasattr(self.player, 'skills'):
            from ..player import DEFAULT_SKILLS
            self.player.skills = dict(DEFAULT_SKILLS)

    @discord.ui.button(label="☣️ Заражения", style=discord.ButtonStyle.primary)
    async def diseases_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа!", ephemeral=True)
                return

            from ..disease_system import format_detailed_status
            text = format_detailed_status(player)

            embed = discord.Embed(
                title="☣️ Заражения и болезни",
                description=text,
                color=discord.Color.dark_red()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🌍 Ивент", style=discord.ButtonStyle.primary)
    async def event_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not GLOBAL_EVENTS_ENABLED:
                embed = discord.Embed(
                    title="🌍 Глобальные ивенты",
                    description="Глобальные ивенты отключены в конфигурации.",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if not current_event.active:
                embed = discord.Embed(
                    title="🌍 Глобальные ивенты",
                    description="В данный момент нет активных глобальных ивентов.",
                    color=discord.Color.green()
                )
                active_effects = get_active_effects(game_manager)
                if active_effects:
                    effect_names = {
                        "trade_discount": "🛒 Скидка 20%",
                        "mutant_wave": "💀 Мутанты опаснее",
                        "loot_boost": "📦 +50% опыта и лута",
                        "flood": "🌊 Переходы дороже",
                        "radiation_spike": "☢️ Радиация сильнее",
                        "power_outage": "⚡ Темнота",
                        "shop_sale": "🏪 Скидка 30%",
                        "x2_exp": "⭐ Двойной опыт",
                        "earthquake": "🌍 Переходы заблокированы",
                        "gas_leak": "☠️ Утечка газа",
                        "station_celebration": "🎉 Праздник",
                        "station_fire": "🔥 Пожар",
                        "stalker_workshop": "🔧 Мастерская",
                        "mutant_breach": "🧟 Прорыв"
                    }
                    effects_text = "\n".join([f"• {effect_names.get(e, e)}" for e in active_effects.keys()])
                    embed.add_field(name="💡 Активные эффекты", value=effects_text, inline=False)
                embed.set_footer(text="Следующий ивент скоро начнется")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            event = current_event.event
            color = get_event_color(event["type"])
            icon = get_event_icon(event["type"])

            embed = discord.Embed(
                title=f"{icon} Активный глобальный ивент",
                description=event["text"],
                color=color
            )
            embed.add_field(
                name="⏱️ Осталось времени",
                value=f"{current_event.time_remaining} минут",
                inline=True
            )
            embed.add_field(
                name="📊 Тип",
                value="✅ Бафф" if event["type"] == "buff" else "❌ Дебафф" if event["type"] == "debuff" else "ℹ️ Нейтральный",
                inline=True
            )
            embed.add_field(
                name="💡 Эффект",
                value=event.get("description", "Нет описания"),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(label="📈 Навыки", style=discord.ButtonStyle.success)
    async def skills_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа командой /start", ephemeral=True)
                return
            if not player.is_alive:
                await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)
                return

            engineering_bonus = BALANCE.get('skills', {}).get('engineering_repair_bonus_per_level', 5)

            embed = discord.Embed(
                title="📈 Прокачка навыков",
                description=f"**{player.name}**, у вас есть **{player.skill_points}** очков навыков!",
                color=discord.Color.blue()
            )
            embed.add_field(name="💪 Сила", value=f"{player.skills.get('сила', 0)}/10\n+Урон в ближнем бою", inline=True)
            embed.add_field(name="🎯 Меткость", value=f"{player.skills.get('меткость', 0)}/10\n+Точность стрельбы", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.skills.get('выносливость', 0)}/10\n+Макс. выносливость", inline=True)
            embed.add_field(name="🛡️ Стойкость", value=f"{player.skills.get('стойкость', 0)}/10\n+Защита, -Урон", inline=True)
            embed.add_field(name="❤️ Здоровье", value=f"{player.skills.get('здоровье', 0)}/10\n+HP, +Иммунитет", inline=True)
            embed.add_field(
                name="🔧 Инженерия",
                value=f"{player.skills.get('инженерия', 0)}/10\n+{engineering_bonus}% шанс ремонта",
                inline=True
            )
            embed.add_field(name="🎯 Осталось очков", value=str(player.skill_points), inline=False)

            view = SkillsUpgradeView(player)
            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

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

            total_health = player.get_total_health()
            max_health = player.get_max_total_health()

            embed.add_field(name="❤️ Здоровье", value=f"{total_health:.1f}/{max_health:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
            embed.add_field(name="📍 Локация", value=station_data["name"], inline=True)
            embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)

            from .main_menu import MainMenu
            view = MainMenu(player)
            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)