# -*- coding: utf-8 -*-
# func/views/weapon_shop/consumables.py - Расходники (0.4.8.6)
#
# ИСТОРИЯ:
#   0.4.8.2   — гранаты и ножи закрыты за уровнем лояльности.
#   0.4.8.6   — модалка количества (1-5) для гранат и ножей.

import discord
import uuid

from ..helpers import game_manager, WEAPONS, save_player, get_trade_discount
from ...factions import (
    get_station_discount, get_station_faction,
    get_player_loyalty_level,
)
from utils.logger import get_logger

logger = get_logger()

MAX_CONSUMABLE_PURCHASE = 5


def _get_discount(player) -> float:
    try:
        return (
                get_trade_discount(game_manager)
                * get_station_discount(player, player.location)
        )
    except Exception:
        return get_trade_discount(game_manager)


# ==================== МОДАЛКИ ====================

class GrenadePurchaseModal(discord.ui.Modal):
    quantity = discord.ui.TextInput(
        label=f"Количество (1-{MAX_CONSUMABLE_PURCHASE})",
        placeholder="1",
        min_length=1,
        max_length=1,
        required=True,
    )

    def __init__(self, player, grenade_id: str, price_per_unit: int):
        super().__init__(
            title=f"💣 {WEAPONS.get(grenade_id, {}).get('name', grenade_id)}"[:45]
        )
        self.player = player
        self.grenade_id = grenade_id
        self.price_per_unit = price_per_unit

    async def on_submit(self, interaction: discord.Interaction):
        try:
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass

            try:
                count = int(self.quantity.value.strip())
            except ValueError:
                await interaction.followup.send(
                    "❌ Введите целое число!", ephemeral=True
                )
                return

            if count < 1 or count > MAX_CONSUMABLE_PURCHASE:
                await interaction.followup.send(
                    f"❌ От 1 до {MAX_CONSUMABLE_PURCHASE}!",
                    ephemeral=True
                )
                return

            total = self.price_per_unit * count
            nickels = self.player.inventory.get("никели", 0)

            if nickels < total:
                await interaction.followup.send(
                    f"❌ Нужно **{total}** никелей, у вас **{nickels}**.",
                    ephemeral=True
                )
                return

            self.player.inventory["никели"] = nickels - total
            for _ in range(count):
                self.player.add_grenade(self.grenade_id, 1)
            await save_player(self.player)

            wdata = WEAPONS.get(self.grenade_id, {})
            await interaction.followup.send(
                f"✅ Куплено **{count}** {wdata.get('emoji', '💣')} "
                f"**{wdata.get('name', self.grenade_id)}** за **{total}** никелей!",
                ephemeral=True
            )

            from .consumables import ConsumablesMenu
            embed = discord.Embed(
                title="💣 Расходники",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="📋 Разделы",
                value="• 💣 **Гранаты**\n• 🔪 **Метательные ножи**",
                inline=False
            )
            new_view = ConsumablesMenu(self.player)
            try:
                await interaction.edit_original_response(
                    embed=embed, view=new_view
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"GrenadePurchaseModal: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    f"❌ Ошибка: {e}", ephemeral=True
                )
            except Exception:
                pass


class ThrowingKnifePurchaseModal(discord.ui.Modal):
    quantity = discord.ui.TextInput(
        label=f"Количество (1-{MAX_CONSUMABLE_PURCHASE})",
        placeholder="1",
        min_length=1,
        max_length=1,
        required=True,
    )

    def __init__(self, player, knife_id: str, price_per_unit: int):
        super().__init__(
            title=f"🔪 {WEAPONS.get(knife_id, {}).get('name', knife_id)}"[:45]
        )
        self.player = player
        self.knife_id = knife_id
        self.price_per_unit = price_per_unit

    async def on_submit(self, interaction: discord.Interaction):
        try:
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass

            try:
                count = int(self.quantity.value.strip())
            except ValueError:
                await interaction.followup.send(
                    "❌ Введите целое число!", ephemeral=True
                )
                return

            if count < 1 or count > MAX_CONSUMABLE_PURCHASE:
                await interaction.followup.send(
                    f"❌ От 1 до {MAX_CONSUMABLE_PURCHASE}!",
                    ephemeral=True
                )
                return

            total = self.price_per_unit * count
            nickels = self.player.inventory.get("никели", 0)

            if nickels < total:
                await interaction.followup.send(
                    f"❌ Нужно **{total}** никелей, у вас **{nickels}**.",
                    ephemeral=True
                )
                return

            self.player.inventory["никели"] = nickels - total
            for _ in range(count):
                self.player.add_knife(self.knife_id, 1)
            await save_player(self.player)

            wdata = WEAPONS.get(self.knife_id, {})
            await interaction.followup.send(
                f"✅ Куплено **{count}** {wdata.get('emoji', '🔪')} "
                f"**{wdata.get('name', self.knife_id)}** за **{total}** никелей!",
                ephemeral=True
            )

            from .consumables import ConsumablesMenu
            embed = discord.Embed(
                title="💣 Расходники",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="📋 Разделы",
                value="• 💣 **Гранаты**\n• 🔪 **Метательные ножи**",
                inline=False
            )
            new_view = ConsumablesMenu(self.player)
            try:
                await interaction.edit_original_response(
                    embed=embed, view=new_view
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"ThrowingKnifePurchaseModal: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    f"❌ Ошибка: {e}", ephemeral=True
                )
            except Exception:
                pass


# ==================== МЕНЮ ====================

class ConsumablesMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="💣 Гранаты", style=discord.ButtonStyle.danger)
    async def grenades_button(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваш магазин!", ephemeral=True
            )
            return

        await interaction.response.defer()

        discount = _get_discount(self.player)

        faction_id = get_station_faction(self.player.location)
        loyalty = get_player_loyalty_level(self.player, faction_id) if faction_id else 5

        embed = discord.Embed(
            title="💣 Гранаты",
            description="Ручные гранаты. Метание — полноценный ход.",
            color=discord.Color.orange()
        )

        available_grenades = []
        for wid, wdata in WEAPONS.items():
            if not isinstance(wdata, dict) or wdata.get('type') != 'grenade':
                continue

            req_level = wdata.get("loyalty_level", 1)
            if loyalty < req_level:
                continue

            available_grenades.append(wid)
            price = int(wdata.get('price', 0) * discount)
            in_inv = self.player.get_grenade_count(wid)
            embed.add_field(
                name=f"{wdata.get('emoji', '💣')} {wdata.get('name', wid)}",
                value=(
                    f"💥 Урон: **{wdata.get('damage', 0)}**\n"
                    f"💰 Цена: **{price}** никелей | 📦 У вас: **{in_inv}**"
                ),
                inline=False
            )

        if not available_grenades:
            embed.add_field(
                name="🔒 Нет доступа",
                value="Повысьте лояльность фракции для покупки гранат.",
                inline=False
            )
            view = None
        else:
            view = GrenadeBuyMenu(self.player, available_grenades)

        embed.set_footer(
            text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)} "
                 f"| 💠 Лояльность: {loyalty} ур."
        )

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit (гранаты): {e}")

    @discord.ui.button(label="🔪 Метательные ножи",
                       style=discord.ButtonStyle.primary)
    async def knives_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваш магазин!", ephemeral=True
            )
            return

        await interaction.response.defer()

        discount = _get_discount(self.player)

        faction_id = get_station_faction(self.player.location)
        loyalty = get_player_loyalty_level(self.player, faction_id) if faction_id else 5

        embed = discord.Embed(
            title="🔪 Метательные ножи",
            description="Метание — полноценный ход.",
            color=discord.Color.blue()
        )

        available_knives = []
        for wid, wdata in WEAPONS.items():
            if not isinstance(wdata, dict) or wdata.get('type') != 'throwing_knife':
                continue

            req_level = wdata.get("loyalty_level", 1)
            if loyalty < req_level:
                continue

            available_knives.append(wid)
            price = int(wdata.get('price', 0) * discount)
            in_inv = self.player.get_knife_count(wid)
            acc = int(wdata.get('accuracy', 0) * 100)
            embed.add_field(
                name=f"{wdata.get('emoji', '🔪')} {wdata.get('name', wid)}",
                value=(
                    f"💥 Урон: **{wdata.get('damage', 0)}** | "
                    f"🎯 Точность: **{acc}%**\n"
                    f"💰 Цена: **{price}** никелей | 📦 У вас: **{in_inv}**"
                ),
                inline=False
            )

        if not available_knives:
            embed.add_field(
                name="🔒 Нет доступа",
                value="Повысьте лояльность фракции для покупки ножей.",
                inline=False
            )
            view = None
        else:
            view = ThrowingKnifeBuyMenu(self.player, available_knives)

        embed.set_footer(
            text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)} "
                 f"| 💠 Лояльность: {loyalty} ур."
        )

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit (ножи): {e}")

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            return
        await interaction.response.defer()

        embed = discord.Embed(
            title="🔫 Оружейный магазин",
            description="Выберите раздел:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📋 Доступные разделы",
            value="• 🔫 **Оружие**\n• 📀 **Магазины**\n• 🎯 **Патроны**\n"
                  "• 🔧 **Модификации**\n• 🗡️ **Ближний бой**\n• 💣 **Расходники**",
            inline=False
        )
        from .main_menu import WeaponShopMainMenu
        view = WeaponShopMainMenu(self.player)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка back (расходники): {e}")


class GrenadeBuyMenu(discord.ui.View):
    def __init__(self, player, available_ids: list):
        super().__init__(timeout=120)
        self.player = player
        self.available_ids = available_ids
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        discount = _get_discount(self.player)
        for idx, wid in enumerate(self.available_ids):
            wdata = WEAPONS[wid]
            price = int(wdata.get('price', 0) * discount)
            btn = discord.ui.Button(
                label=f"{wdata.get('emoji', '💣')} {wdata.get('name', wid)} ({price})"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"buy_gr_{self.menu_id}_{idx}",
                row=idx // 3
            )
            btn.callback = self.create_buy_callback(wid, price)
            self.add_item(btn)

        back = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"buy_gr_back_{self.menu_id}",
            row=3
        )
        back.callback = self.back_callback
        self.add_item(back)

    def create_buy_callback(self, grenade_id: str, price: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message(
                    "❌ Не ваш магазин!", ephemeral=True
                )
                return

            if not interaction.response.is_done():
                await interaction.response.send_modal(
                    GrenadePurchaseModal(self.player, grenade_id, price)
                )

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            return
        await interaction.response.defer()

        from .consumables import ConsumablesMenu
        embed = discord.Embed(
            title="💣 Расходники",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="📋 Разделы",
            value="• 💣 **Гранаты**\n• 🔪 **Метательные ножи**",
            inline=False
        )
        view = ConsumablesMenu(self.player)
        await interaction.edit_original_response(embed=embed, view=view)


class ThrowingKnifeBuyMenu(discord.ui.View):
    def __init__(self, player, available_ids: list):
        super().__init__(timeout=120)
        self.player = player
        self.available_ids = available_ids
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        discount = _get_discount(self.player)
        for idx, wid in enumerate(self.available_ids):
            wdata = WEAPONS[wid]
            price = int(wdata.get('price', 0) * discount)
            btn = discord.ui.Button(
                label=f"{wdata.get('emoji', '🔪')} {wdata.get('name', wid)} ({price})"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"buy_kn_{self.menu_id}_{idx}",
                row=idx // 3
            )
            btn.callback = self.create_buy_callback(wid, price)
            self.add_item(btn)

        back = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"buy_kn_back_{self.menu_id}",
            row=3
        )
        back.callback = self.back_callback
        self.add_item(back)

    def create_buy_callback(self, knife_id: str, price: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message(
                    "❌ Не ваш магазин!", ephemeral=True
                )
                return

            if not interaction.response.is_done():
                await interaction.response.send_modal(
                    ThrowingKnifePurchaseModal(self.player, knife_id, price)
                )

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            return
        await interaction.response.defer()

        from .consumables import ConsumablesMenu
        embed = discord.Embed(
            title="💣 Расходники",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="📋 Разделы",
            value="• 💣 **Гранаты**\n• 🔪 **Метательные ножи**",
            inline=False
        )
        view = ConsumablesMenu(self.player)
        await interaction.edit_original_response(embed=embed, view=view)