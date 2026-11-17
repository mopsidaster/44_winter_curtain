# -*- coding: utf-8 -*-
# func/views/armor_shop.py - Магазин снаряжения (0.4.8.3)
#
# ИСТОРИЯ:
#   0.4.8.3 — Добавлена пагинация для брони и шлемов. ФИКС кнопок.

import discord
import uuid
from .helpers import game_manager, save_player, get_trade_discount
from ..armor_system import get_armor_item
from ..factions import get_station_faction, get_player_loyalty_level, get_station_discount
from config.map_config import ARMOR
from utils.logger import get_logger

logger = get_logger()

ITEMS_PER_PAGE = 5


def _get_available_armor(player, slot: str) -> list:
    """Возвращает список ID брони, доступной по лояльности."""
    faction_id = get_station_faction(player.location)
    loyalty = get_player_loyalty_level(player, faction_id) if faction_id else 5

    items = []
    for item_id, item in ARMOR.get('armor_sets', {}).items():
        if not isinstance(item, dict): continue
        if item.get('slot') != slot: continue
        if not item.get('obtainable', False): continue

        req_level = item.get('loyalty_level', 0)
        if loyalty >= req_level:
            items.append(item_id)

    return items


class ArmorShopMainMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="🧥 Броня", style=discord.ButtonStyle.primary)
    async def armor_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        available = _get_available_armor(self.player, 'armor')
        view = ArmorShopBuyMenu(self.player, slot='armor', available=available, page=0)
        embed = view.build_embed()

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка брони: {e}")

    @discord.ui.button(label="⛑️ Шлемы", style=discord.ButtonStyle.primary)
    async def helmet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        await interaction.response.defer()

        available = _get_available_armor(self.player, 'helmet')
        view = ArmorShopBuyMenu(self.player, slot='helmet', available=available, page=0)
        embed = view.build_embed()

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка шлемов: {e}")

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id: return
        await interaction.response.defer()

        from .trade import TradeMenu
        embed = discord.Embed(title="🏪 Торговая зона", description="Нажмите на кнопку для покупки или продажи.", color=discord.Color.gold())
        view = TradeMenu(self.player)
        await interaction.edit_original_response(embed=embed, view=view)


class ArmorShopBuyMenu(discord.ui.View):
    def __init__(self, player, slot: str, available: list, page: int = 0):
        super().__init__(timeout=120)
        self.player = player
        self.slot = slot
        self.available = available
        self.page = page
        self.menu_id = uuid.uuid4().hex[:8]
        self.total_pages = max(1, (len(available) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        if self.page >= self.total_pages:
            self.page = 0
        self._add_buttons()

    def build_embed(self) -> discord.Embed:
        title = "🧥 Броня" if self.slot == 'armor' else "⛑️ Шлемы"
        embed = discord.Embed(title=title, description="Выберите предмет для покупки:", color=discord.Color.blue())

        discount = get_trade_discount(game_manager) * get_station_discount(self.player, self.player.location)

        start = self.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = self.available[start:end]

        if not page_items:
            embed.add_field(name="📭 Пусто", value="Нет доступных предметов (повысьте лояльность).", inline=False)
            return embed

        for item_id in page_items:
            item = get_armor_item(item_id)
            if not item: continue

            price = int(item.get('price', 0) * discount)
            embed.add_field(
                name=f"{item.get('emoji', '')} {item.get('name', item_id)}",
                value=(
                    f"🔩 {item.get('material', '—')}\n"
                    f"❤️ Прочность: {item.get('max_durability', 0)}\n"
                    f"🛡️ Противоудар: {item.get('impact_protection', 0)}% | Броня: {item.get('armor_protection', 0)}%\n"
                    f"💰 Цена: **{price}** никелей"
                ),
                inline=False
            )

        embed.set_footer(text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)} | Стр. {self.page + 1}/{self.total_pages}")
        return embed

    def _add_buttons(self):
        start = self.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = self.available[start:end]

        # Кнопки покупки
        for idx, item_id in enumerate(page_items):
            item = get_armor_item(item_id)
            btn = discord.ui.Button(
                label=f"{item.get('emoji', '')} {item.get('name', item_id)}"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"arm_buy_{self.menu_id}_{idx}",
                row=idx // 3
            )
            btn.callback = self.create_buy_callback(item_id)
            self.add_item(btn)

        # Пагинация
        if self.total_pages > 1:
            prev_btn = discord.ui.Button(
                label="◀ Назад", style=discord.ButtonStyle.secondary,
                custom_id=f"arm_prev_{self.menu_id}", row=2, disabled=(self.page == 0)
            )
            prev_btn.callback = self.prev_page_callback
            self.add_item(prev_btn)

            next_btn = discord.ui.Button(
                label="Вперёд ▶", style=discord.ButtonStyle.secondary,
                custom_id=f"arm_next_{self.menu_id}", row=2, disabled=(self.page >= self.total_pages - 1)
            )
            next_btn.callback = self.next_page_callback
            self.add_item(next_btn)

        # Назад
        back_button = discord.ui.Button(label="🔙 Назад", style=discord.ButtonStyle.danger, custom_id=f"arm_back_{self.menu_id}", row=3)
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def prev_page_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id: return
        if self.page <= 0: return

        await interaction.response.defer()
        self.page -= 1
        new_view = ArmorShopBuyMenu(self.player, self.slot, self.available, self.page)
        await interaction.edit_original_response(embed=new_view.build_embed(), view=new_view)

    async def next_page_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id: return
        if self.page >= self.total_pages - 1: return

        await interaction.response.defer()
        self.page += 1
        new_view = ArmorShopBuyMenu(self.player, self.slot, self.available, self.page)
        await interaction.edit_original_response(embed=new_view.build_embed(), view=new_view)

    def create_buy_callback(self, item_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id: return
            await interaction.response.defer()

            item = get_armor_item(item_id)
            if not item: return

            discount = get_trade_discount(game_manager) * get_station_discount(self.player, self.player.location)
            price = int(item.get('price', 0) * discount)
            nickels = self.player.inventory.get('никели', 0)

            if nickels < price:
                await interaction.followup.send(f"❌ Нужно **{price}** никелей, у вас **{nickels}**!", ephemeral=True)
                return

            if item_id in self.player.armor_inventory or self.player.armor == item_id or self.player.helmet == item_id:
                await interaction.followup.send(f"⚠️ У вас уже есть **{item.get('name', item_id)}**!", ephemeral=True)
                return

            self.player.inventory['никели'] = nickels - price
            self.player.armor_inventory.append(item_id)
            await save_player(self.player)

            embed = discord.Embed(title="✅ Покупка завершена", description=f"Куплено: {item.get('emoji', '')} **{item.get('name', item_id)}** за **{price}** никелей!", color=discord.Color.green())
            embed.add_field(name="💡 Как надеть", value="Меню → Действия → Броня → Надеть снаряжение", inline=False)
            embed.add_field(name="💰 Остаток никелей", value=str(self.player.inventory.get('никели', 0)), inline=False)

            new_view = ArmorShopBuyMenu(self.player, self.slot, self.available, self.page)
            await interaction.edit_original_response(embed=embed, view=new_view)
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id: return
        await interaction.response.defer()

        embed = discord.Embed(title="🧥 Магазин снаряжения", description="Выберите раздел:", color=discord.Color.blue())
        embed.add_field(name="📋 Разделы", value="• 🧥 **Броня**\n• ⛑️ **Шлемы**", inline=False)
        view = ArmorShopMainMenu(self.player)
        await interaction.edit_original_response(embed=embed, view=view)