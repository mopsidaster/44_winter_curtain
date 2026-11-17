# -*- coding: utf-8 -*-
# func/views/combat_views/pvp_combat_view.py - Кнопки PvP-боя (0.4.6)
#
# ИСТОРИЯ:
#   0.4.6   — базовый PvP 1v1
#   0.4.6.1 — групповой PvP: видят все, нажимает только тот, чей ход

import discord
import uuid

from config.map_config import WEAPONS
from ...weapon_system import (
    get_current_ammo,
    is_spec_weapon,
    is_shotgun,
)
from utils.discord_helpers import safe_defer
from utils.logger import get_logger

logger = get_logger()

DISTANCE_LABELS = {
    "close": "🟢 Близко",
    "medium": "🟡 Средняя",
    "far": "🔴 Далеко",
}


class PvPCombatView(discord.ui.View):
    def __init__(self, combat_id: str):
        super().__init__(timeout=300)
        self.combat_id = combat_id
        self.menu_id = uuid.uuid4().hex[:8]
        self.action_type = None
        self._add_buttons()

    def _get_combat(self):
        from ...combat.pvp_manager import pvp_manager
        return pvp_manager.get_combat(self.combat_id)

    def _add_buttons(self):
        combat = self._get_combat()
        if not combat:
            return

        current = combat.current_combatant
        user_id = current.user_id
        weapon_id = current.player.weapon
        is_spec = is_spec_weapon(weapon_id)
        has_ammo = get_current_ammo(weapon_id, current.player) > 0
        can_melee = (combat.distance == "close")

        if is_spec:
            shoot_label = "💥 ГП-25"
        else:
            shoot_label = "🔫 Выстрел"

        shoot_btn = discord.ui.Button(
            label=shoot_label,
            style=discord.ButtonStyle.danger,
            custom_id=f"pv_shoot_{self.menu_id}",
            disabled=not has_ammo,
            row=0,
        )
        shoot_btn.callback = self.shoot_callback
        self.add_item(shoot_btn)

        melee_btn = discord.ui.Button(
            label="👊 Рукопашная",
            style=discord.ButtonStyle.success,
            custom_id=f"pv_melee_{self.menu_id}",
            disabled=not can_melee,
            row=0,
        )
        melee_btn.callback = self.melee_callback
        self.add_item(melee_btn)

        reload_btn = discord.ui.Button(
            label="🔄 Перезарядка",
            style=discord.ButtonStyle.primary,
            custom_id=f"pv_reload_{self.menu_id}",
            row=0,
        )
        reload_btn.callback = self.reload_callback
        self.add_item(reload_btn)

        medkit_btn = discord.ui.Button(
            label="💊 Аптечка",
            style=discord.ButtonStyle.success,
            custom_id=f"pv_heal_{self.menu_id}",
            row=0,
        )
        medkit_btn.callback = self.heal_callback
        self.add_item(medkit_btn)

        for dist_id in ["close", "medium", "far"]:
            is_current = combat.distance == dist_id
            label = DISTANCE_LABELS.get(dist_id, dist_id)
            if is_current:
                label = f"📍 {label}"
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.secondary,
                custom_id=f"pv_dist_{self.menu_id}_{dist_id}",
                disabled=is_current,
                row=1,
            )
            btn.callback = self.create_distance_callback(dist_id)
            self.add_item(btn)

        # Части тела
        parts = ["голова", "торс", "руки", "ноги"]
        part_emojis = {"голова": "🎯", "торс": "🫀", "руки": "💪", "ноги": "🦵"}
        available = current.get_available_parts()
        for idx, part in enumerate(parts):
            is_avail = part in available
            style = discord.ButtonStyle.danger if part == "голова" else discord.ButtonStyle.secondary
            btn = discord.ui.Button(
                label=f"{part_emojis.get(part, '')} {part.capitalize()}",
                style=style,
                custom_id=f"pv_part_{self.menu_id}_{idx}_{part}",
                disabled=not is_avail,
                row=2,
            )
            btn.callback = self.create_part_callback(part)
            self.add_item(btn)

    async def _check_turn(self, interaction: discord.Interaction) -> bool:
        combat = self._get_combat()
        if not combat or not combat.is_active:
            await interaction.response.send_message("❌ Бой завершён.", ephemeral=True)
            return False
        if interaction.user.id != combat.current_combatant.user_id:
            await interaction.response.send_message("⏳ Не ваш ход!", ephemeral=True)
            return False
        return True

    async def shoot_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self.action_type = "shoot"
        await interaction.response.send_message(
            "🎯 Выберите часть тела (кнопки в панели).", ephemeral=True
        )

    async def melee_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self.action_type = "melee"
        await interaction.response.send_message(
            "👊 Выберите часть тела (кнопки в панели).", ephemeral=True
        )

    def create_part_callback(self, part: str):
        async def callback(interaction: discord.Interaction):
            if not await self._check_turn(interaction):
                return

            action = getattr(self, 'action_type', None)
            if action not in ("shoot", "melee"):
                await interaction.response.send_message(
                    "❌ Сначала выберите действие: Выстрел или Рукопашная.",
                    ephemeral=True,
                )
                return

            await self._perform_action(interaction, action, part)
        return callback

    async def _perform_action(self, interaction: discord.Interaction,
                              action: str, target_part: str):
        from ...combat.api_pvp import handle_pvp_action

        combat = self._get_combat()
        if not combat:
            return

        if not await safe_defer(interaction):
            return

        embed, view = await handle_pvp_action(
            interaction, combat.combat_id, action, target_part
        )
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка edit PvP action: {e}")

    def create_distance_callback(self, distance: str):
        async def callback(interaction: discord.Interaction):
            if not await self._check_turn(interaction):
                return
            await self._perform_action(interaction, "change_distance", distance)
        return callback

    async def reload_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        await self._perform_action(interaction, "reload", None)

    async def heal_callback(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return

        from ...pharmacy_system import get_available_medkits
        combat = self._get_combat()
        combatant = combat.get_combatant_by_user(interaction.user.id)
        if not combatant:
            return

        medkits = get_available_medkits(combatant.player)
        if not medkits:
            await interaction.response.send_message("❌ Нет аптечек!", ephemeral=True)
            return

        from .pvp_heal_menu import PvPHealMenu
        embed = discord.Embed(
            title="💊 Выбор аптечки",
            description="Выберите, что использовать:",
            color=discord.Color.green(),
        )
        for e in medkits:
            item = e['data']
            embed.add_field(
                name=f"{item.get('emoji', '💊')} {item.get('name', e['item_id'])} (x{e['count']})",
                value=f"+{item.get('heal', 0)} HP",
                inline=False,
            )
        await interaction.response.send_message(
            embed=embed,
            view=PvPHealMenu(self.combat_id, medkits),
            ephemeral=True,
        )