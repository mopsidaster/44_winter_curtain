# -*- coding: utf-8 -*-
# func/views/trade/workshop.py - Вкладка «Мастерская» (0.4.8)
#
# ИСТОРИЯ:
#   0.4.4.6 — фильтры + ремонт противогаза
#   0.4.7.6 — «Ремонт брони» и «Товары» (изолента)
#   0.4.7.7 — набор для ремонта
#   0.4.8 — скидка фракции, проверка лояльности

import discord

from ._helpers import (
    _safe_defer, _safe_edit, _safe_followup, _build_workshop_embed,
)
from ..helpers import (
    game_manager, BALANCE, save_player,
    get_trade_discount, get_filter_discount, get_filter,
    is_workshop_station,
)
from ...station_utils import is_trade_station
from ...factions import get_station_discount, has_workshop_on_station
from utils.logger import get_logger

logger = get_logger()


def _get_discount(player) -> float:
    try:
        return get_trade_discount(game_manager) * get_station_discount(player, player.location)
    except Exception:
        return get_trade_discount(game_manager)


SHOP_GOODS = {
    "изолента": {
        "name": "Изолента",
        "emoji": "🩹",
        "base_price": 50,
        "restore": 5,
        "description": "Восстанавливает 5 единиц прочности",
    },
    "набор_для_ремонта": {
        "name": "Набор для ремонта",
        "emoji": "🧰",
        "base_price": 200,
        "restore": 25,
        "description": "Восстанавливает 25 единиц прочности",
    },
}


class WorkshopMenu(discord.ui.View):
    """Вкладка «Мастерская»: фильтры + ремонт + товары."""

    def __init__(self, player):
        super().__init__(timeout=180)
        self.player = player

    def _workshop_locked(self) -> bool:
        """0.4.8: закрыта ли Мастерская (лояльность)."""
        try:
            return not has_workshop_on_station(self.player, self.player.location)
        except Exception:
            return False

    @discord.ui.button(label="🧪 Купить фильтры", style=discord.ButtonStyle.primary, row=0)
    async def buy_filters_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        try:
            if interaction.user.id != self.player.user_id:
                await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)
                return
            if not is_trade_station(self.player.location):
                await _safe_followup(interaction, content="❌ Торговля доступна только на торговых станциях!", ephemeral=True)
                return
            if self._workshop_locked():
                await _safe_followup(
                    interaction,
                    content=(
                        "🔒 Мастерская закрыта.\n"
                        "Нужна лояльность **уровня 1+** у фракции этой станции."
                    ),
                    ephemeral=True,
                )
                return

            filter_discount = get_filter_discount(game_manager)
            faction_discount = _get_discount(self.player) / get_trade_discount(game_manager) if get_trade_discount(game_manager) > 0 else 1.0
            total_discount = get_trade_discount(game_manager) * filter_discount * faction_discount

            embed = discord.Embed(
                title="🧪 Покупка фильтров",
                description="Выберите фильтр:",
                color=discord.Color.blue()
            )

            if is_workshop_station(self.player.location, game_manager):
                embed.add_field(name="🔧 Мастерская сталкеров!", value="Скидка 50% на все фильтры!", inline=False)

            for filter_id in ["поврежденный", "поношенный", "нетронутый", "усиленный"]:
                f = get_filter(filter_id)
                if f:
                    price = int(f.get('price', 0) * total_discount)
                    embed.add_field(
                        name=f"{f.get('emoji', '🧪')} {f.get('name', filter_id)}",
                        value=f"Прочность: {f.get('durability', 0)} ед.\n"
                              f"Цена: {price} никелей" +
                              (f" ~~{f.get('price', 0)}~~ 🔥" if total_discount < 1.0 else ""),
                        inline=False
                    )

            from ..filter_buy import FilterBuyMenu
            view = FilterBuyMenu(self.player)
            await _safe_edit(interaction, embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ Ошибка в buy_filters_btn (workshop): {e}")
            import traceback
            logger.error(traceback.format_exc())

    @discord.ui.button(label="🔧 Ремонт противогаза", style=discord.ButtonStyle.success, row=0)
    async def repair_mask_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        try:
            if interaction.user.id != self.player.user_id:
                await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)
                return
            if not is_trade_station(self.player.location):
                await _safe_followup(interaction, content="❌ Торговля доступна только на торговых станциях!", ephemeral=True)
                return
            if self._workshop_locked():
                await _safe_followup(
                    interaction,
                    content="🔒 Мастерская закрыта. Нужна лояльность уровня 1+ у фракции станции.",
                    ephemeral=True,
                )
                return

            discount = _get_discount(self.player)
            price = int(BALANCE['prices']['repair'] * discount)

            if not self.player.has_gas_mask:
                await _safe_followup(interaction, content="❌ Нет противогаза!", ephemeral=True)
                return

            current_dur = self.player.gas_mask.get('прочность', 0)
            max_dur = self.player.get_gas_mask_max_durability()

            if current_dur >= max_dur and self.player.gas_mask.get('состояние') == "целый":
                await _safe_followup(
                    interaction,
                    content=f"✅ Противогаз в отличном состоянии! ({current_dur:.0f}/{max_dur:.0f})",
                    ephemeral=True
                )
                return

            if self.player.inventory['никели'] < price:
                await _safe_followup(interaction, content=f"❌ Нужно {price} никелей!", ephemeral=True)
                return

            self.player.inventory['никели'] -= price
            self.player.repair_gas_mask_full()
            await save_player(self.player)

            new_dur = self.player.gas_mask.get('прочность', 0)

            embed = _build_workshop_embed(self.player)
            new_view = WorkshopMenu(self.player)
            await _safe_edit(interaction, embed=embed, view=new_view)

            await _safe_followup(
                interaction,
                content=(
                    f"🔧 **Противогаз отремонтирован!**\n"
                    f"💰 Стоимость: {price} никелей\n"
                    f"❤️ Прочность: **{new_dur:.0f}/{max_dur:.0f}**"
                ),
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в repair_mask_btn: {e}")
            import traceback
            logger.error(traceback.format_exc())

    @discord.ui.button(label="🛡️ Ремонт брони", style=discord.ButtonStyle.success, row=1)
    async def repair_armor_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        try:
            if interaction.user.id != self.player.user_id:
                await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)
                return
            if not is_trade_station(self.player.location):
                await _safe_followup(interaction, content="❌ Торговля доступна только на торговых станциях!", ephemeral=True)
                return
            if self._workshop_locked():
                await _safe_followup(
                    interaction,
                    content="🔒 Мастерская закрыта. Нужна лояльность уровня 1+ у фракции станции.",
                    ephemeral=True,
                )
                return

            from ...armor_system import get_item_durability, get_armor_item

            armor_id = getattr(self.player, 'armor', None)
            helmet_id = getattr(self.player, 'helmet', None)

            if not armor_id and not helmet_id:
                await _safe_followup(
                    interaction,
                    content="❌ На вас нет ни брони, ни шлема.",
                    ephemeral=True
                )
                return

            discount = _get_discount(self.player)
            repair_price_per_unit = int(BALANCE['prices']['repair'] * discount)

            to_repair = []

            if armor_id:
                armor_data = get_armor_item(armor_id) or {}
                max_dur = float(armor_data.get('max_durability', 100))
                cur = get_item_durability(self.player, armor_id)
                missing = max_dur - cur
                if missing > 0:
                    to_repair.append({
                        "slot": "armor", "id": armor_id,
                        "name": armor_data.get('name', armor_id),
                        "current": cur, "max": max_dur,
                    })

            if helmet_id:
                helmet_data = get_armor_item(helmet_id) or {}
                max_dur = float(helmet_data.get('max_durability', 100))
                cur = get_item_durability(self.player, helmet_id)
                missing = max_dur - cur
                if missing > 0:
                    to_repair.append({
                        "slot": "helmet", "id": helmet_id,
                        "name": helmet_data.get('name', helmet_id),
                        "current": cur, "max": max_dur,
                    })

            if not to_repair:
                await _safe_followup(
                    interaction,
                    content="✅ Броня и шлем в идеальном состоянии!",
                    ephemeral=True
                )
                return

            total_missing = sum(int(it["max"] - it["current"]) for it in to_repair)
            total_price = max(10, (total_missing + 1) // 2 * repair_price_per_unit // 30)

            if self.player.inventory['никели'] < total_price:
                await _safe_followup(
                    interaction,
                    content=f"❌ Нужно **{total_price}** никелей (у вас {self.player.inventory['никели']}).\n"
                            f"Отсутствует прочности: {total_missing} ед.",
                    ephemeral=True
                )
                return

            self.player.inventory['никели'] -= total_price

            if not hasattr(self.player, 'armor_durability'):
                self.player.armor_durability = {"armor": 0.0, "helmet": 0.0}

            for it in to_repair:
                self.player.armor_durability[it["slot"]] = it["max"]

            await save_player(self.player)

            embed = _build_workshop_embed(self.player)
            new_view = WorkshopMenu(self.player)
            await _safe_edit(interaction, embed=embed, view=new_view)

            lines = [
                f"🛡️ **Ремонт брони завершён!**",
                f"💰 Стоимость: **{total_price}** никелей",
                "",
            ]
            for it in to_repair:
                lines.append(
                    f"  • **{it['name']}**: "
                    f"{it['current']:.0f} → {it['max']:.0f}"
                )

            await _safe_followup(interaction, content="\n".join(lines), ephemeral=True)

        except Exception as e:
            logger.error(f"❌ Ошибка в repair_armor_btn: {e}")
            import traceback
            logger.error(traceback.format_exc())

    @discord.ui.button(label="📦 Товары", style=discord.ButtonStyle.primary, row=1)
    async def shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        try:
            if interaction.user.id != self.player.user_id:
                await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)
                return
            if not is_trade_station(self.player.location):
                await _safe_followup(interaction, content="❌ Торговля доступна только на торговых станциях!", ephemeral=True)
                return
            if self._workshop_locked():
                await _safe_followup(
                    interaction,
                    content="🔒 Мастерская закрыта. Нужна лояльность уровня 1+ у фракции станции.",
                    ephemeral=True,
                )
                return

            embed = self._build_shop_embed()
            view = WorkshopShopMenu(self.player)
            await _safe_edit(interaction, embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ Ошибка в shop_btn: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _build_shop_embed(self) -> discord.Embed:
        discount = _get_discount(self.player)

        embed = discord.Embed(
            title="📦 Товары Мастерской",
            description=(
                "Расходники для ремонта снаряжения.\n"
                "Используются через меню **Действия → 🔨 Мастерить**."
            ),
            color=discord.Color.blue(),
        )

        for goods_id, goods in SHOP_GOODS.items():
            price = int(goods["base_price"] * discount)
            inv_count = self.player.inventory.get(goods_id, 0)

            embed.add_field(
                name=f"{goods['emoji']} {goods['name']}",
                value=(
                    f"{goods['description']}.\n\n"
                    f"💰 Цена: **{price}** никелей | "
                    f"📦 У вас: **{inv_count}** шт."
                ),
                inline=False,
            )

        embed.set_footer(text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)}")
        return embed

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger, row=2)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        try:
            if interaction.user.id != self.player.user_id:
                await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)
                return

            from .factory import build_trade_view
            from ._helpers import _build_trade_page_embed

            new_view = build_trade_view(self.player, 1)
            embed = _build_trade_page_embed(self.player, 1)
            await _safe_edit(interaction, embed=embed, view=new_view)

        except Exception as e:
            logger.error(f"❌ Ошибка в back_btn (workshop): {e}")
            import traceback
            logger.error(traceback.format_exc())


class WorkshopShopMenu(discord.ui.View):
    """0.4.7.7: подменю товаров Мастерской."""

    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player

    @discord.ui.button(label="🩹 Купить изоленту x1", style=discord.ButtonStyle.success, row=0)
    async def buy_tape_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._buy(interaction, "изолента", 1)

    @discord.ui.button(label="🩹 Купить изоленту x5", style=discord.ButtonStyle.success, row=0)
    async def buy_tape_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._buy(interaction, "изолента", 5)

    @discord.ui.button(label="🧰 Купить набор x1", style=discord.ButtonStyle.primary, row=1)
    async def buy_kit_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._buy(interaction, "набор_для_ремонта", 1)

    @discord.ui.button(label="🧰 Купить набор x3", style=discord.ButtonStyle.primary, row=1)
    async def buy_kit_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._buy(interaction, "набор_для_ремонта", 3)

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger, row=2)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await _safe_defer(interaction):
            return
        try:
            if interaction.user.id != self.player.user_id:
                await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)
                return
            embed = _build_workshop_embed(self.player)
            view = WorkshopMenu(self.player)
            await _safe_edit(interaction, embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка в WorkshopShopMenu.back_btn: {e}")

    async def _buy(self, interaction: discord.Interaction, goods_id: str, count: int):
        if not await _safe_defer(interaction):
            return
        try:
            if interaction.user.id != self.player.user_id:
                await _safe_followup(interaction, content="❌ Не ваш магазин!", ephemeral=True)
                return

            goods = SHOP_GOODS.get(goods_id)
            if not goods:
                await _safe_followup(interaction, content="❌ Товар не найден!", ephemeral=True)
                return

            discount = _get_discount(self.player)
            unit_price = int(goods["base_price"] * discount)
            total = unit_price * count

            if self.player.inventory['никели'] < total:
                await _safe_followup(
                    interaction,
                    content=f"❌ Нужно {total} никелей, у вас {self.player.inventory['никели']}!",
                    ephemeral=True,
                )
                return

            self.player.inventory['никели'] -= total
            self.player.inventory[goods_id] = self.player.inventory.get(goods_id, 0) + count
            await save_player(self.player)

            await _safe_followup(
                interaction,
                content=(
                    f"✅ Куплено: {goods['emoji']} **{goods['name']}** ×{count} "
                    f"за **{total}** никелей.\n"
                    f"📦 Всего: **{self.player.inventory[goods_id]}** шт."
                ),
                ephemeral=True,
            )

            embed = self._build_shop_embed()
            view = WorkshopShopMenu(self.player)
            await _safe_edit(interaction, embed=embed, view=view)

        except Exception as e:
            logger.error(f"Ошибка в WorkshopShopMenu._buy: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _build_shop_embed(self) -> discord.Embed:
        discount = _get_discount(self.player)

        embed = discord.Embed(
            title="📦 Товары Мастерской",
            description=(
                "Расходники для ремонта снаряжения.\n"
                "Используются через меню **Действия → 🔨 Мастерить**."
            ),
            color=discord.Color.blue(),
        )

        for goods_id, goods in SHOP_GOODS.items():
            price = int(goods["base_price"] * discount)
            inv_count = self.player.inventory.get(goods_id, 0)

            embed.add_field(
                name=f"{goods['emoji']} {goods['name']}",
                value=(
                    f"{goods['description']}.\n\n"
                    f"💰 Цена: **{price}** никелей | "
                    f"📦 У вас: **{inv_count}** шт."
                ),
                inline=False,
            )

        embed.set_footer(text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)}")
        return embed