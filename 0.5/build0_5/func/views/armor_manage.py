# -*- coding: utf-8 -*-
# func/views/armor_manage.py - Управление экипировкой (Билд 0.4.3)
#
# Надеть / снять / посмотреть состояние брони и шлема.

import discord
import uuid
from .helpers import game_manager, save_player
from ..armor_system import (
    get_armor_item,
    is_full_set,
    get_active_set,
    format_armor_status,
)


class ArmorManageMenu(discord.ui.View):
    """Управление экипировкой."""
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🧥 Снаряжение",
            description="Управление бронёй и шлемом",
            color=discord.Color.blue()
        )

        # Текущий комплект
        embed.add_field(
            name="📦 Надето",
            value=format_armor_status(self.player),
            inline=False
        )

        # Инвентарь брони
        inv = self.player.armor_inventory
        if inv:
            lines = []
            for item_id in inv:
                item = get_armor_item(item_id)
                if not item:
                    continue
                slot_name = "🧥 Броня" if item.get('slot') == 'armor' else "⛑️ Шлем"
                lines.append(f"{slot_name}: {item.get('emoji', '')} {item.get('name', item_id)}")
            embed.add_field(
                name=f"🎒 В рюкзаке ({len(inv)})",
                value="\n".join(lines[:10]),
                inline=False
            )
        else:
            embed.add_field(
                name="🎒 В рюкзаке",
                value="Нет запасной брони или шлемов",
                inline=False
            )

        return embed

    @discord.ui.button(label="🧥 Надеть броню", style=discord.ButtonStyle.success)
    async def equip_armor_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        available = [
            item_id for item_id in self.player.armor_inventory
            if get_armor_item(item_id).get('slot') == 'armor'
        ]

        if not available:
            await interaction.response.send_message(
                "❌ У вас нет запасной брони в рюкзаке!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🧥 Выберите броню",
            description="Надеть на слот «броня»:",
            color=discord.Color.green()
        )
        for item_id in available:
            item = get_armor_item(item_id)
            embed.add_field(
                name=f"{item.get('emoji', '')} {item.get('name', item_id)}",
                value=(
                    f"🛡️ Противоудар: {item.get('impact_protection', 0)}% | "
                    f"Броня: {item.get('armor_protection', 0)}%\n"
                    f"🎯 Зоны: {', '.join(item.get('zones', []))}"
                ),
                inline=False
            )

        view = ArmorEquipSelect(self.player, 'armor', available)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="⛑️ Надеть шлем", style=discord.ButtonStyle.success)
    async def equip_helmet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        available = [
            item_id for item_id in self.player.armor_inventory
            if get_armor_item(item_id).get('slot') == 'helmet'
        ]

        if not available:
            await interaction.response.send_message(
                "❌ У вас нет запасных шлемов в рюкзаке!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⛑️ Выберите шлем",
            description="Надеть на слот «шлем»:",
            color=discord.Color.green()
        )
        for item_id in available:
            item = get_armor_item(item_id)
            embed.add_field(
                name=f"{item.get('emoji', '')} {item.get('name', item_id)}",
                value=(
                    f"🛡️ Противоудар: {item.get('impact_protection', 0)}% | "
                    f"Броня: {item.get('armor_protection', 0)}%"
                ),
                inline=False
            )

        view = ArmorEquipSelect(self.player, 'helmet', available)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🧥 Снять броню", style=discord.ButtonStyle.danger)
    async def unequip_armor_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        if not self.player.armor:
            await interaction.response.send_message("❌ Броня не надета!", ephemeral=True)
            return

        await interaction.response.defer()
        success, msg = self.player.unequip_armor_item('armor')
        await save_player(self.player)

        embed = self._build_embed()
        embed.add_field(name="✅ Результат" if success else "❌ Ошибка", value=msg, inline=False)
        view = ArmorManageMenu(self.player)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            pass

    @discord.ui.button(label="⛑️ Снять шлем", style=discord.ButtonStyle.danger)
    async def unequip_helmet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        if not self.player.helmet:
            await interaction.response.send_message("❌ Шлем не надет!", ephemeral=True)
            return

        await interaction.response.defer()
        success, msg = self.player.unequip_armor_item('helmet')
        await save_player(self.player)

        embed = self._build_embed()
        embed.add_field(name="✅ Результат" if success else "❌ Ошибка", value=msg, inline=False)
        view = ArmorManageMenu(self.player)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            pass

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .action_menu import ActionMenu
        embed = discord.Embed(
            title="🎯 Действия",
            description="Выберите действие:",
            color=discord.Color.blue()
        )
        view = ActionMenu()
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)


class ArmorEquipSelect(discord.ui.View):
    """Выбор предмета для надевания."""
    def __init__(self, player, slot: str, available: list):
        super().__init__(timeout=120)
        self.player = player
        self.slot = slot
        self.available = available
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        for idx, item_id in enumerate(self.available[:5]):
            item = get_armor_item(item_id)
            button = discord.ui.Button(
                label=f"{item.get('emoji', '')} {item.get('name', item_id)}"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"arm_eq_{self.menu_id}_{idx}"
            )
            button.callback = self.create_callback(item_id)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"arm_eq_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, item_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            success, msg = self.player.equip_armor_item(item_id)
            await save_player(self.player)

            embed = discord.Embed(
                title="✅ Надето" if success else "❌ Ошибка",
                description=msg,
                color=discord.Color.green() if success else discord.Color.red()
            )

            view = ArmorManageMenu(self.player)
            # Заменяем embed на статус экипировки
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception:
                pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🧥 Снаряжение",
            description="Управление бронёй и шлемом",
            color=discord.Color.blue()
        )
        view = ArmorManageMenu(self.player)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)