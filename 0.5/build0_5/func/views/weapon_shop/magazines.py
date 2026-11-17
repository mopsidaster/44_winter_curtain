# -*- coding: utf-8 -*-
# func/views/weapon_shop/magazines.py - Меню покупки магазинов (0.4.8)
#
# ИСТОРИЯ:
#   0.4.4.6 — базовое меню с пагинацией
#   0.4.6.2 — категории магазинов
#   0.4.8 — скидка фракции

import discord
import uuid

from ..helpers import (
    game_manager, WEAPONS, MAGAZINES, save_player,
    get_trade_discount, get_magazine,
)
from ...factions import get_station_discount
from utils.logger import get_logger

from ._helpers import MAGAZINES_PER_PAGE

logger = get_logger()


def _get_discount(player) -> float:
    try:
        return get_trade_discount(game_manager) * get_station_discount(player, player.location)
    except Exception:
        return get_trade_discount(game_manager)


MAGAZINE_CATEGORIES = {
    "pistol": {
        "name": "🔫 Пистолетные",
        "description": "ПМ, ГШ-18, .44 Магнум",
        "weapon_types": ["pistol"],
    },
    "smg": {
        "name": "🔫 ПП",
        "description": "ПП-19 «Витязь», ПП-91 «Кедр»",
        "weapon_types": ["smg"],
    },
    "assault": {
        "name": "💥 Автоматы",
        "description": "Ублюдок, Калаш-74, Калаш 2012, АКС-74У, АКМ",
        "weapon_types": ["assault"],
    },
    "sniper": {
        "name": "🎯 Снайперские",
        "description": "ВСК-94, 9А-91, ОСВ-96, Мосина, Вентиль, СВД, СКС",
        "weapon_types": ["sniper"],
    },
    "shotgun": {
        "name": "🔫 Дробовики",
        "description": "Убойник, Сайга-12",
        "weapon_types": ["shotgun"],
    },
    "mg": {
        "name": "🔫 Пулемёты",
        "description": "ДП-27, РПД",
        "weapon_types": ["mg"],
    },
}


def _get_weapon_type(weapon_id: str) -> str:
    wdata = WEAPONS.get(weapon_id)
    if isinstance(wdata, dict):
        return wdata.get('type', 'unknown')
    return 'unknown'


def _get_magazines_by_category(category_id: str) -> list:
    cat = MAGAZINE_CATEGORIES.get(category_id)
    if not cat:
        return []

    weapon_types = cat.get('weapon_types', [])
    result = []

    for mag_id, mag_data in MAGAZINES.items():
        if mag_id.startswith("_"):
            continue
        if not isinstance(mag_data, dict):
            continue

        weapon_id = mag_data.get('weapon')
        if not weapon_id:
            continue

        wtype = _get_weapon_type(weapon_id)
        if wtype in weapon_types:
            result.append(mag_id)

    return result


class MagazineBuyMenu(discord.ui.View):
    def __init__(self, player, page: int = 0):
        super().__init__(timeout=180)
        self.player = player
        self.page = page
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    @staticmethod
    def build_embed(player) -> discord.Embed:
        embed = discord.Embed(
            title="📀 Магазины — категории",
            description=(
                "**Магазины сгруппированы по типу оружия.**\n"
                "Выберите категорию:"
            ),
            color=discord.Color.blue()
        )

        for cat_id, cat in MAGAZINE_CATEGORIES.items():
            mags = _get_magazines_by_category(cat_id)
            if not mags:
                continue
            embed.add_field(
                name=f"{cat['name']} ({len(mags)})",
                value=f"_{cat['description']}_",
                inline=False
            )

        embed.set_footer(text=f"💰 Ваши никели: {player.inventory.get('никели', 0)}")
        return embed

    def _add_buttons(self):
        for idx, (cat_id, cat) in enumerate(MAGAZINE_CATEGORIES.items()):
            mags = _get_magazines_by_category(cat_id)
            if not mags:
                continue

            btn = discord.ui.Button(
                label=f"{cat['name']} ({len(mags)})"[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"mag_cat_{self.menu_id}_{idx}",
                row=idx // 3,
            )
            btn.callback = self.create_category_callback(cat_id)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 К разделам",
            style=discord.ButtonStyle.danger,
            custom_id=f"mag_cat_back_{self.menu_id}",
            row=4,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_category_callback(self, category_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                    return

                await interaction.response.defer()

                new_view = MagazineCategoriesMenu(self.player, category_id)
                embed = new_view.build_embed()

                try:
                    await interaction.edit_original_response(embed=embed, view=new_view)
                except Exception as e:
                    logger.error(f"Ошибка открытия категории {category_id}: {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в category callback ({category_id}): {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                return

            await interaction.response.defer()

            embed = discord.Embed(
                title="🔫 Оружейный магазин",
                description="Выберите раздел:",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📋 Доступные разделы",
                value="• 🔫 **Оружие**\n• 📀 **Магазины**\n• 🎯 **Патроны**\n• 🔧 **Модификации**\n• 🗡️ **Ближний бой**\n• 💣 **Расходники**",
                inline=False
            )
            from .main_menu import WeaponShopMainMenu
            view = WeaponShopMainMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка back (magazines): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (magazines): {e}")


class MagazineCategoriesMenu(discord.ui.View):
    def __init__(self, player, category_id: str = None, page: int = 0):
        super().__init__(timeout=180)
        self.player = player
        self.category_id = category_id
        self.page = page
        self.menu_id = uuid.uuid4().hex[:8]

        if self.category_id:
            self.mag_ids = _get_magazines_by_category(self.category_id)
        else:
            self.mag_ids = []

        self.total_pages = max(
            1,
            (len(self.mag_ids) + MAGAZINES_PER_PAGE - 1) // MAGAZINES_PER_PAGE
        )
        if self.page >= self.total_pages:
            self.page = 0

        self._add_buttons()

    def build_embed(self) -> discord.Embed:
        cat = MAGAZINE_CATEGORIES.get(self.category_id, {})
        discount = _get_discount(self.player)
        current_weapon = self.player.weapon

        embed = discord.Embed(
            title=f"📀 Магазины — {cat.get('name', '?')}",
            description=(
                f"_{cat.get('description', '')}_\n\n"
                f"Страница **{self.page + 1}/{self.total_pages}** • "
                f"Всего магазинов: **{len(self.mag_ids)}**\n"
                f"Текущее оружие: **{WEAPONS.get(current_weapon, {}).get('name', '—')}**"
            ),
            color=discord.Color.blue()
        )

        start = self.page * MAGAZINES_PER_PAGE
        end = start + MAGAZINES_PER_PAGE
        page_mags = self.mag_ids[start:end]

        for mag_id in page_mags:
            mag = get_magazine(mag_id)
            if not mag:
                continue

            is_compatible = mag_id in WEAPONS.get(current_weapon, {}).get('magazines', [])
            price = int(mag.get('price', 0) * discount)
            weapon_name = WEAPONS.get(mag.get('weapon', ''), {}).get('name', mag.get('weapon', '?'))

            compat_marker = "✅ " if is_compatible else ""
            embed.add_field(
                name=f"{compat_marker}{mag.get('emoji', '📀')} {mag.get('name', mag_id)}",
                value=(
                        f"Вместимость: {mag.get('capacity', 0)} шт.\n"
                        f"Калибр: {mag.get('caliber', '?')} | Для: {weapon_name}\n"
                        f"Цена: **{price}** никелей" +
                        (f" ~~{mag.get('price', 0)}~~ 🔥" if discount < 1.0 else "")
                ),
                inline=False
            )

        embed.set_footer(text="✅ — подходит для текущего оружия")
        return embed

    def _add_buttons(self):
        discount = _get_discount(self.player)
        current_weapon = self.player.weapon

        start = self.page * MAGAZINES_PER_PAGE
        end = start + MAGAZINES_PER_PAGE
        page_mags = self.mag_ids[start:end]

        for idx, mag_id in enumerate(page_mags):
            mag = get_magazine(mag_id)
            if not mag:
                continue

            is_compatible = mag_id in WEAPONS.get(current_weapon, {}).get('magazines', [])
            price = int(mag.get('price', 0) * discount)

            label = f"{'✅ ' if is_compatible else ''}{mag.get('emoji', '📀')} {mag.get('name', mag_id)} ({price})"
            button = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.success if is_compatible else discord.ButtonStyle.primary,
                custom_id=f"mag_buy_{self.menu_id}_{idx}",
                row=idx // 3,
            )
            button.callback = self.create_buy_callback(mag_id)
            self.add_item(button)

        prev_btn = discord.ui.Button(
            label="◀ Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mag_prev_{self.menu_id}",
            row=2,
            disabled=(self.page == 0),
        )
        prev_btn.callback = self.prev_page_callback
        self.add_item(prev_btn)

        page_label = discord.ui.Button(
            label=f"Стр. {self.page + 1}/{self.total_pages}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mag_page_{self.menu_id}",
            row=2,
            disabled=True,
        )
        self.add_item(page_label)

        next_btn = discord.ui.Button(
            label="Вперёд ▶",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mag_next_{self.menu_id}",
            row=2,
            disabled=(self.page >= self.total_pages - 1),
        )
        next_btn.callback = self.next_page_callback
        self.add_item(next_btn)

        back_btn = discord.ui.Button(
            label="🔙 К категориям",
            style=discord.ButtonStyle.danger,
            custom_id=f"mag_back_{self.menu_id}",
            row=3,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def prev_page_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                return
            if self.page <= 0:
                await interaction.response.send_message("❌ Это первая страница.", ephemeral=True)
                return

            await interaction.response.defer()
            self.page -= 1
            new_view = MagazineCategoriesMenu(self.player, self.category_id, page=self.page)
            embed = new_view.build_embed()
            try:
                await interaction.edit_original_response(embed=embed, view=new_view)
            except Exception as e:
                logger.error(f"Ошибка prev page: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в prev_page_callback: {e}")

    async def next_page_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                return
            if self.page >= self.total_pages - 1:
                await interaction.response.send_message("❌ Это последняя страница.", ephemeral=True)
                return

            await interaction.response.defer()
            self.page += 1
            new_view = MagazineCategoriesMenu(self.player, self.category_id, page=self.page)
            embed = new_view.build_embed()
            try:
                await interaction.edit_original_response(embed=embed, view=new_view)
            except Exception as e:
                logger.error(f"Ошибка next page: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в next_page_callback: {e}")

    def create_buy_callback(self, magazine_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                    return

                await interaction.response.defer()

                mag = get_magazine(magazine_id)
                if not mag:
                    await interaction.followup.send("❌ Магазин не найден!", ephemeral=True)
                    return

                discount = _get_discount(self.player)
                final_price = int(mag.get('price', 0) * discount)

                if self.player.inventory['никели'] < final_price:
                    await interaction.followup.send(f"❌ Нужно {final_price} никелей!", ephemeral=True)
                    return

                self.player.inventory['никели'] -= final_price
                uid = self.player.add_magazine_instance(magazine_id)
                await save_player(self.player)

                same_count = sum(
                    1 for m in self.player.magazines if m["type_id"] == magazine_id
                )

                await interaction.followup.send(
                    f"✅ Купили **{mag.get('name', magazine_id)}** за {final_price} никелей!\n"
                    f"📀 UID: `{uid}` | Всего таких магазинов: **{same_count}** шт.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ Ошибка в mag buy_callback ({magazine_id}): {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                return

            await interaction.response.defer()

            new_view = MagazineBuyMenu(self.player)
            embed = new_view.build_embed(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=new_view)
            except Exception as e:
                logger.error(f"Ошибка back (category → categories): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (category): {e}")