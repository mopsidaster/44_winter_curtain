# -*- coding: utf-8 -*-
# func/views/weapon_shop/main_menu.py - Главное меню оружейного магазина (0.4.8 Оптимизация)
#
# ИСТОРИЯ:
#   0.4.4.6 — рефакторинг
#   0.4.6.2 — MagazineBuyMenu (категории)
#   0.4.7.6.1 — фикс buy_melee
#   0.4.8 — ОПТИМИЗАЦИЯ: убран ручной перебор оружия ближнего боя,
#           теперь используется готовый MeleeBuyMenu.build_embed().

import discord
import uuid

from ..helpers import game_manager, WEAPONS, get_trade_discount
from ...factions import get_station_discount
from utils.logger import get_logger

from .consumables import ConsumablesMenu
from .weapon_types import WeaponTypeMenu
from .modules import ModuleSlotMenu
from .magazines import MagazineBuyMenu
from .melee import MeleeBuyMenu

logger = get_logger()


def _get_faction_discount(player) -> float:
    """0.4.8: скидка фракции на текущей станции."""
    try:
        return get_station_discount(player, player.location)
    except Exception:
        return 1.0


class WeaponShopMainMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="🔫 Оружие", style=discord.ButtonStyle.primary, row=0)
    async def buy_weapons(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        view = WeaponTypeMenu(self.player, current_page="pistol")
        embed = view.get_embed("pistol")

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit (оружие): {e}")

    @discord.ui.button(label="📀 Магазины", style=discord.ButtonStyle.primary, row=0)
    async def buy_magazines(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        view = MagazineBuyMenu(self.player)
        embed = MagazineBuyMenu.build_embed(self.player)

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit (магазины): {e}")

    @discord.ui.button(label="🎯 Патроны", style=discord.ButtonStyle.primary, row=0)
    async def buy_ammo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        from ..ammo import AmmoCategoriesMenu
        embed = AmmoCategoriesMenu.build_embed(self.player)
        view = AmmoCategoriesMenu(self.player)

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit (патроны): {e}")

    @discord.ui.button(label="🔧 Модификации", style=discord.ButtonStyle.success, row=1)
    async def buy_modules(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        view = ModuleSlotMenu(self.player, current_slot="scope")
        embed = view.get_embed("scope")

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit (модификации): {e}")

    @discord.ui.button(label="🗡️ Ближний бой", style=discord.ButtonStyle.danger, row=1)
    async def buy_melee(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        # 0.4.8 ОПТИМИЗАЦИЯ: Используем готовый класс MeleeBuyMenu
        view = MeleeBuyMenu(self.player)
        embed = view.build_embed()

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit (ближний бой): {e}")

    @discord.ui.button(label="💣 Расходники", style=discord.ButtonStyle.success, row=1)
    async def buy_consumables(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        embed = discord.Embed(
            title="💣 Расходники",
            description="Выберите категорию:",
            color=discord.Color.orange()
        )
        embed.add_field(name="📋 Разделы", value="• 💣 **Гранаты**\n• 🔪 **Метательные ножи**", inline=False)
        embed.set_footer(text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)}")

        view = ConsumablesMenu(self.player)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit (расходники): {e}")

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        from ..trade import build_trade_view, _build_trade_page_embed
        view = build_trade_view(self.player, 2)
        embed = _build_trade_page_embed(self.player, 2)

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка возврата в торговлю: {e}")