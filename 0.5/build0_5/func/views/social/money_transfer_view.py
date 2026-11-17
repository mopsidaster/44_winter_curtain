# -*- coding: utf-8 -*-
# func/views/social/money_transfer_view.py - UI передачи денег (0.4.6)

import discord

from ...game_manager import game_manager
from ...social.transfer import transfer_manager
from ...social.trade import apply_money
from database.db import save_player
from utils.logger import get_logger

logger = get_logger()


class MoneyTransferView(discord.ui.View):
    def __init__(self, transfer_id: str, sender_id: int, receiver_id: int):
        super().__init__(timeout=600)
        self.transfer_id = transfer_id
        self.sender_id = sender_id
        self.receiver_id = receiver_id

    async def _not_receiver(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "❌ Это предложение не для вас!", ephemeral=True
        )

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receiver_id:
            await self._not_receiver(interaction)
            return

        t = transfer_manager.get_money_transfer(self.transfer_id)
        if not t or t.resolved:
            await interaction.response.send_message(
                "⏳ Предложение недействительно.", ephemeral=True
            )
            return

        sender = game_manager.get_player(t.sender_id)
        receiver = game_manager.get_player(t.receiver_id)
        if not sender or not receiver:
            await interaction.response.send_message(
                "❌ Один из игроков не найден.", ephemeral=True
            )
            transfer_manager.resolve_money(self.transfer_id)
            return

        if not apply_money(sender, receiver, t.amount):
            await interaction.response.send_message(
                "❌ У отправителя уже недостаточно никелей!", ephemeral=True
            )
            transfer_manager.resolve_money(self.transfer_id)
            return

        transfer_manager.resolve_money(self.transfer_id)
        await save_player(sender)
        await save_player(receiver)

        await interaction.response.send_message(
            f"💰 **{receiver.name}** получил **{t.amount}** никелей от **{sender.name}**!",
            ephemeral=False,
        )
        try:
            await interaction.message.edit(view=None)
        except Exception:
            pass

    @discord.ui.button(label="❌ Отказаться", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receiver_id:
            await self._not_receiver(interaction)
            return

        transfer_manager.resolve_money(self.transfer_id)
        await interaction.response.send_message(
            f"🚪 **{interaction.user.display_name}** отказался от передачи.",
            ephemeral=False,
        )
        try:
            await interaction.message.edit(view=None)
        except Exception:
            pass