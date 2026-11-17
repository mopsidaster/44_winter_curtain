# -*- coding: utf-8 -*-
# func/views/equipment/shell_load.py - Меню зарядки ствола (0.4.4.7.1)
#
# Рефакторинг без изменения логики.

import discord
import uuid

from ..helpers import WEAPONS, save_player, get_ammo_type
from utils.logger import get_logger

logger = get_logger()


class _ShellLoadMenu(discord.ui.View):
    def __init__(self, player, available: list):
        super().__init__(timeout=120)
        self.player = player
        self.available = available
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        for idx, (atype, count) in enumerate(self.available[:5]):
            ammo_data = get_ammo_type(atype)
            emoji = ammo_data.get('emoji', '🔘') if ammo_data else '🔘'
            name = ammo_data.get('name', atype) if ammo_data else atype

            button = discord.ui.Button(
                label=f"{emoji} {name} ({count} шт.)"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"shell_load_{self.menu_id}_{idx}",
                row=idx // 3
            )
            button.callback = self.create_load_callback(atype)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"shell_load_back_{self.menu_id}",
            row=3
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_load_callback(self, ammo_type: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                    return

                await interaction.response.defer()

                weapon_id = self.player.weapon
                weapon_data = WEAPONS.get(weapon_id, {})
                capacity = weapon_data.get('shell_capacity', 0)
                current = self.player.get_shell_ammo_count()
                free = capacity - current

                if free <= 0:
                    await interaction.followup.send("✅ Ствол уже полный!", ephemeral=True)
                    return

                loaded = self.player.reload_shell(ammo_type, free)
                if loaded <= 0:
                    await interaction.followup.send("❌ Не удалось зарядить!", ephemeral=True)
                    return

                await save_player(self.player)

                ammo_data = get_ammo_type(ammo_type)
                name = ammo_data.get('name', ammo_type) if ammo_data else ammo_type

                await interaction.followup.send(
                    f"✅ Заряжено **{loaded}** {name} в ствол.\n"
                    f"🔋 Всего в стволе: **{self.player.get_shell_ammo_count()}/{capacity}**",
                    ephemeral=True
                )

                from .main_menu import EquipmentMenu
                from ._helpers import _build_equipment_embed

                view = EquipmentMenu(self.player)
                embed = _build_equipment_embed(self.player)
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка edit после зарядки ствола: {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в load_callback ({ammo_type}): {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            from .main_menu import EquipmentMenu
            from ._helpers import _build_equipment_embed

            view = EquipmentMenu(self.player)
            embed = _build_equipment_embed(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка back (shell load): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (shell load): {e}")