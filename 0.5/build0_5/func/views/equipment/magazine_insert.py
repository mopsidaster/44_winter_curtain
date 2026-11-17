# -*- coding: utf-8 -*-
# func/views/equipment/magazine_insert.py - Меню вставки магазина (0.4.4.7.1)
#
# Рефакторинг без изменения логики.

import discord
import uuid

from ..helpers import save_player, get_magazine
from utils.logger import get_logger

logger = get_logger()


class MagazineInsertMenu(discord.ui.View):
    def __init__(self, player, available_magazines):
        super().__init__(timeout=120)
        self.player = player
        self.player_id = player.user_id
        self.available = available_magazines
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        for idx, mag in enumerate(self.available[:5]):
            mag_data = get_magazine(mag["type_id"])
            if not mag_data:
                continue
            ammo_count = sum(mag["ammo"].values())
            capacity = mag_data.get("capacity", 0)

            button = discord.ui.Button(
                label=f"{mag_data.get('emoji', '📀')} {mag_data.get('name', mag['type_id'])} ({ammo_count}/{capacity})"[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"ins_{self.menu_id}_{idx}"
            )
            button.callback = self.create_callback(mag["uid"])
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"ins_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, uid: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player_id:
                    await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                    return

                await interaction.response.defer()

                mag = self.player.get_magazine_obj(uid)
                if not mag:
                    await interaction.followup.send("❌ Магазин не найден!", ephemeral=True)
                    return

                if mag.get("installed"):
                    await interaction.followup.send("❌ Магазин уже установлен!", ephemeral=True)
                    return

                if not self.player.install_magazine(uid):
                    await interaction.followup.send("❌ Не удалось установить магазин!", ephemeral=True)
                    return

                await save_player(self.player)
                mag_data = get_magazine(mag["type_id"])

                await interaction.followup.send(
                    f"✅ Магазин **{mag_data.get('name', '')}** установлен! (UID: `{uid}`)",
                    ephemeral=True
                )

                from .main_menu import EquipmentMenu
                from ._helpers import _build_equipment_embed

                view = EquipmentMenu(self.player)
                embed = _build_equipment_embed(self.player)
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка edit (mag insert): {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в insert callback ({uid}): {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            from .main_menu import EquipmentMenu
            from ._helpers import _build_equipment_embed

            view = EquipmentMenu(self.player)
            embed = _build_equipment_embed(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка back (mag insert): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (mag insert): {e}")