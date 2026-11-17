# -*- coding: utf-8 -*-
# func/views/weapon_shop/weapon_types.py - Меню типов оружия (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.8.2 — фильтрация по лояльности
#   0.4.8.3 — фикс импорта
#   0.4.8.7 — фильтр trader_only (не показывать в общей торговле)

import discord
import uuid

from ..helpers import (
    game_manager, WEAPONS, save_player,
    get_trade_discount, get_weapon,
)
from ...weapon_system import can_install_module
from ...factions import (
    get_station_discount, get_station_faction,
    get_player_loyalty_level,
)
from config.map_config import MODULES
from utils.logger import get_logger

from ._helpers import (
    WEAPON_TYPE_PAGES,
    WEAPONS_PER_PAGE,
    get_weapons_by_type,
)

logger = get_logger()


def _get_discount(player) -> float:
    try:
        return (
                get_trade_discount(game_manager)
                * get_station_discount(player, player.location)
        )
    except Exception:
        return get_trade_discount(game_manager)


def _is_trader_only(weapon_id: str) -> bool:
    """0.4.8.7: оружие только у торговца — не показывать в общей торговле."""
    wdata = WEAPONS.get(weapon_id, {})
    return bool(wdata.get("trader_only"))


class WeaponTypeMenu(discord.ui.View):
    def __init__(self, player, current_page: str = "pistol", weapon_page: int = 0):
        super().__init__(timeout=120)
        self.player = player
        self.current_page = current_page
        self.weapon_page = weapon_page
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _get_available_weapon_ids(self) -> list:
        faction_id = get_station_faction(self.player.location)
        loyalty_level = get_player_loyalty_level(self.player, faction_id) if faction_id else 5

        all_weapons = get_weapons_by_type(self.current_page)
        available = []
        for w_id in all_weapons:
            wdata = WEAPONS.get(w_id, {})
            if loyalty_level < wdata.get("loyalty_level", 1):
                continue
            if _is_trader_only(w_id):
                continue
            available.append(w_id)
        return available

    def _get_page_weapons(self) -> list:
        available = self._get_available_weapon_ids()
        start = self.weapon_page * WEAPONS_PER_PAGE
        end = start + WEAPONS_PER_PAGE
        return available[start:end]

    def _get_total_weapon_pages(self) -> int:
        available = self._get_available_weapon_ids()
        if not available:
            return 1
        return max(1, (len(available) + WEAPONS_PER_PAGE - 1) // WEAPONS_PER_PAGE)

    def _add_buttons(self):
        self.clear_items()

        type_buttons = []
        for type_id, type_data in WEAPON_TYPE_PAGES.items():
            count = len(get_weapons_by_type(type_id))
            if count == 0:
                continue
            type_buttons.append((type_id, type_data, count))

        for idx, (type_id, type_data, count) in enumerate(type_buttons[:5]):
            is_current = (type_id == self.current_page)
            button = discord.ui.Button(
                label=f"{type_data['emoji']} {type_data['name']} ({count})",
                style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.secondary,
                custom_id=f"wtype_{self.menu_id}_{idx}",
                row=0,
                disabled=is_current
            )
            button.callback = self.create_type_callback(type_id)
            self.add_item(button)

        page_weapons = self._get_page_weapons()

        if not page_weapons:
            button = discord.ui.Button(
                label="❌ Нет оружия этого типа (нужна лояльность)",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"wtype_empty_{self.menu_id}",
                row=1
            )
            self.add_item(button)
        else:
            for idx, weapon_id in enumerate(page_weapons):
                weapon = WEAPONS.get(weapon_id, {})
                if not isinstance(weapon, dict):
                    continue

                is_current = self.player.weapon == weapon_id
                label = f"{weapon.get('emoji', '🔫')} {weapon.get('name', weapon_id)}"
                if is_current:
                    label = f"✅ {label}"

                button = discord.ui.Button(
                    label=label[:80],
                    style=discord.ButtonStyle.primary if not is_current else discord.ButtonStyle.success,
                    custom_id=f"wbuy_{self.menu_id}_{self.weapon_page}_{idx}",
                    row=1
                )
                button.callback = self.create_buy_callback(weapon_id)
                self.add_item(button)

        total_pages = self._get_total_weapon_pages()

        if total_pages > 1:
            prev_btn = discord.ui.Button(
                label="◀ Назад",
                style=discord.ButtonStyle.secondary,
                custom_id=f"wpage_prev_{self.menu_id}",
                row=2,
                disabled=(self.weapon_page == 0)
            )
            prev_btn.callback = self.prev_page_callback
            self.add_item(prev_btn)

            page_label = discord.ui.Button(
                label=f"Стр. {self.weapon_page + 1}/{total_pages}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"wpage_label_{self.menu_id}",
                row=2,
                disabled=True
            )
            self.add_item(page_label)

            next_btn = discord.ui.Button(
                label="Вперёд ▶",
                style=discord.ButtonStyle.secondary,
                custom_id=f"wpage_next_{self.menu_id}",
                row=2,
                disabled=(self.weapon_page >= total_pages - 1)
            )
            next_btn.callback = self.next_page_callback
            self.add_item(next_btn)

        back_button = discord.ui.Button(
            label="🔙 К разделам",
            style=discord.ButtonStyle.danger,
            custom_id=f"wtype_back_{self.menu_id}",
            row=3
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def get_embed(self, page: str, weapon_page: int = None) -> discord.Embed:
        if weapon_page is not None:
            self.weapon_page = weapon_page

        type_data = WEAPON_TYPE_PAGES.get(page, {})
        discount = _get_discount(self.player)

        total_pages = self._get_total_weapon_pages()
        page_weapons = self._get_page_weapons()

        description = type_data.get('description', '')
        if total_pages > 1:
            description += f"\n\n📄 Страница **{self.weapon_page + 1}/{total_pages}**"

        embed = discord.Embed(
            title=f"{type_data.get('emoji', '🔫')} {type_data.get('name', page)}",
            description=description,
            color=discord.Color.blue()
        )

        if not page_weapons:
            embed.add_field(name="🔒 Нет доступа", value="Повысьте лояльность фракции для покупки оружия.", inline=False)
            return embed

        for weapon_id in page_weapons:
            weapon = WEAPONS.get(weapon_id, {})
            if not isinstance(weapon, dict):
                continue

            is_current = self.player.weapon == weapon_id
            price = int(weapon.get('price', 0) * discount)
            accuracy = weapon.get('accuracy', 0.5)
            acc_text = f"{accuracy * 100:.0f}% / {accuracy * 75:.1f}% / {accuracy * 50:.1f}%"

            extra = ""
            wtype = weapon.get('type')
            if wtype == 'assault':
                extra = "🔹 Очередь: 2 выстрела"
            elif wtype == 'smg':
                extra = "🔹 Очередь: 4 выстрела"
            elif wtype == 'mg':
                subtype = weapon.get('subtype', 'light')
                subtype_name = "Лёгкий" if subtype == "light" else "Тяжёлый"
                extra = f"🔹 Очередь: 3 выстрела ({subtype_name})"
                if subtype == "heavy":
                    extra += "\n⚠️ Перезарядка 2 хода. Второй ход — только рукопашная."
                    extra += "\n⚠️ Запрещены прицелы и рукояти."
            elif wtype == 'sniper':
                subtype = weapon.get('subtype', '')
                if subtype == 'semi-auto':
                    extra = "🔹 Semi-auto: шанс второго выстрела (−15% точности)"
                elif subtype == 'bolt-action':
                    extra = "🔹 Bolt-action: один мощный выстрел"
                else:
                    extra = "🔹 1 мощный выстрел"
            elif wtype == 'spec_w':
                extra = "🔹 Уникальное"
            elif wtype == 'shotgun':
                extra = "🔹 Дробовик: смертелен вблизи"
                if weapon.get('shell_loading'):
                    extra += f", заряжается вручную ({weapon.get('shell_capacity', 0)} патр.)"
                # 0.4.8.7: дуплет
                if weapon.get('double_shot'):
                    extra += "\n💥 Есть режим **Дуплет** (2 патрона, ×2 урон)"

            if weapon.get('headshot_accuracy_bonus'):
                extra += f"\n🎯 Бонус в голову: +{weapon['headshot_accuracy_bonus']}%"

            if weapon.get('builtin_module'):
                builtin_name = MODULES.get('modules', {}).get(weapon['builtin_module'], {}).get('name', weapon['builtin_module'])
                extra += ("\n" if extra else "") + f"🔧 Встроенный: {builtin_name}"

            embed.add_field(
                name=f"{'✅ ' if is_current else ''}{weapon.get('emoji', '🔫')} {weapon.get('name', weapon_id)}",
                value=f"📊 Урон: **{weapon.get('damage', 0)}**\n"
                      f"🎯 Точность (Б/С/Д): **{acc_text}**\n"
                      f"📦 Калибр: {weapon.get('caliber', '?')}\n"
                      f"💰 Цена: **{price}** никелей" +
                      (f" ~~{weapon.get('price', 0)}~~ 🔥" if discount < 1.0 else "") +
                      (f"\n{extra}" if extra else ""),
                inline=False
            )

        if total_pages > 1:
            embed.set_footer(text="◀ Назад / Вперёд ▶ — переключение страниц")

        return embed

    def create_type_callback(self, type_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                return

            await interaction.response.defer()

            self.current_page = type_id
            self.weapon_page = 0
            new_view = WeaponTypeMenu(self.player, current_page=type_id, weapon_page=0)
            embed = new_view.get_embed(type_id)

            try:
                await interaction.edit_original_response(embed=embed, view=new_view)
            except Exception as e:
                logger.error(f"Ошибка смены типа: {e}")

        return callback

    async def prev_page_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id: return
        if self.weapon_page <= 0:
            await interaction.response.send_message("❌ Это первая страница.", ephemeral=True)
            return

        await interaction.response.defer()
        self.weapon_page -= 1
        new_view = WeaponTypeMenu(self.player, current_page=self.current_page, weapon_page=self.weapon_page)

        try:
            await interaction.edit_original_response(embed=new_view.get_embed(self.current_page), view=new_view)
        except Exception as e:
            logger.error(f"Ошибка prev page (weapon): {e}")

    async def next_page_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id: return
        total_pages = self._get_total_weapon_pages()
        if self.weapon_page >= total_pages - 1:
            await interaction.response.send_message("❌ Это последняя страница.", ephemeral=True)
            return

        await interaction.response.defer()
        self.weapon_page += 1
        new_view = WeaponTypeMenu(self.player, current_page=self.current_page, weapon_page=self.weapon_page)

        try:
            await interaction.edit_original_response(embed=new_view.get_embed(self.current_page), view=new_view)
        except Exception as e:
            logger.error(f"Ошибка next page (weapon): {e}")

    def create_buy_callback(self, weapon_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id: return
            await interaction.response.defer()

            weapon = get_weapon(weapon_id)
            if not isinstance(weapon, dict):
                await interaction.followup.send("❌ Оружие не найдено!", ephemeral=True)
                return

            discount = _get_discount(self.player)
            final_price = int(weapon.get('price', 0) * discount)

            if self.player.inventory['никели'] < final_price:
                await interaction.followup.send(f"❌ Нужно {final_price} никелей!", ephemeral=True)
                return
            if self.player.weapon == weapon_id:
                await interaction.followup.send("❌ Уже есть это оружие!", ephemeral=True)
                return

            current_mag_uid = self.player.equipped_magazine
            mag_compatible = False
            new_weapon = get_weapon(weapon_id)

            if current_mag_uid:
                cur_mag = self.player.get_magazine_obj(current_mag_uid)
                if cur_mag and new_weapon and cur_mag["type_id"] in new_weapon.get('magazines', []):
                    mag_compatible = True

            if current_mag_uid and not mag_compatible:
                self.player.uninstall_magazine()

            try:
                self.player.remove_builtin_modules()
            except AttributeError:
                pass

            removed_modules = []
            for slot, module_id in list(self.player.equipped_modules.items()):
                if module_id:
                    can_install, _ = can_install_module(weapon_id, module_id)
                    if not can_install:
                        self.player.modules_inventory.append(module_id)
                        self.player.equipped_modules[slot] = None
                        removed_modules.append(module_id)

            old_weapon = self.player.weapon
            if old_weapon and old_weapon != weapon_id and old_weapon != "пистолет_макарова":
                if old_weapon not in self.player.weapons_inventory:
                    self.player.weapons_inventory.append(old_weapon)

            self.player.inventory['никели'] -= final_price
            self.player.weapon = weapon_id

            try:
                self.player.apply_builtin_modules()
            except AttributeError:
                pass

            if not self.player.equipped_magazine and new_weapon:
                for mag in self.player.get_uninstalled_magazines():
                    if mag["type_id"] in new_weapon.get('magazines', []):
                        self.player.install_magazine(mag["uid"])
                        break

            await save_player(self.player)

            msg = f"✅ Купили **{weapon.get('name', weapon_id)}** за {final_price} никелей!"
            if removed_modules:
                msg += f"\n⚠️ Снято несовместимых модулей: {len(removed_modules)}"
            if weapon.get('builtin_module'):
                builtin_name = MODULES.get('modules', {}).get(weapon['builtin_module'], {}).get('name', weapon['builtin_module'])
                msg += f"\n🔧 Встроенный модуль: **{builtin_name}** (установлен)"

            await interaction.followup.send(msg, ephemeral=True)

            new_view = WeaponTypeMenu(self.player, current_page=self.current_page, weapon_page=self.weapon_page)

            try:
                await interaction.edit_original_response(embed=new_view.get_embed(self.current_page), view=new_view)
            except Exception as e:
                logger.error(f"Ошибка edit после покупки: {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id: return
        await interaction.response.defer()

        embed = discord.Embed(title="🔫 Оружейный магазин", description="Выберите раздел:", color=discord.Color.blue())
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
            logger.error(f"Ошибка back (weapon type): {e}")