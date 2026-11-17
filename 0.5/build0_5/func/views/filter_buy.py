# -*- coding: utf-8 -*-
# func/views/filter_buy.py - Меню покупки фильтров

import discord
from .helpers import (
    game_manager, save_player, get_trade_discount,
    get_filter_discount, get_filter, get_filter_price,
    get_filter_name, get_filter_emoji, get_filter_durability
)

class FilterBuyMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self._add_buttons()

    def _add_buttons(self):
        filter_discount = get_filter_discount(game_manager)
        trade_discount = get_trade_discount(game_manager)
        total_discount = trade_discount * filter_discount

        available_filters = ["поврежденный", "поношенный", "нетронутый", "усиленный"]

        for filter_id in available_filters:
            filter_data = get_filter(filter_id)
            if filter_data:
                price = int(filter_data.get('price', 0) * total_discount)
                button = discord.ui.Button(
                    label=f"{filter_data.get('emoji', '🧪')} {filter_data.get('name', filter_id)} ({price} никелей)",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"buy_filter_{filter_id}"
                )
                button.callback = self.create_callback(filter_id, price)
                self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, filter_id: str, price: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            if self.player.inventory['никели'] < price:
                await interaction.response.send_message(f"❌ Нужно {price} никелей!", ephemeral=True)
                return

            self.player.inventory['никели'] -= price
            self.player.filters.append(filter_id)
            await save_player(self.player)

            filter_data = get_filter(filter_id)
            await interaction.response.send_message(f"✅ Купили **{filter_data.get('name', filter_id)}** за {price} никелей!", ephemeral=True)

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        from .trade import TradeMenu
        embed = discord.Embed(
            title="🏪 Торговая зона",
            description="Нажмите на кнопку для покупки или продажи.",
            color=discord.Color.gold()
        )
        view = TradeMenu(self.player)
        await interaction.response.edit_message(embed=embed, view=view)