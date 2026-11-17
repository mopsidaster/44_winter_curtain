# -*- coding: utf-8 -*-
# func/views/trade/_helpers.py - Общие хелперы торговли (0.4.4.8)
#
# Рефакторинг без изменения логики.
# safe-хелперы вынесены в utils/discord_helpers.py и реэкспортируются
# под прежними именами (_safe_defer и т.д.) для обратной совместимости.

import discord

from ..helpers import (
    game_manager, BALANCE, get_trade_discount, get_filter_discount,
    get_filter,
)
from utils.discord_helpers import (
    safe_defer as _safe_defer,
    safe_edit as _safe_edit,
    safe_followup as _safe_followup,
)
from utils.logger import get_logger

logger = get_logger()

TOTAL_TRADE_PAGES = 3


# ==================== EMBED ====================

def _build_trade_page_embed(player, page: int) -> discord.Embed:
    embed = discord.Embed(
        title="🏪 Торговая зона",
        description=f"Страница **{page}/2**. Выберите действие.",
        color=discord.Color.gold()
    )

    if page == 1:
        embed.add_field(
            name="🛒 Купить",
            value="• 💊 **Аптека**\n• 🔧 **Мастерская**\n• 🍖 **Еда**\n"
                  "• 🔫 **Оружие**\n• 🧥 **Снаряжение**",
            inline=False
        )
    else:
        embed.add_field(
            name="💰 Продать",
            value="• **Продать всё** — хлам, оружие, броня, модули",
            inline=False
        )

    from ...factions import get_station_discount_percent
    faction_discount = get_station_discount_percent(player, player.location)
    if faction_discount > 0:
        embed.add_field(
            name="🏷️ Скидка фракции",
            value=f"**{faction_discount}%**",
            inline=False,
        )

    embed.set_footer(text=f"💰 Ваши никели: {player.inventory.get('никели', 0)} • Стр. {page}/2")
    return embed


def _build_workshop_embed(player) -> discord.Embed:
    embed = discord.Embed(
        title="🔧 Мастерская",
        description="Здесь можно купить фильтры и отремонтировать противогаз.",
        color=discord.Color.blue()
    )

    filter_discount = get_filter_discount(game_manager)
    trade_discount = get_trade_discount(game_manager)
    total_discount = trade_discount * filter_discount

    filter_lines = []
    for fid in ["поврежденный", "поношенный", "нетронутый", "усиленный"]:
        f = get_filter(fid)
        if f:
            price = int(f.get('price', 0) * total_discount)
            filter_lines.append(
                f"{f.get('emoji', '🧪')} **{f.get('name', fid)}** — "
                f"прочность {f.get('durability', 0)}, цена **{price}**"
            )

    embed.add_field(
        name="🧪 Фильтры",
        value="\n".join(filter_lines) if filter_lines else "Нет в наличии",
        inline=False
    )

    if player.has_gas_mask:
        current_dur = player.gas_mask.get('прочность', 0)
        max_dur = player.get_gas_mask_max_durability()
        state = player.gas_mask.get('состояние', 'поношенный')
        state_map = {"целый": "🟢 целый", "поношенный": "🟡 поношенный", "разбитый": "🔴 разбитый"}
        state_text = state_map.get(state, state)

        repair_price = int(BALANCE['prices']['repair'] * trade_discount)

        embed.add_field(
            name="🎒 Противогаз",
            value=f"Состояние: **{state_text}**\n"
                  f"Прочность: **{current_dur:.0f}/{max_dur:.0f}**\n"
                  f"🔧 Ремонт: **{repair_price}** никелей",
            inline=False
        )
    else:
        embed.add_field(name="🎒 Противогаз", value="❌ У вас нет противогаза", inline=False)

    embed.set_footer(text=f"💰 Ваши никели: {player.inventory.get('никели', 0)}")
    return embed