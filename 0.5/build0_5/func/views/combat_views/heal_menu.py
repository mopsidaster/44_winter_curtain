# -*- coding: utf-8 -*-
# func/views/combat_views/heal_menu.py - Меню аптечки в бою (0.4.4.8)
#
# ИСТОРИЯ:
#   0.4.4.7 — вынесено из views/combat.py
#   0.4.4.8 — safe_defer вынесен в utils/discord_helpers

import discord
import uuid

from ..helpers import combat_manager, handle_combat_action
from utils.discord_helpers import safe_defer
from utils.logger import get_logger

logger = get_logger()


class _CombatHealMenu(discord.ui.View):
    """Выбор аптечки для использования в бою."""

    def __init__(self, user_id: int, medkits: list):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.menu_id = uuid.uuid4().hex[:8]

        for idx, entry in enumerate(medkits[:6]):
            item = entry['data']
            item_id = entry['item_id']
            count = entry['count']
            heal = item.get('heal', 0)
            rad_red = item.get('radiation_reduction', 0)

            label = f"{item.get('emoji', '💊')} {item.get('name', item_id)} ({count})"
            if rad_red > 0:
                label += f" +{heal:.0f}HP -{rad_red}☢️"
            else:
                label += f" +{heal:.0f}HP"

            btn = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"cb_heal_{self.menu_id}_{idx}",
                row=idx // 2
            )
            btn.callback = self.create_heal_callback(item_id)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"cb_heal_back_{self.menu_id}",
            row=3
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_heal_callback(self, medkit_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return
            combat = combat_manager.get_combat(self.user_id)
            if not combat or not combat.can_act():
                await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
                return

            if not await safe_defer(interaction):
                return

            embed, view = await handle_combat_action(interaction, "heal_in_combat", medkit_id)
            if embed is None:
                return
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка heal_in_combat: {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            return

        from .action_submenu import _ActionSubmenu

        embed = combat.get_status_embed()
        embed.add_field(name="⚙️ Действие", value="Выберите вспомогательное действие:", inline=False)
        view = _ActionSubmenu(self.user_id)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            pass