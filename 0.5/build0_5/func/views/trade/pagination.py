# -*- coding: utf-8 -*-
# func/views/trade/pagination.py - Пагинация (0.4.8.8)

import discord

from ._helpers import _safe_defer, _safe_edit, _safe_followup, _build_trade_page_embed
from utils.logger import get_logger

logger = get_logger()

TOTAL_TRADE_PAGES = 2


class _TradePaginationMixin:

    def build_page_embed(self) -> discord.Embed:
        return _build_trade_page_embed(self.player, self.page)

    @discord.ui.button(label="🛒 Купить", style=discord.ButtonStyle.success, row=3)
    async def nav_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        if self.page == 1:
            return
        from .factory import build_trade_view
        new_view = build_trade_view(self.player, 1)
        embed = _build_trade_page_embed(self.player, 1)
        await _safe_edit(interaction, embed=embed, view=new_view)

    @discord.ui.button(label="💰 Продать", style=discord.ButtonStyle.primary, row=3)
    async def nav_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        if self.page == 2:
            return
        from .factory import build_trade_view
        new_view = build_trade_view(self.player, 2)
        embed = _build_trade_page_embed(self.player, 2)
        await _safe_edit(interaction, embed=embed, view=new_view)

    @discord.ui.button(label="🔙 В меню", style=discord.ButtonStyle.danger, row=4)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        try:
            from ..main_menu import MainMenu, build_main_embed
            from ...map_data import MAP_DATA
            station_data = MAP_DATA["станции"].get(self.player.location, {})
            embed = build_main_embed(self.player, station_data)
            await _safe_edit(interaction, embed=embed, view=MainMenu(self.player))
        except Exception as e:
            logger.error(f"❌ Ошибка back: {e}")