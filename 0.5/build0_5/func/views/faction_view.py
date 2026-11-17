# -*- coding: utf-8 -*-
# func/views/faction_view.py - Меню фракций (0.4.8)
#
# ИСТОРИЯ:
#   0.4.8 — новый файл. Фикс кастомных эмодзи в кнопках.

import discord
import uuid
import re

from .helpers import game_manager, save_player
from ..factions import (
    get_all_factions, get_faction_data, get_faction_name, get_faction_emoji,
    get_player_relation_to, get_relation_meta,
    get_player_loyalty, get_player_loyalty_level,
    get_loyalty_progress,
)
from utils.logger import get_logger

logger = get_logger()

def _extract_emoji_for_button(emoji_str: str):
    """
    Извлекает кастомный эмодзи из строки формата <:name:id> или <a:name:id>
    и возвращает объект discord.PartialEmoji.
    Если эмодзи стандартный (юникод) — возвращает строку.
    """
    if not emoji_str:
        return None

    # Ищем паттерн кастомного эмодзи
    match = re.match(r'<(a?):([a-zA-Z0-9_]+):(\d+)>', emoji_str)
    if match:
        animated = bool(match.group(1))
        name = match.group(2)
        id = int(match.group(3))
        return discord.PartialEmoji(name=name, id=id, animated=animated)

    # Обычный юникод-эмодзи
    return emoji_str


def build_factions_embed(player) -> discord.Embed:
    """Обзор всех фракций + статус игрока."""
    current_faction = getattr(player, 'faction', 'loners')

    embed = discord.Embed(
        title="🏴 Фракции 44: White Curtain",
        description=(
            f"Ваша фракция: **{get_faction_emoji(current_faction)} "
            f"{get_faction_name(current_faction)}**\n"
            f"_Список всех известных фракций Метро_"
        ),
        color=discord.Color.dark_gold(),
    )

    for fid, fdata in get_all_factions().items():
        relation = get_player_relation_to(player, fid)
        relation_meta = get_relation_meta(relation)
        loyalty_level = get_player_loyalty_level(player, fid)
        loyalty_points = get_player_loyalty(player, fid)

        faction_name = fdata.get("name", fid)
        faction_emoji = get_faction_emoji(fid)
        is_current = (fid == current_faction)

        marker = " ⬅️ вы здесь" if is_current else ""

        embed.add_field(
            name=f"{faction_emoji} {faction_name}{marker}",
            value=(
                f"_{fdata.get('description', '')}_\n"
                f"{relation_meta['emoji']} Отношение: **{relation_meta['name']}**\n"
                f"💠 Лояльность: **{loyalty_points}** очков (ур. {loyalty_level}/5)"
            ),
            inline=False,
        )

    embed.set_footer(text="Подробнее: /faction_info <id>")
    return embed


def build_faction_detail_embed(player, faction_id: str) -> discord.Embed:
    """Подробная информация о фракции."""
    fdata = get_faction_data(faction_id)
    if not fdata:
        return discord.Embed(
            title="❌ Фракция не найдена",
            description=f"ID `{faction_id}` не существует.",
            color=discord.Color.red(),
        )

    faction_emoji = get_faction_emoji(faction_id)
    faction_name = fdata.get("name", faction_id)
    current_faction = getattr(player, 'faction', 'loners')
    is_member = (current_faction == faction_id)

    relation = get_player_relation_to(player, faction_id)
    relation_meta = get_relation_meta(relation)
    loyalty_points = get_player_loyalty(player, faction_id)
    loyalty_level = get_player_loyalty_level(player, faction_id)
    progress = get_loyalty_progress(player, faction_id)

    embed = discord.Embed(
        title=f"{faction_emoji} {faction_name}",
        description=fdata.get("description", ""),
        color=discord.Color.dark_gold(),
    )

    embed.add_field(
        name="📊 Ваш статус",
        value=(
                f"{relation_meta['emoji']} Отношение: **{relation_meta['name']}**\n"
                f"💠 Лояльность: **{loyalty_points}** очков (ур. {loyalty_level}/5)"
                + ("\n👑 **Вы член этой фракции!**" if is_member else "")
        ),
        inline=False,
    )

    # Прогресс до следующего уровня
    if progress.get("next_threshold"):
        remaining = progress["next_threshold"] - loyalty_points
        bar_len = 10
        filled = int(progress["progress"] * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        embed.add_field(
            name="📈 Прогресс лояльности",
            value=(
                f"`[{bar}]`\n"
                f"Следующий уровень: **{progress['next_level']}** "
                f"(ещё **{remaining}** очков)"
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="📈 Прогресс",
            value="🏆 Максимальный уровень лояльности достигнут!",
            inline=False,
        )

    # Список бонусов
    levels = fdata.get("loyalty_levels", {})
    bonuses_text = []
    for lvl in range(1, 6):
        lvl_data = levels.get(str(lvl), {})
        points = lvl_data.get("points", 0)
        unlocked = "✅" if loyalty_level >= lvl else "🔒"

        bonuses = []
        for b in lvl_data.get("bonuses", []):
            desc = b.get("description", "")
            if desc:
                bonuses.append(desc)

        if lvl_data.get("can_join"):
            bonuses.append("Возможность вступить во фракцию")

        bonus_str = "; ".join(bonuses) if bonuses else "—"
        bonuses_text.append(f"{unlocked} **Ур. {lvl}** ({points} очк.): {bonus_str}")

    embed.add_field(
        name="🎁 Бонусы уровней",
        value="\n".join(bonuses_text),
        inline=False,
    )

    return embed


class FactionsMenu(discord.ui.View):
    """Меню фракций со списком кнопок на каждую фракцию."""

    def __init__(self, player, parent_view=None):
        super().__init__(timeout=300)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self.parent_view = parent_view
        self._add_buttons()

    def _add_buttons(self):
        factions = get_all_factions()
        current = getattr(self.player, 'faction', 'loners')

        for idx, (fid, fdata) in enumerate(factions.items()):
            emoji_str = get_faction_emoji(fid)
            emoji_obj = _extract_emoji_for_button(emoji_str)

            name = fdata.get("name", fid)
            marker = " ⬅️" if fid == current else ""
            label = f"{name}{marker}".strip()

            btn = discord.ui.Button(
                label=label[:80],
                emoji=emoji_obj,  # <-- Передаем эмодзи отдельно от текста
                style=discord.ButtonStyle.success if fid == current else discord.ButtonStyle.primary,
                custom_id=f"fac_{fid}_{self.menu_id}",
                row=idx // 3,
            )
            btn.callback = self.create_faction_callback(fid)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="Назад в меню",
            emoji="🔙",
            style=discord.ButtonStyle.secondary,
            custom_id=f"fac_back_{self.menu_id}",
            row=4,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_faction_callback(self, faction_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваше меню!", ephemeral=True)
                return

            embed = build_faction_detail_embed(self.player, faction_id)
            new_view = FactionDetailView(self.player, faction_id)
            try:
                await interaction.response.edit_message(embed=embed, view=new_view)
            except Exception as e:
                logger.error(f"Ошибка faction_callback: {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваше меню!", ephemeral=True)
            return
        try:
            from .main_menu import MainMenu
            from ..map_data import MAP_DATA

            player = self.player
            station_data = MAP_DATA["станции"].get(player.location, {})
            total_hp = player.get_total_health()
            max_hp = player.get_max_total_health()

            embed = discord.Embed(
                title="🎮 Меню 44: White Curtain",
                description=f"Добро пожаловать, **{player.name}**!\nУровень: **{player.level}**",
                color=discord.Color.blue(),
            )
            embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
            embed.add_field(name="📍 Локация", value=station_data.get("name", "?"), inline=True)
            embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)

            await interaction.response.edit_message(embed=embed, view=MainMenu())
        except Exception as e:
            logger.error(f"Ошибка faction back: {e}")


class FactionDetailView(discord.ui.View):
    """Детальная view для одной фракции."""

    def __init__(self, player, faction_id: str):
        super().__init__(timeout=300)
        self.player = player
        self.faction_id = faction_id
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        current_faction = getattr(self.player, 'faction', 'loners')
        is_member = (current_faction == self.faction_id)

        # Обновить
        refresh_btn = discord.ui.Button(
            label="Обновить",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
            custom_id=f"facdt_refresh_{self.menu_id}",
            row=0,
        )
        refresh_btn.callback = self.refresh_callback
        self.add_item(refresh_btn)

        # Показать путь (если не член и лояльность ≥ 3)
        from ..factions import can_join_faction
        can_join, reason = can_join_faction(self.player, self.faction_id)

        join_btn = discord.ui.Button(
            label="Вступить во фракцию" if can_join else "Вступление",
            emoji="✅" if can_join else "🔒",
            style=discord.ButtonStyle.success if can_join else discord.ButtonStyle.secondary,
            custom_id=f"facdt_join_{self.menu_id}",
            row=0,
            disabled=(not can_join),
        )
        join_btn.callback = self.join_callback
        self.add_item(join_btn)

        back_btn = discord.ui.Button(
            label="К фракциям",
            emoji="🔙",
            style=discord.ButtonStyle.secondary,
            custom_id=f"facdt_back_{self.menu_id}",
            row=1,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def refresh_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваше меню!", ephemeral=True)
            return
        embed = build_faction_detail_embed(self.player, self.faction_id)
        await interaction.response.edit_message(embed=embed, view=self)

    async def join_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваше меню!", ephemeral=True)
            return

        from ..factions import join_faction
        ok, message = join_faction(self.player, self.faction_id)
        if ok:
            await save_player(self.player)

        embed = build_faction_detail_embed(self.player, self.faction_id)
        new_view = FactionDetailView(self.player, self.faction_id)

        try:
            await interaction.response.edit_message(embed=embed, view=new_view)
        except Exception as e:
            logger.error(f"join_callback edit: {e}")

        try:
            await interaction.followup.send(message, ephemeral=True)
        except Exception:
            pass

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваше меню!", ephemeral=True)
            return
        embed = build_factions_embed(self.player)
        new_view = FactionsMenu(self.player)
        try:
            await interaction.response.edit_message(embed=embed, view=new_view)
        except Exception as e:
            logger.error(f"detail back: {e}")