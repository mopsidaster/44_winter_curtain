# -*- coding: utf-8 -*-
# func/views/combat_views/pvp_heal_menu.py - Выбор аптечки в PvP (0.4.6)

import discord
import uuid

from utils.discord_helpers import safe_defer
from utils.logger import get_logger

logger = get_logger()


class PvPHealMenu(discord.ui.View):
    def __init__(self, combat_id: str, medkits: list):
        super().__init__(timeout=60)
        self.combat_id = combat_id
        self.menu_id = uuid.uuid4().hex[:8]

        for idx, e in enumerate(medkits[:5]):
            item = e['data']
            btn = discord.ui.Button(
                label=f"{item.get('emoji','💊')} {item.get('name', e['item_id'])} ({e['count']})"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"pvh_{self.menu_id}_{idx}",
                row=idx // 3,
            )
            btn.callback = self.create_callback(e['item_id'])
            self.add_item(btn)

    def create_callback(self, item_id: str):
        async def callback(interaction: discord.Interaction):
            from ...combat.api_pvp import handle_pvp_action

            if not await safe_defer(interaction):
                return
            embed, view = await handle_pvp_action(
                interaction, self.combat_id, "heal", item_id
            )
            if embed is None:
                return
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка PvP heal: {e}")
        return callback