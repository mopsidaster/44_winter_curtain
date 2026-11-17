# -*- coding: utf-8 -*-
# func/views/trade/page2.py - Универсальная торговля: Продать (0.4.8.8)

import discord
import uuid

from ._helpers import _safe_defer, _safe_edit, _safe_followup
from .pagination import _TradePaginationMixin
from ..helpers import save_player, ITEMS
from ...station_utils import is_trade_station
from ...game_manager import game_manager
from config.map_config import WEAPONS, ARMOR, MODULES, MAGAZINES
from ...weapon_system import get_magazine_price
from ...melee_system import get_melee_weapon
from utils.logger import get_logger

logger = get_logger()


class TradePage2Menu(_TradePaginationMixin, discord.ui.View):
    """Универсальная вкладка «Продать»."""

    def __init__(self, player):
        super().__init__(timeout=180)
        self.player = player
        self.page = 2

    @discord.ui.button(label="💰 Продать всё", style=discord.ButtonStyle.danger, row=0)
    async def sell_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        if interaction.user.id != self.player.user_id:
            return await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)

        if not is_trade_station(self.player.location):
            return await _safe_followup(interaction, content="❌ Торговля только на торговых станциях!", ephemeral=True)

        # Продаем весь хлам
        hlam = self.player.inventory.get('хлам', []) or []
        total = 0
        sold_items = []

        for item in hlam[:]:
            if item.startswith("груз_") or item in ("временный_пропуск", "постоянный_пропуск"):
                continue
            if item in ITEMS['sell']:
                total += ITEMS['sell'][item]["price"]
                sold_items.append(ITEMS['sell'][item]["name"])
                hlam.remove(item)

        # Продаем оружие (кроме текущего)
        weapons_to_sell = [w for w in self.player.weapons_inventory if w != self.player.weapon]
        for w_id in weapons_to_sell:
            wdata = WEAPONS.get(w_id, {})
            price = int(wdata.get('price', 0) * 0.5)
            total += price
            sold_items.append(f"{wdata.get('name', w_id)} (оружие)")
            self.player.weapons_inventory.remove(w_id)

        # Продаем броню (кроме надетой)
        armor_to_sell = [a for a in self.player.armor_inventory if a != self.player.armor and a != self.player.helmet]
        for a_id in armor_to_sell:
            adata = ARMOR.get('armor_sets', {}).get(a_id, {})
            price = int(adata.get('price', 0) * 0.5)
            total += price
            sold_items.append(f"{adata.get('name', a_id)} (броня)")
            self.player.armor_inventory.remove(a_id)

        # Продаем модули
        mods_to_sell = list(self.player.modules_inventory)
        for m_id in mods_to_sell:
            mdata = MODULES.get('modules', {}).get(m_id, {})
            price = int(mdata.get('price', 0) * 0.5)
            total += price
            sold_items.append(f"{mdata.get('name', m_id)} (модуль)")
            self.player.modules_inventory.remove(m_id)

        if not sold_items:
            await _safe_followup(interaction, content="❌ Нечего продавать!", ephemeral=True)
            return

        self.player.inventory['никели'] = self.player.inventory.get('никели', 0) + total
        self.player.inventory['хлам'] = hlam
        await save_player(self.player)

        embed = discord.Embed(
            title="💰 Продажа завершена",
            description=f"Продано: {', '.join(sold_items[:10])}"
                        + (f" и ещё {len(sold_items)-10}" if len(sold_items) > 10 else ""),
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Получено", value=f"**{total}** никелей", inline=True)
        embed.add_field(name="💳 Всего никелей", value=str(self.player.inventory['никели']), inline=True)

        from .factory import build_trade_view
        new_view = build_trade_view(self.player, 2)
        await _safe_edit(interaction, embed=embed, view=new_view)