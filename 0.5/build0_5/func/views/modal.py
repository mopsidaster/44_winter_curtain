# -*- coding: utf-8 -*-
# func/views/modal.py - Модальные окна (0.4.7.1)
#
# ИСТОРИЯ:
#   0.4.2.10 — оптимизация
#   0.4.7    — модалка ввода ключа доступа
#   0.4.7.1  — вторая модалка открывается через кнопку (нельзя две подряд)

import discord
from .helpers import game_manager, BALANCE, save_player
from database.db import activate_access_key, get_access_key
from utils.logger import get_logger

logger = get_logger()


class AccessKeyModal(discord.ui.Modal, title="🔐 Введите ключ доступа"):
    """0.4.7: модалка для ввода ключа доступа."""

    key = discord.ui.TextInput(
        label="Ключ доступа",
        placeholder="MTR-XXXX-XXXX",
        min_length=5,
        max_length=30,
        required=True,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            key_value = self.key.value.strip().upper()

            ok, reason = await activate_access_key(key_value, interaction.user.id)
            if not ok:
                logger.warning(
                    f"[KEY] Игрок {interaction.user.id} не смог активировать ключ "
                    f"'{key_value}': {reason}"
                )
                await interaction.response.send_message(reason, ephemeral=True)
                return

            logger.info(f"[KEY] Игрок {interaction.user.id} активировал ключ '{key_value}'")

            # 0.4.7.1: нельзя открыть вторую модалку сразу — показываем кнопку
            embed = discord.Embed(
                title="✅ Ключ принят!",
                description=(
                    "🔓 Доступ к 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍 открыт.\n\n"
                    "Нажмите кнопку ниже, чтобы создать персонажа."
                ),
                color=discord.Color.green(),
            )
            view = CreateCharacterButtonView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"[KEY] Ошибка в AccessKeyModal: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    f"❌ Ошибка: {str(e)}", ephemeral=True
                )
            except:
                pass


class CreateCharacterButtonView(discord.ui.View):
    """0.4.7.1: кнопка для открытия модалки создания персонажа."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🌆 Создать персонажа", style=discord.ButtonStyle.success)
    async def create_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.response.is_done():
                return
            await interaction.response.send_modal(CreateCharacterModal())
        except discord.errors.NotFound:
            logger.warning(
                f"[KEY] Interaction истёк при создании персонажа у {interaction.user.id}"
            )
        except Exception as e:
            logger.error(f"[KEY] Ошибка в CreateCharacterButtonView: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    f"❌ Ошибка: {str(e)}", ephemeral=True
                )
            except:
                pass


class CreateCharacterModal(discord.ui.Modal, title="🌆 Создание персонажа 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍"):
    name = discord.ui.TextInput(
        label="Имя персонажа",
        placeholder="Введите Ф.И.О или позывной",
        min_length=1,
        max_length=50,
        required=True,
        style=discord.TextStyle.short
    )

    backstory = discord.ui.TextInput(
        label="Краткая предыстория (необязательно)",
        placeholder="Расскажите кратко о своем персонаже...",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            from .skills import SkillsView

            name = self.name.value
            backstory = self.backstory.value or "Без предыстории"

            player = game_manager.add_player(
                interaction.user.id,
                interaction.user.display_name,
                name
            )
            player.backstory = backstory

            embed = discord.Embed(
                title="✅ Персонаж создан!",
                description=f"**{name}**, добро пожаловать в 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍!",
                color=discord.Color.green()
            )

            total_health = player.get_total_health()
            max_health = player.get_max_total_health()

            embed.add_field(name="📝 Имя", value=name, inline=True)
            embed.add_field(
                name="📖 Предыстория",
                value=backstory[:100] + "..." if len(backstory) > 100 else backstory,
                inline=False
            )
            embed.add_field(name="❤️ Здоровье", value=f"{total_health:.1f}/{max_health:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value="10/10", inline=True)
            embed.add_field(name="💰 Никели", value=str(BALANCE['player']['start_gold']), inline=True)
            embed.add_field(
                name="🎒 Противогаз",
                value=f"🟡 Поношенный (прочность: {BALANCE['gas_mask']['worn_durability']})",
                inline=True
            )
            embed.set_footer(text="Теперь распределите навыки!")

            await interaction.response.send_message(embed=embed, ephemeral=True)

            embed_skills = discord.Embed(
                title="🎯 Распределение навыков",
                description=(
                    f"**{name}**, у вас есть **{BALANCE['skills']['start_points']} очков навыков**!\n"
                    f"Распределите их между характеристиками:\n\n"
                    f"💪 **Сила** - урон в рукопашной + шанс найти еду\n"
                    f"🎯 **Меткость** - точность стрельбы (+{BALANCE['skills']['accuracy_per_level']}% за уровень)\n"
                    f"🏃 **Выносливость** - максимальная выносливость\n"
                    f"🛡️ **Стойкость** - снижение получаемого урона (-{BALANCE['skills']['toughness_per_level']}% за уровень) и шанса падений\n"
                    f"❤️ **Здоровье** - максимальное здоровье (+{BALANCE['skills']['health_per_level']} HP за уровень)\n\n"
                    f"Максимальный уровень навыков: **{BALANCE['skills']['max_level']}**"
                ),
                color=discord.Color.blue()
            )
            embed_skills.add_field(name="💪 Сила", value="0/10", inline=True)
            embed_skills.add_field(name="🎯 Меткость", value="0/10", inline=True)
            embed_skills.add_field(name="🏃 Выносливость", value="0/10", inline=True)
            embed_skills.add_field(name="🛡️ Стойкость", value="0/10", inline=True)
            embed_skills.add_field(name="❤️ Здоровье", value="0/10", inline=True)
            embed_skills.add_field(
                name="🎯 Осталось очков",
                value=str(BALANCE['skills']['start_points']),
                inline=False
            )

            view = SkillsView(player)

            await interaction.followup.send(embed=embed_skills, view=view, ephemeral=True)

            await save_player(player)

        except Exception as e:
            logger.error(f"Ошибка в CreateCharacterModal: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    f"❌ Ошибка: {str(e)}", ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        f"❌ Ошибка: {str(e)}", ephemeral=True
                    )
                except:
                    pass