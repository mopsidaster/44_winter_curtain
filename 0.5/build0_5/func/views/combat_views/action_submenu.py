# -*- coding: utf-8 -*-
# func/views/combat_views/action_submenu.py - Подменю «Действие» (0.4.5.1)
#
# ИСТОРИЯ:
#   0.4.4.7   — вынесено из views/combat.py
#   0.4.4.8   — safe_defer вынесен в utils/discord_helpers
#   0.4.5     — defer первой строкой + edit_original_response
#   0.4.5.1   — логирование в callback-ах

import discord
import uuid

from ..helpers import combat_manager, handle_combat_action
from ...weapon_system import (
    is_shell_loaded_weapon,
    is_heavy_mg,
    get_caliber_ammo_types,
)
from config.map_config import WEAPONS
from utils.discord_helpers import safe_defer
from utils.logger import get_logger

from .shell_reload import _ShellReloadMenu
from .throw_menu import _ThrowSelectMenu
from .heal_menu import _CombatHealMenu

logger = get_logger()


class _ActionSubmenu(discord.ui.View):
    """
    Перезарядка, Метнуть, Аптечка, Отступить, Назад.
    Ряд 0: Перезарядка | Метнуть | Аптечка
    Ряд 1: Отступить | Назад
    """
    def __init__(self, user_id: int):
        super().__init__(timeout=90)
        self.user_id = user_id
        self.menu_id = uuid.uuid4().hex[:8]
        try:
            self._add_buttons()
            logger.info(f"⚙️ _ActionSubmenu: создан, кнопок={len(self.children)}")
        except Exception as e:
            logger.error(f"⚙️ _ActionSubmenu: ОШИБКА в _add_buttons: {e}", exc_info=True)
            raise

    def _add_buttons(self):
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            logger.warning(f"⚙️ _ActionSubmenu: combat не найден")
            return

        # --- Перезарядка ---
        is_shell = is_shell_loaded_weapon(combat.player.weapon)
        heavy_mg = is_heavy_mg(combat.player.weapon)

        if is_shell:
            reload_label = "🔄 Зарядить ствол"
            reload_disabled = False
        elif heavy_mg:
            progress = combat.player.mg_reload_progress
            if progress == 0:
                reload_label = "🔄 Перезарядка (2 хода)"
                reload_disabled = False
            elif progress == 1:
                reload_label = "🔧 Перезарядка (1/2)"
                reload_disabled = True
            else:
                reload_label = "🔧 Перезарядка (2/2)"
                reload_disabled = True
        else:
            weapon_mags = WEAPONS.get(combat.player.weapon, {}).get('magazines', [])
            has_spare = False
            for mag in combat.player.get_uninstalled_magazines():
                if mag["type_id"] in weapon_mags and sum(mag.get("ammo", {}).values()) > 0:
                    has_spare = True
                    break
            reload_label = "🔄 Сменить магазин"
            if not has_spare:
                reload_label += " (нет)"
            reload_disabled = not has_spare

        reload_btn = discord.ui.Button(
            label=reload_label,
            style=discord.ButtonStyle.primary,
            custom_id=f"act_reload_{self.menu_id}",
            row=0,
            disabled=reload_disabled
        )
        reload_btn.callback = self.reload_callback
        self.add_item(reload_btn)

        # --- Метнуть ---
        has_throwables = (
                combat.player.get_grenades_total() > 0
                or combat.player.get_knives_total() > 0
        )
        throw_btn = discord.ui.Button(
            label="🎯 Метнуть",
            style=discord.ButtonStyle.primary,
            custom_id=f"act_throw_{self.menu_id}",
            row=0,
            disabled=not has_throwables
        )
        throw_btn.callback = self.throw_callback
        self.add_item(throw_btn)

        # --- Аптечка ---
        try:
            from ...pharmacy_system import get_available_medkits
            medkits = get_available_medkits(combat.player)
        except Exception as e:
            logger.error(f"⚙️ _ActionSubmenu: ошибка get_available_medkits: {e}")
            medkits = []

        medkit_btn = discord.ui.Button(
            label="💊 Аптечка",
            style=discord.ButtonStyle.success,
            custom_id=f"act_heal_{self.menu_id}",
            row=0,
            disabled=(len(medkits) == 0)
        )
        medkit_btn.callback = self.heal_callback
        self.add_item(medkit_btn)

        # --- Отступить ---
        legs_alive = not combat.player.is_body_part_destroyed("ноги")
        retreat_btn = discord.ui.Button(
            label="🏃 Отступить",
            style=discord.ButtonStyle.danger,
            custom_id=f"act_retreat_{self.menu_id}",
            row=1,
            disabled=not legs_alive
        )
        retreat_btn.callback = self.retreat_callback
        self.add_item(retreat_btn)

        # --- Назад ---
        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"act_back_{self.menu_id}",
            row=1
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    # ==================== CALLBACKS ====================

    async def reload_callback(self, interaction: discord.Interaction):
        logger.info(f"⚙️ reload_callback: user={interaction.user.id}")

        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat or not combat.can_act():
            await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
            return

        # Shell-оружие — открываем подменю выбора патрона
        if is_shell_loaded_weapon(combat.player.weapon):
            weapon_data = WEAPONS.get(combat.player.weapon, {})
            caliber = weapon_data.get('caliber')
            ammo_types = get_caliber_ammo_types(caliber)

            available = []
            for atype in ammo_types:
                count = combat.player.inventory.get(atype, 0)
                if count > 0:
                    available.append((atype, count))

            if not available:
                await interaction.response.send_message("❌ Нет патронов в инвентаре!", ephemeral=True)
                return

            if not await safe_defer(interaction):
                return

            embed = discord.Embed(
                title="🔄 Зарядка ствола",
                description=(
                    f"Оружие: **{weapon_data.get('name', '—')}**\n"
                    f"В стволе: **{combat.player.get_shell_ammo_count()}/{weapon_data.get('shell_capacity', 0)}**\n\n"
                    f"Выберите тип патронов:"
                ),
                color=discord.Color.blue()
            )
            view = _ShellReloadMenu(self.user_id, self.menu_id, available)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка edit (reload shell submenu): {e}")
            return

        if not await safe_defer(interaction):
            return
        embed, view = await handle_combat_action(interaction, "reload")
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка reload: {e}")

    async def throw_callback(self, interaction: discord.Interaction):
        logger.info(f"⚙️ throw_callback: user={interaction.user.id}")

        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat or not combat.can_act():
            await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
            return

        if not await safe_defer(interaction):
            return

        grenades = combat.player.get_all_grenades()
        knives = combat.player.get_all_knives()

        if not grenades and not knives:
            await interaction.followup.send("❌ У вас нет ни гранат, ни метательных ножей!", ephemeral=True)
            return

        lines = []
        for gid, count in grenades.items():
            g = WEAPONS.get(gid, {})
            lines.append(f"💣 **{g.get('name', gid)}** ×{count} — урон {g.get('damage', '?')}")
        for kid, count in knives.items():
            k = WEAPONS.get(kid, {})
            lines.append(
                f"🔪 **{k.get('name', kid)}** ×{count} — урон {k.get('damage', '?')}, "
                f"точность {int(k.get('accuracy', 0) * 100)}%"
            )

        embed = discord.Embed(
            title="🎯 Что метнуть?",
            description="\n".join(lines) + "\n\n⚠️ Метание = полноценный ход.",
            color=discord.Color.orange()
        )

        view = _ThrowSelectMenu(self.user_id, self.menu_id, grenades, knives)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка throw submenu: {e}")

    async def heal_callback(self, interaction: discord.Interaction):
        logger.info(f"⚙️ heal_callback: user={interaction.user.id}")

        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat or not combat.can_act():
            await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
            return

        if not await safe_defer(interaction):
            return

        try:
            from ...pharmacy_system import get_available_medkits
            medkits = get_available_medkits(combat.player)
        except Exception:
            medkits = []

        if not medkits:
            await interaction.followup.send("❌ Нет аптечек!", ephemeral=True)
            return

        embed = discord.Embed(
            title="💊 Использовать аптечку",
            description="⚠️ Использование аптечки — **полноценный ход**.",
            color=discord.Color.green()
        )
        for entry in medkits:
            item = entry['data']
            count = entry['count']
            heal = item.get('heal', 0)
            rad_red = item.get('radiation_reduction', 0)
            desc = f"+{heal:.1f} HP"
            if rad_red > 0:
                desc += f" | -{rad_red}☢️"
            embed.add_field(
                name=f"{item.get('emoji', '💊')} {item.get('name', entry['item_id'])} (x{count})",
                value=desc,
                inline=False
            )

        view = _CombatHealMenu(self.user_id, medkits)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка heal submenu: {e}")

    async def retreat_callback(self, interaction: discord.Interaction):
        logger.info(f"⚙️ retreat_callback: user={interaction.user.id}")

        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat or not combat.can_act():
            await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
            return
        if combat.player.is_body_part_destroyed("ноги"):
            await interaction.response.send_message("❌ Ноги уничтожены!", ephemeral=True)
            return
        if not await safe_defer(interaction):
            return
        embed, view = await handle_combat_action(interaction, "retreat")
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка retreat: {e}")

    async def back_callback(self, interaction: discord.Interaction):
        logger.info(f"⚙️ back_callback: user={interaction.user.id}")

        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            return

        if not await safe_defer(interaction):
            return

        from .main_view import CombatView

        embed = combat.get_status_embed()
        view = CombatView(self.user_id)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка back (action_submenu): {e}")