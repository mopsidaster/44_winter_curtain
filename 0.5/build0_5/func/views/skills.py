# -*- coding: utf-8 -*-
# func/views/skills.py - Меню навыков (0.4.8.2)
#
# ИСТОРИЯ:
#   0.4.8.2 — ФИКС: кнопка "Завершить" больше не вызывает Interaction Failed.
#             ФИКС: убран вызов get_max_lives (устаревший метод).
#             Возвращен класс SkillsUpgradeView для меню /status.

import discord
from .helpers import BALANCE, save_player
from utils.logger import get_logger

logger = get_logger()


class SkillsView(discord.ui.View):
    """Меню распределения навыков при создании персонажа."""
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.max_level = BALANCE['skills']['max_level']

    def _spent_points(self) -> int:
        return sum(v for k, v in self.player.skills.items())

    def _total_points(self) -> int:
        return BALANCE['skills']['start_points'] + (self.player.level - 1)

    async def update_display(self, interaction: discord.Interaction):
        total_points = self._total_points()
        spent_points = self._spent_points()
        remaining = total_points - spent_points

        embed = discord.Embed(
            title="🎯 Распределение навыков",
            description=f"**{self.player.name}**, у вас есть **{total_points} очков навыков**!\n"
                        f"Распределите их между характеристиками:",
            color=discord.Color.blue()
        )

        s = self.player.skills
        ml = self.max_level
        endurance_bonus = BALANCE['skills'].get('endurance_stamina_bonus', 2)
        base_stamina = BALANCE['player'].get('base_stamina', 10)
        engineering_bonus = BALANCE.get('skills', {}).get('engineering_repair_bonus_per_level', 5)

        strength_bar = "█" * s["сила"] + "░" * (ml - s["сила"])
        accuracy_bar = "█" * s["меткость"] + "░" * (ml - s["меткость"])
        endurance_bar = "█" * s["выносливость"] + "░" * (ml - s["выносливость"])
        toughness_bar = "█" * s["стойкость"] + "░" * (ml - s["стойкость"])
        health_bar = "█" * s["здоровье"] + "░" * (ml - s["здоровье"])
        engineering_bar = "█" * s.get("инженерия", 0) + "░" * (ml - s.get("инженерия", 0))

        embed.add_field(
            name="💪 Сила",
            value=f"{strength_bar} {s['сила']}/{ml}\n"
                  f"➜ Урон в ближнем бою +1% | Точность удара +2% | Шанс оглушения +1%",
            inline=False
        )
        embed.add_field(
            name="🎯 Меткость",
            value=f"{accuracy_bar} {s['меткость']}/{ml}\n"
                  f"➜ Точность стрельбы +2% | Точность в голову +1%",
            inline=False
        )
        embed.add_field(
            name="🏃 Выносливость",
            value=f"{endurance_bar} {s['выносливость']}/{ml}\n"
                  f"➜ Макс. выносливость: **{base_stamina + s['выносливость'] * endurance_bonus}**",
            inline=False
        )
        embed.add_field(
            name="🛡️ Стойкость",
            value=f"{toughness_bar} {s['стойкость']}/{ml}\n"
                  f"➜ Защита при блоке +2% | Падения -10% | Получаемый урон -2.5%",
            inline=False
        )
        embed.add_field(
            name="❤️ Здоровье",
            value=f"{health_bar} {s['здоровье']}/{ml}\n"
                  f"➜ HP частей +1 | Иммунитет -5% шанс заболеть",
            inline=False
        )
        embed.add_field(
            name="🔧 Инженерия",
            value=f"{engineering_bar} {s.get('инженерия', 0)}/{ml}\n"
                  f"➜ Шанс ремонта изолентой +{engineering_bonus}% за уровень",
            inline=False
        )
        embed.add_field(
            name="🎯 Осталось очков",
            value=str(remaining),
            inline=False
        )

        self.clear_items()

        if remaining > 0:
            if s["сила"] < ml: self.add_item(self.add_strength)
            if s["меткость"] < ml: self.add_item(self.add_accuracy)
            if s["выносливость"] < ml: self.add_item(self.add_endurance)
            if s["стойкость"] < ml: self.add_item(self.add_toughness)
            if s["здоровье"] < ml: self.add_item(self.add_health)
            if s.get("инженерия", 0) < ml: self.add_item(self.add_engineering)

            embed.add_field(
                name="⚠️ Осталось распределить",
                value=f"Осталось **{remaining}** очков!",
                inline=False
            )

        if remaining == 0:
            self.add_item(self.finish)
            embed.add_field(
                name="✅ Готово!",
                value="Нажмите 'Завершить' чтобы начать игру",
                inline=False
            )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💪 + Сила", style=discord.ButtonStyle.primary)
    async def add_strength(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._total_points() - self._spent_points() <= 0 or self.player.skills["сила"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["сила"] += 1
        await self.update_display(interaction)

    @discord.ui.button(label="🎯 + Меткость", style=discord.ButtonStyle.primary)
    async def add_accuracy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._total_points() - self._spent_points() <= 0 or self.player.skills["меткость"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["меткость"] += 1
        await self.update_display(interaction)

    @discord.ui.button(label="🏃 + Выносливость", style=discord.ButtonStyle.success)
    async def add_endurance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._total_points() - self._spent_points() <= 0 or self.player.skills["выносливость"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["выносливость"] += 1
        self.player.recalc_max_stamina()
        self.player.stamina = self.player.max_stamina
        await self.update_display(interaction)

    @discord.ui.button(label="🛡️ + Стойкость", style=discord.ButtonStyle.secondary)
    async def add_toughness(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._total_points() - self._spent_points() <= 0 or self.player.skills["стойкость"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["стойкость"] += 1
        await self.update_display(interaction)

    @discord.ui.button(label="❤️ + Здоровье", style=discord.ButtonStyle.danger)
    async def add_health(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._total_points() - self._spent_points() <= 0 or self.player.skills["здоровье"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["здоровье"] += 1
        self.player.recalc_body_parts_max_hp()
        self.player.restore_full_health()
        await self.update_display(interaction)

    @discord.ui.button(label="🔧 + Инженерия", style=discord.ButtonStyle.success)
    async def add_engineering(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._total_points() - self._spent_points() <= 0 or self.player.skills.get("инженерия", 0) >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["инженерия"] = self.player.skills.get("инженерия", 0) + 1
        await self.update_display(interaction)

    @discord.ui.button(label="✅ Завершить", style=discord.ButtonStyle.danger)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        remaining = self._total_points() - self._spent_points()
        if remaining > 0:
            await interaction.response.send_message(f"❌ Осталось {remaining} очков!", ephemeral=True)
            return

        # Не делаем defer, так как сразу отредактируем сообщение
        try:
            self.player.skill_points = 0
            self.player.is_new = False

            # 0.4.8.2 ФИКС: используем get_max_total_health() вместо удаленного get_max_lives()
            self.player.max_lives = self.player.get_max_total_health()

            await save_player(self.player)

            # Пытаемся запустить Пролог
            from .prologue import PrologueView, build_scene_embed
            prologue_view = PrologueView(self.player.user_id, scene_num=1)
            prologue_embed = build_scene_embed(1, self.player)

            await interaction.response.edit_message(embed=prologue_embed, view=prologue_view)

        except Exception as e:
            logger.error(f"[Skills] Ошибка при запуске пролога: {e}", exc_info=True)

            # Если Пролог сломался, перекидываем игрока в Главное меню
            try:
                from .main_menu import MainMenu
                from ..map_data import MAP_DATA

                station_data = MAP_DATA["станции"].get(self.player.location, {})
                embed = discord.Embed(
                    title="🎮 Меню 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
                    description=f"Добро пожаловать, **{self.player.name}**!",
                    color=discord.Color.blue()
                )
                embed.add_field(name="📍 Локация", value=station_data.get("name", "?"), inline=True)

                await interaction.response.edit_message(embed=embed, view=MainMenu())
            except Exception as e2:
                logger.error(f"[Skills] Критическая ошибка при возврате в меню: {e2}", exc_info=True)
                # Если уже не можем ответить через response, пробуем followup
                try:
                    await interaction.followup.send(f"❌ Критическая ошибка: {e2}", ephemeral=True)
                except:
                    pass


class SkillsUpgradeView(discord.ui.View):
    """0.4.7.8.1: Прокачка навыков на экране статуса (после повышения уровня)."""

    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.max_level = BALANCE['skills']['max_level']

    async def update_display(self, interaction: discord.Interaction):
        s = self.player.skills
        ml = self.max_level
        endurance_bonus = BALANCE['skills'].get('endurance_stamina_bonus', 2)
        base_stamina = BALANCE['player'].get('base_stamina', 10)
        engineering_bonus = BALANCE.get('skills', {}).get('engineering_repair_bonus_per_level', 5)

        embed = discord.Embed(
            title="📈 Прокачка навыков",
            description=f"**{self.player.name}**, у вас есть **{self.player.skill_points}** очков навыков!",
            color=discord.Color.blue()
        )

        embed.add_field(name="💪 Сила", value=f"{s['сила']}/{ml}\n+Урон в ближнем бою", inline=True)
        embed.add_field(name="🎯 Меткость", value=f"{s['меткость']}/{ml}\n+Точность стрельбы", inline=True)
        embed.add_field(
            name="🏃 Выносливость",
            value=f"{s['выносливость']}/{ml}\nМакс: **{base_stamina + s['выносливость'] * endurance_bonus}**",
            inline=True
        )
        embed.add_field(name="🛡️ Стойкость", value=f"{s['стойкость']}/{ml}\n+Защита, -Урон", inline=True)
        embed.add_field(name="❤️ Здоровье", value=f"{s['здоровье']}/{ml}\n+HP, +Иммунитет", inline=True)
        embed.add_field(
            name="🔧 Инженерия",
            value=f"{s.get('инженерия', 0)}/{ml}\n+{engineering_bonus}% шанс ремонта",
            inline=True
        )
        embed.add_field(name="🎯 Осталось очков", value=str(self.player.skill_points), inline=False)

        total_health = self.player.get_total_health()
        max_health = self.player.get_max_total_health()
        embed.add_field(
            name="📊 Текущее здоровье",
            value=f"{total_health:.1f}/{max_health:.1f}",
            inline=False
        )

        self.clear_items()

        if self.player.skill_points > 0:
            if s["сила"] < ml: self.add_item(self.add_strength)
            if s["меткость"] < ml: self.add_item(self.add_accuracy)
            if s["выносливость"] < ml: self.add_item(self.add_endurance)
            if s["стойкость"] < ml: self.add_item(self.add_toughness)
            if s["здоровье"] < ml: self.add_item(self.add_health)
            if s.get("инженерия", 0) < ml: self.add_item(self.add_engineering)

        self.add_item(self.back_button)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💪 + Сила", style=discord.ButtonStyle.primary)
    async def add_strength(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.skill_points <= 0 or self.player.skills["сила"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["сила"] += 1
        self.player.skill_points -= 1
        await self.update_display(interaction)
        await save_player(self.player)

    @discord.ui.button(label="🎯 + Меткость", style=discord.ButtonStyle.primary)
    async def add_accuracy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.skill_points <= 0 or self.player.skills["меткость"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["меткость"] += 1
        self.player.skill_points -= 1
        await self.update_display(interaction)
        await save_player(self.player)

    @discord.ui.button(label="🏃 + Выносливость", style=discord.ButtonStyle.success)
    async def add_endurance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.skill_points <= 0 or self.player.skills["выносливость"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["выносливость"] += 1
        self.player.skill_points -= 1
        self.player.recalc_max_stamina()
        self.player.stamina = self.player.max_stamina
        await self.update_display(interaction)
        await save_player(self.player)

    @discord.ui.button(label="🛡️ + Стойкость", style=discord.ButtonStyle.secondary)
    async def add_toughness(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.skill_points <= 0 or self.player.skills["стойкость"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["стойкость"] += 1
        self.player.skill_points -= 1
        await self.update_display(interaction)
        await save_player(self.player)

    @discord.ui.button(label="❤️ + Здоровье", style=discord.ButtonStyle.danger)
    async def add_health(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.skill_points <= 0 or self.player.skills["здоровье"] >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["здоровье"] += 1
        self.player.skill_points -= 1
        self.player.recalc_body_parts_max_hp()
        self.player.restore_full_health()
        await self.update_display(interaction)
        await save_player(self.player)

    @discord.ui.button(label="🔧 + Инженерия", style=discord.ButtonStyle.success)
    async def add_engineering(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.skill_points <= 0 or self.player.skills.get("инженерия", 0) >= self.max_level:
            await interaction.response.send_message("❌ Нельзя!", ephemeral=True)
            return
        self.player.skills["инженерия"] = self.player.skills.get("инженерия", 0) + 1
        self.player.skill_points -= 1
        await self.update_display(interaction)
        await save_player(self.player)

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            from .main_menu import MainMenu
            from ..map_data import MAP_DATA as _MAP_DATA
            from .helpers import game_manager

            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Игрок не найден!", ephemeral=True)
                return

            station_data = _MAP_DATA["станции"][player.location]
            total_hp = player.get_total_health()
            max_hp = player.get_max_total_health()

            embed = discord.Embed(
                title="🎮 Меню 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
                description=f"Добро пожаловать, **{player.name}**!\nУровень: **{player.level}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
            embed.add_field(name="📍 Локация", value=station_data["name"], inline=True)
            embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)

            view = MainMenu(player)
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
            except:
                pass