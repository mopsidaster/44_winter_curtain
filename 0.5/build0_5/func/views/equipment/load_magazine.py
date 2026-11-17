# -*- coding: utf-8 -*-
# func/views/equipment/load_magazine.py - Меню зарядки магазина (0.4.6.3)
#
# ИСТОРИЯ:
#   0.4.4.7.1 — рефакторинг
#   0.4.6.3   — патроны хранятся как '<caliber>|<type>'

import discord
import uuid

from ..helpers import (
    save_player, get_magazine, get_ammo_type, get_caliber_ammo_types,
)
from config.map_config import AMMO
from utils.logger import get_logger

logger = get_logger()


class EquipmentLoadMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.player_id = player.user_id
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        uninstalled = self.player.get_uninstalled_magazines()

        if not uninstalled:
            button = discord.ui.Button(
                label="❌ Нет вытащенных магазинов",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"eq_load_empty_{self.menu_id}"
            )
            self.add_item(button)
        else:
            for idx, mag in enumerate(uninstalled[:5]):
                mag_data = get_magazine(mag["type_id"])
                if not mag_data:
                    continue
                ammo_count = sum(mag["ammo"].values())
                capacity = mag_data.get("capacity", 0)

                button = discord.ui.Button(
                    label=f"{mag_data.get('emoji', '📀')} {mag_data.get('name', mag['type_id'])} ({ammo_count}/{capacity})"[:80],
                    style=discord.ButtonStyle.primary,
                    custom_id=f"eq_load_{self.menu_id}_{idx}"
                )
                button.callback = self.create_mag_callback(mag["uid"])
                self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"eq_load_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_mag_callback(self, uid: str):
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

                mag_data = get_magazine(mag["type_id"])
                if not mag_data:
                    await interaction.followup.send("❌ Ошибка данных!", ephemeral=True)
                    return

                caliber = mag_data.get("caliber")
                caliber_name = AMMO.get('calibers', {}).get(caliber, {}).get('name', caliber)
                ammo_types = get_caliber_ammo_types(caliber)

                embed = discord.Embed(
                    title=f"🎯 Зарядка {mag_data.get('name', '')}",
                    description=f"Калибр: **{caliber_name}**\n"
                                f"Магазин: `{uid}`\n\n"
                                f"Выберите тип патронов (только {caliber_name}):",
                    color=discord.Color.blue()
                )

                # 0.4.6.3: ключ '<caliber>|<type>'
                from ...weapon_system.ammo import make_ammo_key
                for ammo_type in ammo_types:
                    ammo = get_ammo_type(ammo_type)
                    if ammo:
                        inv_key = make_ammo_key(caliber, ammo_type)
                        count = self.player.inventory.get(inv_key, 0)
                        embed.add_field(
                            name=f"{ammo.get('emoji', '🔘')} {ammo.get('name', ammo_type)}",
                            value=f"В наличии: {count} шт.\n{ammo.get('description', '')}",
                            inline=False
                        )

                view = EquipmentLoadSelectMenu(self.player, uid)
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка edit (load mag select): {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в mag callback ({uid}): {e}")

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
                logger.error(f"Ошибка back (load menu): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (load menu): {e}")


class EquipmentLoadSelectMenu(discord.ui.View):
    def __init__(self, player, magazine_uid: str):
        super().__init__(timeout=120)
        self.player = player
        self.player_id = player.user_id
        self.magazine_uid = magazine_uid
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        from ...weapon_system import get_caliber_ammo_types
        from ...weapon_system.ammo import make_ammo_key

        mag = self.player.get_magazine_obj(self.magazine_uid)
        if not mag:
            return
        mag_data = get_magazine(mag["type_id"])
        if not mag_data:
            return

        caliber = mag_data.get("caliber")
        ammo_types = get_caliber_ammo_types(caliber)

        for idx, ammo_type in enumerate(ammo_types):
            ammo = get_ammo_type(ammo_type)
            if ammo:
                inv_key = make_ammo_key(caliber, ammo_type)
                count = self.player.inventory.get(inv_key, 0)
                if count > 0:
                    button = discord.ui.Button(
                        label=f"{ammo.get('emoji', '🔘')} {ammo.get('name', ammo_type)} ({count} шт.)"[:80],
                        style=discord.ButtonStyle.success,
                        custom_id=f"eq_sel_{self.menu_id}_{idx}"
                    )
                    button.callback = self.create_callback(inv_key)
                    self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"eq_sel_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, inv_key: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player_id:
                    await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                    return

                await interaction.response.defer()

                mag = self.player.get_magazine_obj(self.magazine_uid)
                if not mag:
                    await interaction.followup.send("❌ Магазин не найден!", ephemeral=True)
                    return

                mag_data = get_magazine(mag["type_id"])
                if not mag_data:
                    await interaction.followup.send("❌ Ошибка данных!", ephemeral=True)
                    return

                from ...weapon_system.ammo import parse_ammo_key
                from ...weapon_system import get_caliber_ammo_types

                incoming_caliber, plain_type = parse_ammo_key(inv_key)
                mag_caliber = mag_data.get("caliber")

                # Проверка калибра
                if incoming_caliber is not None and incoming_caliber != mag_caliber:
                    await interaction.followup.send(
                        f"❌ Патрон калибра **{incoming_caliber}** не подходит для магазина калибра **{mag_caliber}**!",
                        ephemeral=True
                    )
                    return

                allowed = get_caliber_ammo_types(mag_caliber)
                if plain_type not in allowed:
                    await interaction.followup.send(
                        f"❌ Патрон **{plain_type}** не подходит для калибра **{mag_caliber}**!",
                        ephemeral=True
                    )
                    return

                capacity = mag_data.get("capacity", 0)
                current_ammo = sum(mag["ammo"].values())
                available = capacity - current_ammo

                if available <= 0:
                    await interaction.followup.send("✅ Магазин полный!", ephemeral=True)
                    return

                count = self.player.inventory.get(inv_key, 0)
                if count <= 0:
                    await interaction.followup.send("❌ Нет патронов!", ephemeral=True)
                    return

                to_load = min(count, available)

                success = self.player.add_magazine_ammo(self.magazine_uid, inv_key, to_load)
                if not success:
                    await interaction.followup.send("❌ Не удалось зарядить (проверка калибра не прошла).", ephemeral=True)
                    return

                self.player.inventory[inv_key] = count - to_load
                await save_player(self.player)

                ammo = get_ammo_type(plain_type)
                embed = discord.Embed(
                    title="✅ Зарядка завершена!",
                    description=f"Заряжено **{to_load}** {ammo.get('emoji', '🔘')} **{ammo.get('name', plain_type)}** "
                                f"в **{mag_data.get('name', '')}**!\n"
                                f"📊 Патронов: **{current_ammo + to_load}/{capacity}**",
                    color=discord.Color.green()
                )

                view = EquipmentLoadSelectMenu(self.player, self.magazine_uid)
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка edit (load select callback): {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в load select callback ({inv_key}): {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            view = EquipmentLoadMenu(self.player)
            embed = discord.Embed(
                title="🎯 Зарядка магазина",
                description="Выберите магазин:",
                color=discord.Color.blue()
            )
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка back (load select): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (load select): {e}")