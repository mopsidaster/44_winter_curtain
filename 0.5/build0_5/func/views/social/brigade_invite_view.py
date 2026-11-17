# -*- coding: utf-8 -*-
# func/views/social/brigade_invite_view.py - Приглашение в группу (0.4.6)

import discord

from ...game_manager import game_manager
from ...social.brigade_manager import brigade_manager
from utils.logger import get_logger

logger = get_logger()


class BrigadeInviteView(discord.ui.View):
    def __init__(self, invite_id: str, inviter_id: int, invitee_id: int):
        super().__init__(timeout=60)
        self.invite_id = invite_id
        self.inviter_id = inviter_id
        self.invitee_id = invitee_id

    async def _not_invitee(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "❌ Это приглашение не для вас!", ephemeral=True
        )

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invitee_id:
            await self._not_invitee(interaction)
            return

        invite = brigade_manager.get_invite(self.invite_id)
        if not invite or invite.resolved:
            await interaction.response.send_message(
                "⏳ Приглашение недействительно.", ephemeral=True
            )
            return

        if brigade_manager.is_user_in_brigade(interaction.user.id):
            await interaction.response.send_message(
                "❌ Вы уже в группе!", ephemeral=True
            )
            brigade_manager.resolve_invite(self.invite_id)
            return

        brigade = brigade_manager.get_brigade(invite.brigade_id)
        if not brigade or brigade.is_full():
            await interaction.response.send_message(
                "❌ Группа уже полная или не существует.", ephemeral=True
            )
            brigade_manager.resolve_invite(self.invite_id)
            return

        await brigade_manager.add_member(brigade.brigade_id, interaction.user.id)
        brigade_manager.resolve_invite(self.invite_id)

        await interaction.response.send_message(
            f"✅ Вы вступили в группу **{brigade.name}**!", ephemeral=False
        )
        try:
            await interaction.message.edit(view=None)
        except Exception:
            pass

    @discord.ui.button(label="❌ Отказаться", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invitee_id:
            await self._not_invitee(interaction)
            return

        brigade_manager.resolve_invite(self.invite_id)
        await interaction.response.send_message(
            f"🚪 **{interaction.user.display_name}** отказался вступить в группу.",
            ephemeral=False,
        )
        try:
            await interaction.message.edit(view=None)
        except Exception:
            pass