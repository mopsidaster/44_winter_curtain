# -*- coding: utf-8 -*-
# func/views/combat_views/pvp_invite_view.py - Приглашение на PvP (0.4.6)
#
# ИСТОРИЯ:
#   0.4.6 — новый файл.
#
# Кнопки: Accept / Decline / Убежать.
# Видят все, но нажимать может только цель.

import random
import discord

from utils.logger import get_logger

logger = get_logger()


class PvPInviteView(discord.ui.View):
    """Кнопки приглашения на PvP-бой."""

    def __init__(self, invite_id: str, initiator_id: int, target_id: int):
        super().__init__(timeout=60)
        self.invite_id = invite_id
        self.initiator_id = initiator_id
        self.target_id = target_id

    async def _not_target(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "❌ Это приглашение не для вас!", ephemeral=True
        )

    @discord.ui.button(label="⚔️ Принять", style=discord.ButtonStyle.danger)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await self._not_target(interaction)
            return
        from ...combat.pvp_manager import pvp_manager
        invite = pvp_manager.get_invite(self.invite_id)
        if not invite or invite.resolved:
            await interaction.response.send_message(
                "⏳ Приглашение больше не действительно.", ephemeral=True
            )
            return
        await interaction.response.defer()
        pvp_manager.resolve_invite(self.invite_id)

        from .pvp_start import start_pvp_from_invite
        await start_pvp_from_invite(interaction, invite)

    @discord.ui.button(label="❌ Отказаться", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await self._not_target(interaction)
            return

        from ...combat.pvp_manager import pvp_manager
        pvp_manager.resolve_invite(self.invite_id)

        await interaction.response.send_message(
            f"🕊️ **{interaction.user.display_name}** отказался от боя.",
            ephemeral=False
        )
        try:
            await interaction.message.edit(view=None)
        except Exception:
            pass

    @discord.ui.button(label="🏃 Убежать (25%)", style=discord.ButtonStyle.primary)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await self._not_target(interaction)
            return

        from ...combat.pvp_manager import pvp_manager
        invite = pvp_manager.get_invite(self.invite_id)
        if not invite or invite.resolved:
            await interaction.response.send_message(
                "⏳ Приглашение больше не действительно.", ephemeral=True
            )
            return

        await interaction.response.defer()

        success = random.randint(1, 100) <= 25
        pvp_manager.resolve_invite(self.invite_id)

        if success:
            await interaction.followup.send(
                f"🏃 **{interaction.user.display_name}** сбежал! Бой отменён.",
                ephemeral=False
            )
            try:
                await interaction.message.edit(view=None)
            except Exception:
                pass
            return

        await interaction.followup.send(
            f"⚠️ **{interaction.user.display_name}** пытался сбежать, но не вышло!",
            ephemeral=False
        )

        from .pvp_start import start_pvp_from_invite
        await start_pvp_from_invite(interaction, invite)