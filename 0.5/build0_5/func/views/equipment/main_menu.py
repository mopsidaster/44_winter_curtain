# -*- coding: utf-8 -*-
# func/views/equipment/main_menu.py - Главное меню снаряжения (0.4.4.7.1)
#
# Рефакторинг без изменения логики.

import discord
import uuid

from ..helpers import (
    WEAPONS, save_player,
    get_magazine, get_current_ammo, get_weapon_max_ammo,
    get_available_magazines_for_weapon, get_caliber_ammo_types,
    get_ammo_type,
)
from ...melee_system import get_melee_weapon
from ...weapon_system import (
    get_module_price, uninstall_all_modules, is_spec_weapon,
    is_shotgun, is_shell_loaded_weapon, is_mg, is_heavy_mg,
    get_module_slots,
)
from config.map_config import MODULES, AMMO
from utils.logger import get_logger

from ._helpers import (
    _safe_get_module, _safe_get_slots, _safe_iter_modules,
    _build_equipment_embed,
)
from .shell_load import _ShellLoadMenu
from .weapon_change import _WeaponChangeMenu
from .modules import ModuleManagementMenu
from .magazine_insert import MagazineInsertMenu
from .load_magazine import EquipmentLoadMenu
from .melee_change import MeleeChangeMenu

logger = get_logger()


class EquipmentMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._refresh_view()

    def _refresh_view(self):
        self.clear_items()

        weapon_id = self.player.weapon
        is_shell_weapon = is_shell_loaded_weapon(weapon_id)

        # Ряд 0
        check_button = discord.ui.Button(
            label="🔍 Проверить патроны",
            style=discord.ButtonStyle.secondary,
            custom_id=f"check_ammo_{self.menu_id}",
            row=0
        )
        check_button.callback = self.check_ammo_callback
        self.add_item(check_button)

        modules_button = discord.ui.Button(
            label="🔧 Модули",
            style=discord.ButtonStyle.success,
            custom_id=f"manage_modules_{self.menu_id}",
            row=0
        )
        modules_button.callback = self.modules_callback
        self.add_item(modules_button)

        change_weapon_button = discord.ui.Button(
            label="🔫 Сменить оружие",
            style=discord.ButtonStyle.primary,
            custom_id=f"change_weapon_{self.menu_id}",
            row=0
        )
        change_weapon_button.callback = self.change_weapon_callback
        self.add_item(change_weapon_button)

        # Ряд 1
        if is_shell_weapon:
            reload_shell_button = discord.ui.Button(
                label="🔋 Зарядить ствол",
                style=discord.ButtonStyle.success,
                custom_id=f"reload_shell_{self.menu_id}",
                row=1
            )
            reload_shell_button.callback = self.reload_shell_callback
            self.add_item(reload_shell_button)

            unload_shell_button = discord.ui.Button(
                label="📤 Разрядить ствол",
                style=discord.ButtonStyle.danger,
                custom_id=f"unload_shell_{self.menu_id}",
                row=1
            )
            unload_shell_button.callback = self.unload_shell_callback
            self.add_item(unload_shell_button)
        else:
            insert_button = discord.ui.Button(
                label="📀 Вставить магазин",
                style=discord.ButtonStyle.success,
                custom_id=f"insert_magazine_{self.menu_id}",
                row=1
            )
            insert_button.callback = self.insert_magazine_callback
            self.add_item(insert_button)

            eject_button = discord.ui.Button(
                label="📀 Вытащить магазин",
                style=discord.ButtonStyle.danger,
                custom_id=f"eject_magazine_{self.menu_id}",
                row=1
            )
            eject_button.callback = self.eject_magazine_callback
            self.add_item(eject_button)

        # Ряд 2
        if not is_shell_weapon:
            load_button = discord.ui.Button(
                label="🎯 Зарядить магазин",
                style=discord.ButtonStyle.primary,
                custom_id=f"load_magazine_{self.menu_id}",
                row=2
            )
            load_button.callback = self.load_magazine_callback
            self.add_item(load_button)

            unload_button = discord.ui.Button(
                label="📤 Разрядить магазин",
                style=discord.ButtonStyle.danger,
                custom_id=f"unload_magazine_{self.menu_id}",
                row=2
            )
            unload_button.callback = self.unload_magazine_callback
            self.add_item(unload_button)

        # Ряд 3
        melee_button = discord.ui.Button(
            label="🗡️ Сменить ближний бой",
            style=discord.ButtonStyle.primary,
            custom_id=f"change_melee_{self.menu_id}",
            row=3
        )
        melee_button.callback = self.change_melee_callback
        self.add_item(melee_button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"back_to_action_{self.menu_id}",
            row=3
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    # ==================== CALLBACKS ====================

    async def change_weapon_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            inv = _safe_iter_modules(self.player.weapons_inventory) if False else [
                wid for wid in self.player.weapons_inventory if isinstance(wid, str)
            ]
            if not inv:
                await interaction.followup.send(
                    "❌ У вас нет запасного оружия в инвентаре!",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🔫 Смена оружия",
                description=f"Текущее: **{WEAPONS.get(self.player.weapon, {}).get('name', '—')}**\n\n"
                            f"Выберите оружие из инвентаря:",
                color=discord.Color.blue()
            )

            for weapon_id in inv[:8]:
                wdata = WEAPONS.get(weapon_id, {})
                if not isinstance(wdata, dict):
                    continue
                embed.add_field(
                    name=f"{wdata.get('emoji', '🔫')} {wdata.get('name', weapon_id)}",
                    value=f"📊 Урон: {wdata.get('damage', 0)} | Точность: {wdata.get('accuracy', 0) * 100:.0f}%\n"
                          f"📦 Калибр: {wdata.get('caliber', '?')}",
                    inline=False
                )

            embed.set_footer(text="⚠️ Все модули с текущего оружия будут сняты")

            view = _WeaponChangeMenu(self.player, inv)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка edit (change weapon): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в change_weapon_callback: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def reload_shell_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            weapon_id = self.player.weapon
            weapon_data = WEAPONS.get(weapon_id, {})
            if not weapon_data.get('shell_loading'):
                await interaction.followup.send("❌ Это оружие не заряжается в ствол!", ephemeral=True)
                return

            caliber = weapon_data.get('caliber')
            ammo_types = get_caliber_ammo_types(caliber)

            available = []
            for atype in ammo_types:
                count = self.player.inventory.get(atype, 0)
                if count > 0:
                    available.append((atype, count))

            if not available:
                await interaction.followup.send(
                    "❌ Нет патронов в инвентаре! Купите в оружейном магазине (раздел «Патроны»).",
                    ephemeral=True
                )
                return

            capacity = weapon_data.get('shell_capacity', 0)
            current = self.player.get_shell_ammo_count()
            free = capacity - current

            embed = discord.Embed(
                title="🔋 Зарядка ствола",
                description=(
                    f"Оружие: **{weapon_data.get('name', '—')}**\n"
                    f"Калибр: **{weapon_data.get('caliber', '?')}**\n"
                    f"В стволе: **{current}/{capacity}**\n"
                    f"Свободно: **{free}**\n\n"
                    f"Выберите тип патрона:"
                ),
                color=discord.Color.blue()
            )

            for atype, count in available:
                ammo_data = get_ammo_type(atype)
                emoji = ammo_data.get('emoji', '🔘') if ammo_data else '🔘'
                name = ammo_data.get('name', atype) if ammo_data else atype
                embed.add_field(
                    name=f"{emoji} {name}",
                    value=f"В инвентаре: **{count}** шт.",
                    inline=True
                )

            view = _ShellLoadMenu(self.player, available)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка edit (reload shell): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в reload_shell_callback: {e}")

    async def unload_shell_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            weapon_id = self.player.weapon
            weapon_data = WEAPONS.get(weapon_id, {})
            if not weapon_data.get('shell_loading'):
                await interaction.followup.send("❌ Это оружие не разряжается через ствол!", ephemeral=True)
                return

            shell = self.player.get_shell_ammo(weapon_id)
            if not shell:
                await interaction.followup.send("✅ Ствол уже пуст!", ephemeral=True)
                return

            unloaded = []
            for atype, count in list(shell.items()):
                self.player.inventory[atype] = self.player.inventory.get(atype, 0) + count
                unloaded.append(f"{atype} ×{count}")

            self.player.shell_ammo[weapon_id] = {}
            await save_player(self.player)

            await interaction.followup.send(
                f"📤 **Ствол разряжен:**\n" + "\n".join(unloaded) + "\n\n"
                                                                   f"Патроны вернулись в инвентарь.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в unload_shell_callback: {e}")

    async def check_ammo_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            weapon_id = self.player.weapon
            weapon_data = WEAPONS.get(weapon_id, {})

            if is_shell_loaded_weapon(weapon_id):
                shell = self.player.get_shell_ammo(weapon_id)
                capacity = weapon_data.get('shell_capacity', 0)
                total = sum(shell.values())

                embed = discord.Embed(
                    title="🔍 Ствол",
                    description=f"**{weapon_data.get('name', '—')}**\n"
                                f"Калибр: **{weapon_data.get('caliber', '?')}**\n"
                                f"Заряжено: **{total}/{capacity}**",
                    color=discord.Color.blue()
                )

                if shell:
                    ammo_text = ""
                    for atype, cnt in shell.items():
                        ammo_data = get_ammo_type(atype)
                        emoji = ammo_data.get('emoji', '🔘') if ammo_data else '🔘'
                        name = ammo_data.get('name', atype) if ammo_data else atype
                        ammo_text += f"{emoji} **{name}**: {cnt} шт.\n"
                    embed.add_field(name="📦 Содержимое", value=ammo_text, inline=False)
                else:
                    embed.add_field(name="📦 Содержимое", value="Ствол пуст", inline=False)

                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            equipped = self.player.get_equipped_magazine_obj()
            if not equipped:
                await interaction.followup.send("❌ В оружии нет магазина!", ephemeral=True)
                return

            mag_data = get_magazine(equipped["type_id"])
            if not mag_data:
                await interaction.followup.send("❌ Магазин не найден!", ephemeral=True)
                return

            current_ammo = sum(equipped["ammo"].values())
            max_ammo = mag_data.get("capacity", 0)

            embed = discord.Embed(
                title="🔍 Патроны в магазине",
                description=f"**{mag_data.get('name', '?')}** (ID: `{equipped['uid']}`)\n"
                            f"Калибр: **{mag_data.get('caliber', '?')}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="📊 Общее", value=f"{current_ammo}/{max_ammo}", inline=True)

            if equipped["ammo"]:
                ammo_text = ""
                for ammo_type, count in equipped["ammo"].items():
                    ammo = get_ammo_type(ammo_type)
                    if ammo:
                        ammo_text += f"{ammo.get('emoji', '🔘')} **{ammo.get('name', ammo_type)}**: {count} шт.\n"
                embed.add_field(name="📦 По типам", value=ammo_text, inline=False)
            else:
                embed.add_field(name="📦 По типам", value="Магазин пуст", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ Ошибка в check_ammo_callback: {e}")
            try:
                await interaction.followup.send(f"❌ Ошибка: {str(e)}", ephemeral=True)
            except:
                pass

    async def modules_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            is_spec = is_spec_weapon(self.player.weapon)

            embed = discord.Embed(
                title="🔧 Управление модулями",
                description=f"Оружие: **{WEAPONS.get(self.player.weapon, {}).get('name', 'Нет')}**",
                color=discord.Color.green()
            )

            if is_spec:
                embed.add_field(
                    name="⚠️ Специальное оружие",
                    value="На это оружие модули не устанавливаются.",
                    inline=False
                )
                await interaction.edit_original_response(embed=embed)
                return

            slots = MODULES.get('slots', {})
            equipped = self.player.equipped_modules or {}

            equipped_text = ""
            shown_modules = set()
            for slot_id, slot_data in slots.items():
                module_id = equipped.get(slot_id)
                if module_id and module_id not in shown_modules:
                    module_data = _safe_get_module(module_id)
                    if not module_data:
                        # в слоте мусор — пропускаем
                        shown_modules.add(module_id)
                        continue
                    slots_of = _safe_get_slots(module_id)
                    slot_names = ", ".join(
                        MODULES['slots'].get(s, {}).get('name', s) for s in slots_of
                    ) if slots_of else slot_data.get('name', slot_id)
                    equipped_text += (f"{slot_data.get('emoji', '🔧')} "
                                      f"**{slot_names}**: "
                                      f"{module_data.get('emoji', '')} "
                                      f"{module_data.get('name', module_id)}\n")
                    shown_modules.add(module_id)
                elif not module_id:
                    equipped_text += f"{slot_data.get('emoji', '🔧')} **{slot_data.get('name', slot_id)}**: ❌ пусто\n"

            if not equipped_text:
                equipped_text = "_Пусто_"

            embed.add_field(name="📦 Установлено", value=equipped_text, inline=False)

            # Безопасный обход инвентаря
            inv_modules = _safe_iter_modules(self.player.modules_inventory)
            if inv_modules:
                inv_text = ""
                for module_id in inv_modules:
                    module_data = _safe_get_module(module_id)
                    if not module_data:
                        continue
                    inv_text += f"• {module_data.get('emoji', '🔧')} {module_data.get('name', module_id)}\n"
                if inv_text:
                    embed.add_field(
                        name=f"🎒 В инвентаре ({len(inv_modules)})",
                        value=inv_text[:1000],
                        inline=False
                    )
                else:
                    embed.add_field(name="🎒 В инвентаре", value="Нет модулей", inline=False)
            else:
                embed.add_field(name="🎒 В инвентаре", value="Нет модулей", inline=False)

            view = ModuleManagementMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка edit (modules): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в modules_callback: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def unload_magazine_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            equipped = self.player.get_equipped_magazine_obj()
            if not equipped:
                await interaction.followup.send("❌ В оружии нет магазина!", ephemeral=True)
                return

            if not equipped["ammo"]:
                await interaction.followup.send("❌ Магазин уже пуст!", ephemeral=True)
                return

            unloaded = []
            for ammo_type, count in list(equipped["ammo"].items()):
                ammo = get_ammo_type(ammo_type)
                self.player.inventory[ammo_type] = self.player.inventory.get(ammo_type, 0) + count
                unloaded.append(f"{ammo.get('name', ammo_type) if ammo else ammo_type} x{count}")

            equipped["ammo"] = {}
            await save_player(self.player)

            await interaction.followup.send(
                f"📤 Магазин разряжен:\n" + "\n".join(unloaded),
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в unload_magazine_callback: {e}")

    async def eject_magazine_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            equipped = self.player.get_equipped_magazine_obj()
            if not equipped:
                await interaction.followup.send("❌ В оружии нет магазина!", ephemeral=True)
                return

            mag_data = get_magazine(equipped["type_id"])
            uid = self.player.uninstall_magazine()
            await save_player(self.player)

            await interaction.followup.send(
                f"✅ Магазин **{mag_data.get('name', '')}** вытащен!\n📀 UID: `{uid}`",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в eject_magazine_callback: {e}")

    async def insert_magazine_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            if self.player.equipped_magazine:
                await interaction.followup.send("❌ Сначала вытащите текущий магазин!", ephemeral=True)
                return

            weapon = WEAPONS.get(self.player.weapon)
            if not weapon:
                await interaction.followup.send("❌ Нет оружия!", ephemeral=True)
                return

            weapon_mags = weapon.get('magazines', [])
            available = []
            for mag in self.player.get_uninstalled_magazines():
                if mag["type_id"] in weapon_mags:
                    available.append(mag)

            if not available:
                await interaction.followup.send("❌ Нет доступных магазинов для этого оружия!", ephemeral=True)
                return

            embed = discord.Embed(
                title="📀 Вставка магазина",
                description="Выберите магазин:",
                color=discord.Color.blue()
            )

            for mag in available[:5]:
                mag_data = get_magazine(mag["type_id"])
                if mag_data:
                    ammo_count = sum(mag["ammo"].values())
                    capacity = mag_data.get("capacity", 0)
                    embed.add_field(
                        name=f"{mag_data.get('emoji', '📀')} {mag_data.get('name', mag['type_id'])}",
                        value=f"UID: `{mag['uid']}`\n"
                              f"Калибр: {mag_data.get('caliber', '?')}\n"
                              f"Патронов: {ammo_count}/{capacity}",
                        inline=False
                    )

            view = MagazineInsertMenu(self.player, available)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка edit (insert mag): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в insert_magazine_callback: {e}")

    async def load_magazine_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            uninstalled = self.player.get_uninstalled_magazines()
            if not uninstalled:
                await interaction.followup.send(
                    "❌ Нет вытащенных магазинов для зарядки!\n💡 Сначала вытащите магазин из оружия.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🎯 Зарядка магазина",
                description="Выберите магазин:",
                color=discord.Color.blue()
            )

            for mag in uninstalled[:5]:
                mag_data = get_magazine(mag["type_id"])
                if mag_data:
                    current_ammo = sum(mag["ammo"].values())
                    capacity = mag_data.get("capacity", 0)
                    embed.add_field(
                        name=f"{mag_data.get('emoji', '📀')} {mag_data.get('name', mag['type_id'])}",
                        value=f"UID: `{mag['uid']}`\n"
                              f"Калибр: {mag_data.get('caliber', '?')}\n"
                              f"Патронов: {current_ammo}/{capacity}",
                        inline=False
                    )

            view = EquipmentLoadMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка edit (load mag): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в load_magazine_callback: {e}")

    async def change_melee_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            embed = discord.Embed(
                title="🗡️ Смена оружия ближнего боя",
                description="Для смены купите новое оружие в оружейном магазине (раздел «Ближний бой»).",
                color=discord.Color.blue()
            )

            current = self.player.melee_weapon
            melee_data = get_melee_weapon(current) or {}

            embed.add_field(
                name="📊 Текущее",
                value=f"{melee_data.get('emoji', '👊')} **{melee_data.get('name', 'Кулаки')}**\n"
                      f"Прочность: {self.player.get_melee_weapon_durability_percent()}%",
                inline=False
            )

            view = MeleeChangeMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка edit (melee change): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в change_melee_callback: {e}")

    async def back_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            from ..action_menu import ActionMenu
            embed = discord.Embed(title="🎯 Действия", description="Выберите действие:", color=discord.Color.blue())
            view = ActionMenu()
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка возврата в ActionMenu: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (equipment): {e}")