# -*- coding: utf-8 -*-
# func/views/social/trade_view.py - UI обмена (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.6   — модалка «Собрать предложение» + подтверждения
#   0.4.7.2 — полностью новый UI: обе стороны выбирают предметы кнопками
#             (категория → предмет → количество). Деньги — отдельная модалка.
#             Никакого ввода ID вручную.

import discord

from ...game_manager import game_manager
from ...social.transfer import transfer_manager
from ...social.trade import apply_trade, player_has_money
from ...social.item_picker import (
    CategoryPickerView, ItemPickerView, CountPickerView,
    build_category_embed, build_items_embed, build_count_embed,
    apply_count_to_descriptor, describe_item,
)
from database.db import save_player
from utils.logger import get_logger

logger = get_logger()


# ==================== КОРНЕВОЕ МЕНЮ ОБМЕНА ====================

class TradeView(discord.ui.View):
    """
    Основное меню обмена. Обе стороны видят свои кнопки.
    """

    def __init__(self, trade_id: str, initiator_id: int, receiver_id: int):
        super().__init__(timeout=600)
        self.trade_id = trade_id
        self.initiator_id = initiator_id
        self.receiver_id = receiver_id

    def _get_trade(self):
        return transfer_manager.get_trade(self.trade_id)

    def build_embed(self) -> discord.Embed:
        trade = self._get_trade()
        if not trade:
            return discord.Embed(
                title="❌ Обмен недействителен",
                color=discord.Color.red(),
            )

        initiator = game_manager.get_player(trade.initiator_id)
        receiver = game_manager.get_player(trade.receiver_id)

        embed = discord.Embed(
            title="🤝 Обмен",
            description=(
                f"**{initiator.name if initiator else '?'}** ↔ "
                f"**{receiver.name if receiver else '?'}**\n\n"
                f"Обе стороны выбирают предметы через кнопки "
                f"и подтверждают обмен."
            ),
            color=discord.Color.blue(),
        )

        init_status = "✅" if trade.confirmed_by_initiator else "⏳"
        recv_status = "✅" if trade.confirmed_by_receiver else "⏳"

        embed.add_field(
            name=f"{init_status} Предложение {initiator.name if initiator else '?'}",
            value=self._format_offer(trade.initiator_items, trade.initiator_money),
            inline=False,
        )
        embed.add_field(
            name=f"{recv_status} Предложение {receiver.name if receiver else '?'}",
            value=self._format_offer(trade.receiver_items, trade.receiver_money),
            inline=False,
        )
        return embed

    def _format_offer(self, items: list, money: int) -> str:
        lines = []
        if money > 0:
            lines.append(f"💰 {money} никелей")
        for it in items:
            lines.append(f"• {describe_item(it)}")
        if not lines:
            return "_пусто_"
        return "\n".join(lines)

    # ==================== КНОПКИ ====================

    @discord.ui.button(label="📦 Выбрать предметы", style=discord.ButtonStyle.primary)
    async def pick_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.initiator_id, self.receiver_id):
            await interaction.response.send_message("❌ Не ваш обмен!", ephemeral=True)
            return

        trade = self._get_trade()
        if not trade or trade.resolved:
            await interaction.response.send_message(
                "⏳ Обмен недействителен.", ephemeral=True
            )
            return

        user_id = interaction.user.id
        builder = _TradeItemBuilder(self, user_id)
        await builder.start(interaction)

    @discord.ui.button(label="💰 Ввести сумму", style=discord.ButtonStyle.primary)
    async def money(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.initiator_id, self.receiver_id):
            await interaction.response.send_message("❌ Не ваш обмен!", ephemeral=True)
            return

        trade = self._get_trade()
        if not trade or trade.resolved:
            await interaction.response.send_message(
                "⏳ Обмен недействителен.", ephemeral=True
            )
            return

        await interaction.response.send_modal(
            _TradeMoneyModal(self.trade_id, interaction.user.id)
        )

    @discord.ui.button(label="✅ Подтвердить", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.initiator_id, self.receiver_id):
            await interaction.response.send_message("❌ Не ваш обмен!", ephemeral=True)
            return

        trade = self._get_trade()
        if not trade or trade.resolved:
            await interaction.response.send_message(
                "⏳ Обмен недействителен.", ephemeral=True
            )
            return

        if interaction.user.id == self.initiator_id:
            trade.confirmed_by_initiator = True
        else:
            trade.confirmed_by_receiver = True

        if trade.confirmed_by_initiator and trade.confirmed_by_receiver:
            initiator = game_manager.get_player(trade.initiator_id)
            receiver = game_manager.get_player(trade.receiver_id)
            if not initiator or not receiver:
                await interaction.response.send_message(
                    "❌ Один из игроков не найден.", ephemeral=True
                )
                transfer_manager.resolve_trade(self.trade_id)
                return

            ok, reason = apply_trade(trade, initiator, receiver)
            if not ok:
                await interaction.response.send_message(
                    f"❌ Не удалось обменять: {reason}", ephemeral=True
                )
                transfer_manager.resolve_trade(self.trade_id)
                return

            transfer_manager.resolve_trade(self.trade_id)
            await save_player(initiator)
            await save_player(receiver)

            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="✅ Обмен совершён!",
                    description=f"**{initiator.name}** ↔ **{receiver.name}**",
                    color=discord.Color.green(),
                ),
                view=None,
            )
            return

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.initiator_id, self.receiver_id):
            await interaction.response.send_message("❌ Не ваш обмен!", ephemeral=True)
            return

        transfer_manager.resolve_trade(self.trade_id)
        await interaction.response.edit_message(
            embed=discord.Embed(title="🚪 Обмен отменён", color=discord.Color.dark_gray()),
            view=None,
        )


# ==================== МОДАЛКА ВВОДА ДЕНЕГ ====================

class _TradeMoneyModal(discord.ui.Modal, title="💰 Сумма никелей"):
    amount = discord.ui.TextInput(
        label="Сколько никелей вы предлагаете?",
        placeholder="0",
        required=False,
        max_length=10,
    )

    def __init__(self, trade_id: str, user_id: int):
        super().__init__()
        self.trade_id = trade_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        trade = transfer_manager.get_trade(self.trade_id)
        if not trade or trade.resolved:
            await interaction.response.send_message(
                "⏳ Обмен недействителен.", ephemeral=True
            )
            return

        try:
            amount = int((self.amount.value or "0").strip())
        except ValueError:
            amount = 0
        amount = max(0, amount)

        player = game_manager.get_player(self.user_id)
        if not player:
            await interaction.response.send_message("❌ Игрок не найден.", ephemeral=True)
            return

        if amount > 0 and not player_has_money(player, amount):
            await interaction.response.send_message(
                f"❌ У вас только {player.inventory.get('никели', 0)} никелей.",
                ephemeral=True,
            )
            return

        if self.user_id == trade.initiator_id:
            trade.initiator_money = amount
            trade.confirmed_by_initiator = False
        else:
            trade.receiver_money = amount
            trade.confirmed_by_receiver = False

        view = TradeView(self.trade_id, trade.initiator_id, trade.receiver_id)
        try:
            await interaction.response.edit_message(
                embed=view.build_embed(), view=view
            )
        except Exception:
            await interaction.response.send_message(
                f"✅ Сумма сохранена: {amount} никелей.", ephemeral=True
            )


# ==================== ПОСТРОИТЕЛЬ ПРЕДМЕТОВ ДЛЯ ОДНОЙ СТОРОНЫ ====================

class _TradeItemBuilder:
    """
    Сессия выбора предметов для одной стороны обмена.
    Сохраняет выбранные предметы в trade.initiator_items / trade.receiver_items.
    """

    def __init__(self, trade_view: TradeView, user_id: int):
        self.trade_view = trade_view
        self.user_id = user_id
        self.trade_id = trade_view.trade_id

    def _get_player(self):
        return game_manager.get_player(self.user_id)

    def _get_trade(self):
        return transfer_manager.get_trade(self.trade_id)

    def _is_initiator(self) -> bool:
        trade = self._get_trade()
        return bool(trade and self.user_id == trade.initiator_id)

    def _get_current_items(self) -> list:
        trade = self._get_trade()
        if not trade:
            return []
        return trade.initiator_items if self._is_initiator() else trade.receiver_items

    def _set_current_items(self, items: list):
        trade = self._get_trade()
        if not trade:
            return
        if self._is_initiator():
            trade.initiator_items = items
            trade.confirmed_by_initiator = False
        else:
            trade.receiver_items = items
            trade.confirmed_by_receiver = False

    async def start(self, interaction: discord.Interaction):
        await self._show_categories(interaction)

    async def _show_categories(self, interaction: discord.Interaction):
        player = self._get_player()
        if not player:
            await interaction.response.send_message("❌ Игрок не найден.", ephemeral=True)
            return

        embed = self._build_embed(
            title="📦 Что вы предлагаете?",
            hint="Выберите категорию предметов.",
        )

        view = CategoryPickerView(
            player=player,
            on_pick=self._on_category_picked,
            back_label="🔙 К обмену",
        )
        for child in view.children:
            if child.custom_id.endswith("_back_" + view.menu_id):
                child.callback = self._back_to_trade

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _on_category_picked(self, interaction: discord.Interaction, category_id: str):
        player = self._get_player()
        if not player:
            return

        embed = build_items_embed(
            player, category_id,
            title="📦 Выбор предмета",
        )
        embed = self._append_selected(embed)

        view = ItemPickerView(
            player=player,
            category_id=category_id,
            on_pick=self._on_item_picked,
            back_callback=self._back_to_categories,
        )

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _on_item_picked(self, interaction: discord.Interaction, item: dict):
        if item.get("count") and int(item.get("count", 1)) > 1:
            embed = build_count_embed(item)
            embed = self._append_selected(embed)
            view = CountPickerView(
                player=self._get_player(),
                item=item,
                on_pick=lambda i, n: self._on_count_picked(i, item, n),
                back_callback=self._back_to_categories,
            )
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except Exception:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

        items = list(self._get_current_items())
        items.append(apply_count_to_descriptor(item, 1))
        self._set_current_items(items)
        await self._show_categories(interaction)

    async def _on_count_picked(self, interaction: discord.Interaction, item: dict, count: int):
        items = list(self._get_current_items())
        items.append(apply_count_to_descriptor(item, count))
        self._set_current_items(items)
        await self._show_categories(interaction)

    async def _back_to_categories(self, interaction: discord.Interaction):
        await self._show_categories(interaction)

    async def _back_to_trade(self, interaction: discord.Interaction):
        trade = self._get_trade()
        if not trade:
            return
        view = TradeView(self.trade_id, trade.initiator_id, trade.receiver_id)
        try:
            await interaction.response.edit_message(
                embed=view.build_embed(), view=view
            )
        except Exception:
            pass

    def _append_selected(self, embed: discord.Embed) -> discord.Embed:
        items = self._get_current_items()
        if items:
            text = "\n".join(f"• {describe_item(it)}" for it in items[:10])
            if len(items) > 10:
                text += f"\n... и ещё {len(items) - 10}"
            embed.add_field(
                name=f"✅ Уже выбрано ({len(items)})",
                value=text,
                inline=False,
            )
        return embed

    def _build_embed(self, title: str, hint: str) -> discord.Embed:
        trade = self._get_trade()
        player = self._get_player()
        initiator = game_manager.get_player(trade.initiator_id) if trade else None
        receiver = game_manager.get_player(trade.receiver_id) if trade else None

        embed = discord.Embed(
            title=title,
            description=(
                f"**{initiator.name if initiator else '?'}** ↔ "
                f"**{receiver.name if receiver else '?'}**\n\n"
                f"{hint}"
            ),
            color=discord.Color.blue(),
        )
        return self._append_selected(embed)