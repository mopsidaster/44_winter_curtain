# -*- coding: utf-8 -*-
# func/debug_tool.py - Отладочный инструмент (Билд 0.4.8.7.3)

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import get_logger
from database.db import save_player

logger = get_logger()

DEBUG_PASSWORD = "metro"
DEBUG_NICKELS_AMOUNT = 10000

DEBUG_WEAPON = "ак_2012"
DEBUG_MAGAZINE = "магазин_ак2012_50"
DEBUG_AMMO_TYPE = "бронебойные"
DEBUG_AMMO_COUNT = 500
DEBUG_MAGAZINES_COUNT = 5

DEBUG_MELEE = ["ледоруб"]

DEBUG_ARMOR = "бутовский_странник_броня"
DEBUG_HELMET = "бутовский_странник_шлем"

DEBUG_FOOD_ITEMS = [
    ("жареный_кусок_свинины", 10),
    ("жареные_грибы_с_мясом", 10),
    ("жареное_мясо_крысы", 10),
]

DEBUG_MEDKITS = [
    ("тактическая_аптечка", 5),
    ("аптечка_аи2", 10),
    ("мед_подсумок", 5),
]

DEBUG_CONSUMABLES = [
    ("антирад", 5),
    ("активированный_уголь", 5),
    ("аспирин", 5),
]

DEBUG_GRENADES = [
    ("ф_1", 5),
    ("ргд_5", 5),
]

DEBUG_KNIVES = [
    ("боевой_метательный_нож", 5),
]

DEBUG_FILTERS = [
    ("усиленный", 5),
    ("нетронутый", 5),
]


def _give_test_gear(player) -> dict:
    """0.4.8.7.3: минимальный тестовый набор."""
    summary = {
        "weapons": 0, "magazines": 0, "ammo": 0,
        "armor": 0, "helmet": 0, "melee": 0,
        "food": 0, "medkits": 0, "consumables": 0,
        "grenades": 0, "knives": 0, "filters": 0, "nickels": 0,
    }

    # 1. Одно оружие
    if DEBUG_WEAPON not in player.weapons_inventory \
            and DEBUG_WEAPON != player.weapon:
        player.weapons_inventory.append(DEBUG_WEAPON)
        summary["weapons"] = 1

    # 2. Магазины
    for _ in range(DEBUG_MAGAZINES_COUNT):
        uid = player.add_magazine_instance(DEBUG_MAGAZINE)
        try:
            player.add_magazine_ammo(uid, DEBUG_AMMO_TYPE, 50)
            summary["ammo"] += 50
        except Exception as e:
            logger.error(f"[DEBUG] add_magazine_ammo {uid}: {e}")
        summary["magazines"] += 1

    # 3. Патроны в инвентарь
    from func.weapon_system.ammo import make_ammo_key
    from func.weapon_system.weapons import get_weapon

    wdata = get_weapon(DEBUG_WEAPON) or {}
    caliber = wdata.get("caliber", "5.45x39")
    inv_key = make_ammo_key(caliber, DEBUG_AMMO_TYPE)

    player.inventory[inv_key] = (
            player.inventory.get(inv_key, 0) + DEBUG_AMMO_COUNT
    )
    summary["ammo"] += DEBUG_AMMO_COUNT

    # 4. Ближний бой (ледоруб) — 0.4.8.7.3 фикс
    try:
        if not hasattr(player, 'melee_inventory') or player.melee_inventory is None:
            player.melee_inventory = []
        for melee_id in DEBUG_MELEE:
            if melee_id not in player.melee_inventory \
                    and melee_id != player.melee_weapon:
                player.melee_inventory.append(melee_id)
                summary["melee"] += 1
    except Exception as e:
        logger.error(f"[DEBUG] melee: {e}")

    # 5. Броня + шлем
    try:
        if not hasattr(player, 'armor_inventory') or player.armor_inventory is None:
            player.armor_inventory = []
        if DEBUG_ARMOR not in player.armor_inventory \
                and DEBUG_ARMOR != player.armor:
            player.armor_inventory.append(DEBUG_ARMOR)
            summary["armor"] = 1
        if DEBUG_HELMET not in player.armor_inventory \
                and DEBUG_HELMET != player.helmet:
            player.armor_inventory.append(DEBUG_HELMET)
            summary["helmet"] = 1
    except Exception as e:
        logger.error(f"[DEBUG] armor: {e}")

    # 6. Еда
    for food_id, count in DEBUG_FOOD_ITEMS:
        for _ in range(count):
            player.food_inventory.append(food_id)
            summary["food"] += 1

    # 7. Аптечки
    for medkit_id, count in DEBUG_MEDKITS:
        player.inventory[medkit_id] = (
                player.inventory.get(medkit_id, 0) + count
        )
        summary["medkits"] += count

    # 8. Расходники
    for item_id, count in DEBUG_CONSUMABLES:
        player.inventory[item_id] = (
                player.inventory.get(item_id, 0) + count
        )
        summary["consumables"] += count

    # 9. Гранаты
    for gid, count in DEBUG_GRENADES:
        player.add_grenade(gid, count)
        summary["grenades"] += count

    # 10. Ножи
    for kid, count in DEBUG_KNIVES:
        player.add_knife(kid, count)
        summary["knives"] += count

    # 11. Фильтры
    for fid, count in DEBUG_FILTERS:
        for _ in range(count):
            player.filters.append(fid)
            summary["filters"] += 1

    # 12. Никели
    player.inventory["никели"] = (
            player.inventory.get("никели", 0) + DEBUG_NICKELS_AMOUNT
    )
    summary["nickels"] = DEBUG_NICKELS_AMOUNT

    return summary


# ==================== МОДАЛКИ ====================

class DebugPasswordModal(discord.ui.Modal, title="🔐 Введите пароль"):
    password = discord.ui.TextInput(
        label="Пароль",
        placeholder="Введите пароль для активации debug-режима...",
        min_length=1,
        max_length=50,
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, game_manager):
        super().__init__()
        self.game_manager = game_manager

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.password.value != DEBUG_PASSWORD:
                await interaction.response.send_message(
                    "❌ Неверный пароль!", ephemeral=True
                )
                return

            player = self.game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message(
                    "❌ У вас нет персонажа! Создайте командой /start",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="🐛 Debug-режим активирован",
                description="Выберите действие:",
                color=discord.Color.dark_red()
            )
            view = DebugMenuView(self.game_manager)
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в debug-модалке: {e}")
            try:
                await interaction.response.send_message(
                    f"❌ Ошибка: {str(e)}", ephemeral=True
                )
            except:
                pass


class DebugMenuView(discord.ui.View):
    def __init__(self, game_manager):
        super().__init__(timeout=120)
        self.game_manager = game_manager

    @discord.ui.button(label="💰 +10000 никелей", style=discord.ButtonStyle.success)
    async def add_nickels(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        player = self.game_manager.get_player(interaction.user.id)
        if not player:
            return

        old = player.inventory.get('никели', 0)
        player.inventory['никели'] = old + DEBUG_NICKELS_AMOUNT
        await save_player(player)

        await interaction.response.send_message(
            f"✅ Выдано {DEBUG_NICKELS_AMOUNT} никелей! "
            f"(Было: {old}, стало: {player.inventory['никели']})",
            ephemeral=True,
        )

    @discord.ui.button(label="💠 Выдать лояльность",
                       style=discord.ButtonStyle.primary)
    async def add_loyalty_btn(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        embed = discord.Embed(
            title="💠 Выдача лояльности",
            description=(
                "Выберите фракцию, которой хотите выдать максимальную "
                "лояльность (500 очков, 5 ур.):"
            ),
            color=discord.Color.dark_gold()
        )
        view = DebugFactionSelectView(self.game_manager)
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )

    @discord.ui.button(label="💠 Лояльность торговцу",
                       style=discord.ButtonStyle.primary)
    async def add_trader_loyalty_btn(self, interaction: discord.Interaction,
                                     button: discord.ui.Button):
        embed = discord.Embed(
            title="💠 Лояльность торговцу",
            description=(
                "Выберите торговца, которому хотите выдать 200 очков "
                "(максимум, 2 ур.):"
            ),
            color=discord.Color.dark_gold()
        )
        view = DebugTraderSelectView(self.game_manager)
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )

    @discord.ui.button(label="🎁 Тестовый набор",
                       style=discord.ButtonStyle.danger)
    async def give_test_gear(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        player = self.game_manager.get_player(interaction.user.id)
        if not player:
            await interaction.response.send_message(
                "❌ Персонаж не найден.", ephemeral=True
            )
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            summary = _give_test_gear(player)
            await save_player(player)

            embed = discord.Embed(
                title="🎁 Тестовый набор выдан",
                description=(
                    "АК-2012 + 5 магазинов + 500 патронов.\n"
                    "Надень Бутовского Странника — он для поверхности."
                ),
                color=discord.Color.gold(),
            )
            embed.add_field(
                name="🔫 Оружие", value=f"1 (АК-2012)", inline=True
            )
            embed.add_field(
                name="📀 Магазины", value=str(summary["magazines"]),
                inline=True
            )
            embed.add_field(
                name="🎯 Патроны", value=str(summary["ammo"]), inline=True
            )
            embed.add_field(
                name="🧥 Броня", value=str(summary["armor"]), inline=True
            )
            embed.add_field(
                name="⛑️ Шлем", value=str(summary["helmet"]), inline=True
            )
            embed.add_field(
                name="🗡️ Ближний бой",
                value=f"1 (Ледоруб)" if summary["melee"] > 0 else "0",
                inline=True
            )
            embed.add_field(
                name="🍖 Еда", value=str(summary["food"]), inline=True
            )
            embed.add_field(
                name="💊 Аптечки", value=str(summary["medkits"]),
                inline=True
            )
            embed.add_field(
                name="💉 Расходники", value=str(summary["consumables"]),
                inline=True
            )
            embed.add_field(
                name="💣 Гранаты", value=str(summary["grenades"]),
                inline=True
            )
            embed.add_field(
                name="🔪 Ножи", value=str(summary["knives"]), inline=True
            )
            embed.add_field(
                name="🧪 Фильтры", value=str(summary["filters"]),
                inline=True
            )
            embed.add_field(
                name="💰 Никели", value=f"+{summary['nickels']}", inline=True
            )
            embed.set_footer(
                text="Надеть: /menu → Действия → Снаряжение"
            )

            try:
                await interaction.followup.send(
                    embed=embed, ephemeral=True
                )
            except Exception as e:
                logger.error(f"[DEBUG] followup: {e}")

        except Exception as e:
            logger.error(f"[DEBUG] give_test_gear: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    f"❌ Ошибка: {e}", ephemeral=True
                )
            except Exception:
                pass


class DebugFactionSelectView(discord.ui.View):
    def __init__(self, game_manager):
        super().__init__(timeout=60)
        self.game_manager = game_manager

        from func.factions import (
            get_all_factions, get_faction_emoji, get_faction_name,
        )

        options = []
        for fid, fdata in get_all_factions().items():
            emoji = get_faction_emoji(fid)
            options.append(discord.SelectOption(
                label=get_faction_name(fid)[:100],
                value=fid,
                emoji=emoji if isinstance(emoji, str) else None
            ))

        select = discord.ui.Select(
            placeholder="Выберите фракцию...",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.create_select_callback()
        self.add_item(select)

    def create_select_callback(self):
        async def callback(interaction: discord.Interaction):
            faction_id = interaction.data["values"][0]
            player = self.game_manager.get_player(interaction.user.id)
            if not player:
                return

            from func.factions import set_player_loyalty, get_faction_name

            set_player_loyalty(player, faction_id, 500)
            await save_player(player)

            await interaction.response.send_message(
                f"✅ Лояльность с фракцией "
                f"**{get_faction_name(faction_id)}** повышена до максимума "
                f"(500 очков)!",
                ephemeral=True,
            )
        return callback


class DebugTraderSelectView(discord.ui.View):
    def __init__(self, game_manager):
        super().__init__(timeout=60)
        self.game_manager = game_manager

        from func.independent_traders import (
            get_all_traders, get_trader_name, get_trader_emoji,
        )

        options = []
        for tid, tdata in get_all_traders().items():
            emoji = get_trader_emoji(tid)
            options.append(discord.SelectOption(
                label=get_trader_name(tid)[:100],
                value=tid,
                emoji=emoji if isinstance(emoji, str) else None
            ))

        select = discord.ui.Select(
            placeholder="Выберите торговца...",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.create_select_callback()
        self.add_item(select)

    def create_select_callback(self):
        async def callback(interaction: discord.Interaction):
            trader_id = interaction.data["values"][0]
            player = self.game_manager.get_player(interaction.user.id)
            if not player:
                return

            from func.independent_traders import (
                set_player_trader_loyalty, get_trader_name,
            )

            set_player_trader_loyalty(player, trader_id, 200)
            await save_player(player)

            await interaction.response.send_message(
                f"✅ Лояльность торговца "
                f"**{get_trader_name(trader_id)}** повышена до максимума "
                f"(200 очков, 2 ур.)!",
                ephemeral=True,
            )
        return callback


def setup_debug_commands(bot: commands.Bot, game_manager):
    @bot.tree.command(name="debug", description="[DEBUG] Меню отладки")
    async def cmd_debug(interaction: discord.Interaction):
        try:
            logger.info(
                f"🐛 Debug-команда вызвана от {interaction.user.id} "
                f"({interaction.user.name})"
            )

            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message(
                    "❌ У вас нет персонажа! Создайте командой /start",
                    ephemeral=True,
                )
                return

            await interaction.response.send_modal(
                DebugPasswordModal(game_manager)
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в cmd_debug: {e}")
            try:
                await interaction.response.send_message(
                    f"❌ Ошибка: {str(e)}", ephemeral=True
                )
            except:
                pass

    logger.info("🐛 Debug-команды зарегистрированы")