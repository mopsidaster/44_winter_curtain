# -*- coding: utf-8 -*-
# func/views/equipment/weapon_change.py - Меню смены оружия (0.4.4.7.1)
#
# Рефакторинг без изменения логики.

import discord
import uuid

from ..helpers import WEAPONS, save_player
from ...weapon_system import uninstall_all_modules
from utils.logger import get_logger

logger = get_logger()


class _WeaponChangeMenu(discord.ui.View):
    def __init__(self, player, weapons: list):
        super().__init__(timeout=120)
        self.player = player
        self.weapons = weapons
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        for idx, weapon_id in enumerate(self.weapons[:8]):
            wdata = WEAPONS.get(weapon_id, {})
            if not isinstance(wdata, dict):
                continue
            button = discord.ui.Button(
                label=f"{wdata.get('emoji', '🔫')} {wdata.get('name', weapon_id)}"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"weap_ch_{self.menu_id}_{idx}"
            )
            button.callback = self.create_callback(weapon_id)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"weap_ch_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, weapon_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                    return

                await interaction.response.defer()

                if weapon_id not in self.player.weapons_inventory:
                    await interaction.followup.send("❌ Оружие не найдено!", ephemeral=True)
                    return

                removed_modules = uninstall_all_modules(self.player)

                new_weapon_data = WEAPONS.get(weapon_id, {}) or {}
                new_weapon_mags = new_weapon_data.get('magazines', [])
                current_mag_uid = self.player.equipped_magazine

                if current_mag_uid:
                    cur_mag = self.player.get_magazine_obj(current_mag_uid)
                    if cur_mag and cur_mag['type_id'] not in new_weapon_mags:
                        self.player.uninstall_magazine()

                old_weapon = self.player.weapon
                self.player.weapons_inventory.remove(weapon_id)
                if old_weapon and old_weapon not in self.player.weapons_inventory:
                    self.player.weapons_inventory.append(old_weapon)
                self.player.weapon = weapon_id

                try:
                    self.player.apply_builtin_modules()
                except AttributeError:
                    pass

                if not self.player.equipped_magazine and new_weapon_mags:
                    for mag in self.player.get_uninstalled_magazines():
                        if mag['type_id'] in new_weapon_mags:
                            self.player.install_magazine(mag['uid'])
                            break

                await save_player(self.player)

                msg = f"✅ Сменено на **{new_weapon_data.get('name', weapon_id)}**"
                if removed_modules:
                    msg += f"\n⚠️ Снято модулей: {len(removed_modules)}"

                await interaction.followup.send(msg, ephemeral=True)

                from .main_menu import EquipmentMenu
                from ._helpers import _build_equipment_embed

                view = EquipmentMenu(self.player)
                embed = _build_equipment_embed(self.player)
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка edit после смены оружия: {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в weapon change callback ({weapon_id}): {e}")

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
                logger.error(f"Ошибка back (weapon change): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (weapon change): {e}")