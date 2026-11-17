# -*- coding: utf-8 -*-
# func/views/trade/page1.py - Универсальная торговля: Купить (0.4.9.0 Visual)

import discord

from ._helpers import (
    _safe_defer, _safe_edit, _safe_followup, _build_workshop_embed,
)
from .pagination import _TradePaginationMixin
from ..helpers import (
    game_manager, save_player, get_trade_discount, get_food,
)
from ...station_utils import is_trade_station
from ...factions import (
    get_station_discount, has_workshop_on_station,
    get_station_faction, get_player_loyalty_level,
)
from utils.logger import get_logger

logger = get_logger()


def _get_faction_discount(player) -> float:
    try:
        return get_station_discount(player, player.location)
    except Exception:
        return 1.0


class TradePage1Menu(_TradePaginationMixin, discord.ui.View):
    """Универсальная вкладка «Купить»."""

    def __init__(self, player):
        super().__init__(timeout=180)
        self.player = player
        self.page = 1

    @discord.ui.button(label="Аптека", emoji="💊", style=discord.ButtonStyle.success, row=0)
    async def pharmacy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        if interaction.user.id != self.player.user_id:
            return await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)

        from ..pharmacy import PharmacyMenu
        embed = discord.Embed(
            title="💊 АПТЕКА",
            description="> *Жизнь дороже никелей.*\n━━━━━━━━━━━━━━━━━━",
            color=discord.Color.green()
        )
        embed.add_field(
            name="🏥 Разделы:",
            value="• 💊 **Товары** — АИ-2, Подсумок, Антирад, Аспирин\n• 👨‍⚕️ **Врач** — Лечение болезней",
            inline=False
        )
        view = PharmacyMenu(self.player)
        await _safe_edit(interaction, embed=embed, view=view)

    @discord.ui.button(label="Мастерская", emoji="🔧", style=discord.ButtonStyle.primary, row=0)
    async def workshop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        if interaction.user.id != self.player.user_id:
            return await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)

        if not has_workshop_on_station(self.player, self.player.location):
            return await _safe_followup(interaction, content="🔒 Мастерская закрыта (нужна лояльность 1+).", ephemeral=True)

        embed = _build_workshop_embed(self.player)
        from .workshop import WorkshopMenu
        view = WorkshopMenu(self.player)
        await _safe_edit(interaction, embed=embed, view=view)

    @discord.ui.button(label="Еда", emoji="🍖", style=discord.ButtonStyle.success, row=1)
    async def food_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        if interaction.user.id != self.player.user_id:
            return await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)

        from ..food import FoodBuyMenu
        embed = discord.Embed(
            title="🍖 ПРОДУКТЫ",
            description="> *Голод — плохой советчик.*",
            color=discord.Color.green()
        )
        view = FoodBuyMenu(self.player)
        await _safe_edit(interaction, embed=embed, view=view)

    @discord.ui.button(label="Оружейный магазин", emoji="🔫", style=discord.ButtonStyle.danger, row=1)
    async def weapon_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        if interaction.user.id != self.player.user_id:
            return await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)

        from ..weapon_shop import WeaponShopMainMenu
        embed = discord.Embed(
            title="🔫 ОРУЖЕЙНЫЙ МАГАЗИН",
            description="> *Свинец решает всё.*",
            color=discord.Color.red()
        )
        embed.add_field(
            name="📋 Разделы",
            value="• 🔫 **Оружие**\n• 📀 **Магазины**\n• 🎯 **Патроны**\n• 🔧 **Модификации**\n• 🗡️ **Ближний бой**\n• 💣 **Расходники**",
            inline=False
        )
        view = WeaponShopMainMenu(self.player)
        await _safe_edit(interaction, embed=embed, view=view)

    @discord.ui.button(label="Снаряжение", emoji="🧥", style=discord.ButtonStyle.primary, row=2)
    async def armor_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        if interaction.user.id != self.player.user_id:
            return await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)

        from ..armor_shop import ArmorShopMainMenu
        embed = discord.Embed(
            title="🧥 СНАРЯЖЕНИЕ",
            description="> *Твоя вторая кожа.*",
            color=discord.Color.blue()
        )
        embed.add_field(name="📋 Разделы", value="• 🧥 **Броня**\n• ⛑️ **Шлемы**", inline=False)
        view = ArmorShopMainMenu(self.player)
        await _safe_edit(interaction, embed=embed, view=view)