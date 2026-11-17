# -*- coding: utf-8 -*-
# func/views/equipment/modules.py - Меню модулей (0.4.4.7.1)
#
# Рефакторинг без изменения логики.

import discord
import uuid

from ..helpers import save_player
from config.map_config import MODULES
from utils.logger import get_logger

from ._helpers import _safe_get_module, _safe_get_slots

logger = get_logger()


class ModuleManagementMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        slots = MODULES.get('slots', {})

        for slot_id, slot_data in slots.items():
            button = discord.ui.Button(
                label=f"⬆️ Установить в {slot_data.get('name', slot_id)}",
                style=discord.ButtonStyle.success,
                custom_id=f"install_module_{slot_id}_{self.menu_id}"
            )
            button.callback = self.create_install_callback(slot_id)
            self.add_item(button)

        equipped = self.player.equipped_modules or {}
        shown = set()
        for slot_id, slot_data in slots.items():
            equipped_id = equipped.get(slot_id)
            if equipped_id and equipped_id not in shown:
                button = discord.ui.Button(
                    label=f"⬇️ Снять {slot_data.get('name', slot_id)}",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"remove_module_{slot_id}_{self.menu_id}"
                )
                button.callback = self.create_remove_callback(slot_id)
                self.add_item(button)
                shown.add(equipped_id)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"modules_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_install_callback(self, slot_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                await interaction.response.defer()

                available = []
                for module_id in self.player.modules_inventory:
                    if not isinstance(module_id, str):
                        continue
                    module_data = _safe_get_module(module_id)
                    if not module_data:
                        continue
                    slots_of = _safe_get_slots(module_id)
                    if slot_id in slots_of:
                        from ...weapon_system import can_install_module
                        try:
                            can_install, _ = can_install_module(self.player.weapon, module_id)
                        except Exception as e:
                            logger.error(f"can_install_module({self.player.weapon}, {module_id}): {e}")
                            continue
                        if can_install:
                            available.append(module_id)

                if not available:
                    await interaction.followup.send(
                        f"❌ Нет подходящих модулей для слота «{MODULES['slots'][slot_id].get('name', slot_id)}»!",
                        ephemeral=True
                    )
                    return

                embed = discord.Embed(
                    title=f"🔧 Установка в слот «{MODULES['slots'][slot_id].get('name', slot_id)}»",
                    description="Выберите модуль:",
                    color=discord.Color.green()
                )

                for module_id in available:
                    module_data = _safe_get_module(module_id)
                    if not module_data:
                        continue
                    acc = module_data.get('accuracy', {}) or {}
                    embed.add_field(
                        name=f"{module_data.get('emoji', '🔧')} {module_data.get('name', module_id)}",
                        value=f"🎯 Точность Б: +{acc.get('close', 0) * 100:.0f}% | "
                              f"С: +{acc.get('medium', 0) * 100:.0f}% | "
                              f"Д: +{acc.get('far', 0) * 100:.0f}%",
                        inline=False
                    )

                view = ModuleInstallSelect(self.player, slot_id, available)
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка edit (install module): {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в install callback ({slot_id}): {e}")
                import traceback
                logger.error(traceback.format_exc())

        return callback

    def create_remove_callback(self, slot_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                await interaction.response.defer()

                success, msg = self.player.remove_module(slot_id)
                await save_player(self.player)

                if success:
                    embed = discord.Embed(title="🔧 Управление модулями", color=discord.Color.green())
                    embed.add_field(name="✅ Успех", value=msg, inline=False)
                    new_view = ModuleManagementMenu(self.player)
                    try:
                        await interaction.edit_original_response(embed=embed, view=new_view)
                    except Exception as e:
                        logger.error(f"Ошибка edit (remove module): {e}")
                else:
                    await interaction.followup.send(msg, ephemeral=True)

            except Exception as e:
                logger.error(f"❌ Ошибка в remove callback ({slot_id}): {e}")

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
                logger.error(f"Ошибка back (module management): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (module management): {e}")


class ModuleInstallSelect(discord.ui.View):
    def __init__(self, player, slot_id: str, available: list):
        super().__init__(timeout=120)
        self.player = player
        self.slot_id = slot_id
        self.menu_id = uuid.uuid4().hex[:8]

        for idx, module_id in enumerate(available):
            module_data = _safe_get_module(module_id)
            if not module_data:
                continue
            button = discord.ui.Button(
                label=f"{module_data.get('emoji', '🔧')} {module_data.get('name', module_id)}"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"select_module_{self.menu_id}_{idx}"
            )
            button.callback = self.create_callback(module_id)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"install_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, module_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                await interaction.response.defer()

                success, msg = self.player.install_module(module_id)
                await save_player(self.player)

                if success:
                    embed = discord.Embed(title="🔧 Управление модулями", color=discord.Color.green())
                    embed.add_field(name="✅ Успех", value=msg, inline=False)
                    new_view = ModuleManagementMenu(self.player)
                    try:
                        await interaction.edit_original_response(embed=embed, view=new_view)
                    except Exception as e:
                        logger.error(f"Ошибка edit (install select): {e}")
                else:
                    await interaction.followup.send(msg, ephemeral=True)

            except Exception as e:
                logger.error(f"❌ Ошибка в select callback ({module_id}): {e}")
                import traceback
                logger.error(traceback.format_exc())

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            embed = discord.Embed(title="🔧 Управление модулями", color=discord.Color.green())
            view = ModuleManagementMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка back (install select): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (install select): {e}")