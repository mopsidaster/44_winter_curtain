# -*- coding: utf-8 -*-
# func/views/combat_views/shell_reload.py - Зарядка ствола в бою (0.4.5.1)
#
# ИСТОРИЯ:
#   0.4.4.7   — вынесено из views/combat.py
#   0.4.4.8   — inline-проверки response.is_done() заменены на safe_defer
#   0.4.5.1   — ИСПРАВЛЕНИЕ: убран импорт update_combat_status (его нет в helpers).

import discord
import uuid

from ..helpers import combat_manager
from ...weapon_system import get_ammo_type
from config.map_config import WEAPONS
from utils.discord_helpers import safe_defer
from utils.logger import get_logger

logger = get_logger()


class _ShellReloadMenu(discord.ui.View):
    def __init__(self, user_id: int, menu_id: str, available: list):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.menu_id = uuid.uuid4().hex[:8]

        combat = combat_manager.get_combat(user_id)
        if not combat:
            return

        for idx, (atype, count) in enumerate(available[:5]):
            ammo_data = get_ammo_type(atype)
            label = f"{ammo_data.get('emoji', '🔘') if ammo_data else '🔘'} {atype} ({count} шт.)"
            btn = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"shell_load_{self.menu_id}_{idx}",
                row=idx // 2
            )
            btn.callback = self.create_load_callback(atype)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Отмена",
            style=discord.ButtonStyle.danger,
            custom_id=f"shell_back_{self.menu_id}",
            row=3
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_load_callback(self, ammo_type: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return

            combat = combat_manager.get_combat(self.user_id)
            if not combat:
                await interaction.response.send_message("❌ Бой завершён!", ephemeral=True)
                return

            weapon = WEAPONS.get(combat.player.weapon, {})
            capacity = weapon.get('shell_capacity', 0)
            current = combat.player.get_shell_ammo_count()
            free = capacity - current

            if free <= 0:
                await interaction.response.send_message("✅ Ствол уже полный!", ephemeral=True)
                return

            loaded = combat.player.reload_shell(ammo_type, free)
            if loaded <= 0:
                await interaction.response.send_message("❌ Не удалось зарядить!", ephemeral=True)
                return

            from database.db import save_player
            await save_player(combat.player)

            await interaction.response.send_message(
                f"✅ Заряжено **{loaded}** {ammo_type} в ствол.\n"
                f"🔋 Всего в стволе: **{combat.player.get_shell_ammo_count()}/{capacity}**\n\n"
                f"💡 Это действие не тратит ход. Можете стрелять!",
                ephemeral=True
            )

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
        view = _ActionSubmenu(self.user_id)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            pass