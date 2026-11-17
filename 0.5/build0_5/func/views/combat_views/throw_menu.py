# -*- coding: utf-8 -*-
# func/views/combat_views/throw_menu.py - Меню метания (0.4.4.8)
#
# ИСТОРИЯ:
#   0.4.4.7 — вынесено из views/combat.py
#   0.4.4.8 — safe_defer вынесен в utils/discord_helpers

import discord
import uuid

from ..helpers import combat_manager, handle_combat_action
from config.map_config import WEAPONS
from utils.discord_helpers import safe_defer
from utils.logger import get_logger

logger = get_logger()


class _ThrowSelectMenu(discord.ui.View):
    """Выбор, что метнуть: гранаты или ножи."""

    def __init__(self, user_id: int, menu_id: str, grenades: dict, knives: dict):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.menu_id = uuid.uuid4().hex[:8]

        for gid, count in grenades.items():
            g = WEAPONS.get(gid, {})
            label = f"💣 {g.get('name', gid)} ({count})"[:80]
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.danger,
                custom_id=f"throw_gr_{self.menu_id}_{gid}"[:100],
                row=0
            )
            btn.callback = self.create_grenade_callback(gid)
            self.add_item(btn)

        for kid, count in knives.items():
            k = WEAPONS.get(kid, {})
            label = f"🔪 {k.get('name', kid)} ({count})"[:80]
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary,
                custom_id=f"throw_kn_{self.menu_id}_{kid}"[:100],
                row=1
            )
            btn.callback = self.create_knife_callback(kid)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"throw_back_{self.menu_id}",
            row=2
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_grenade_callback(self, grenade_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return
            combat = combat_manager.get_combat(self.user_id)
            if not combat or not combat.can_act():
                await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
                return

            if not await safe_defer(interaction):
                return

            embed, view = await handle_combat_action(interaction, "throw_grenade", grenade_id)
            if embed is None:
                return
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка throw_grenade: {e}")

        return callback

    def create_knife_callback(self, knife_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return
            combat = combat_manager.get_combat(self.user_id)
            if not combat or not combat.can_act():
                await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
                return

            k = WEAPONS.get(knife_id, {})
            embed = discord.Embed(
                title=f"🔪 {k.get('name', knife_id)}",
                description=f"Выберите часть тела для метания:\n"
                            f"Урон: {k.get('damage', '?')} | Точность: {int(k.get('accuracy', 0) * 100)}%",
                color=discord.Color.orange()
            )
            view = _KnifeTargetMenu(self.user_id, self.menu_id, knife_id)
            await interaction.response.edit_message(embed=embed, view=view)

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
        embed.add_field(name="⚙️ Действие", value="Выберите вспомогательное действие:", inline=False)
        view = _ActionSubmenu(self.user_id)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            pass


class _KnifeTargetMenu(discord.ui.View):
    def __init__(self, user_id: int, menu_id: str, knife_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.knife_id = knife_id
        self.menu_id = uuid.uuid4().hex[:8]

        combat = combat_manager.get_combat(user_id)
        if not combat:
            return

        part_emojis = {"голова": "🎯", "торс": "🫀", "руки": "💪", "ноги": "🦵"}
        available = combat.get_target_parts()

        for idx, part in enumerate(["голова", "торс", "руки", "ноги"]):
            if part not in available:
                continue
            btn = discord.ui.Button(
                label=f"{part_emojis.get(part, '')} {part.capitalize()}",
                style=discord.ButtonStyle.danger if part == "голова" else discord.ButtonStyle.primary,
                custom_id=f"kn_tg_{self.menu_id}_{idx}"[:100],
                row=0
            )
            btn.callback = self.create_part_callback(part)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"kn_tg_back_{self.menu_id}",
            row=1
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_part_callback(self, part: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return
            combat = combat_manager.get_combat(self.user_id)
            if not combat or not combat.can_act():
                await interaction.response.send_message("⏳ Дождитесь хода врага!", ephemeral=True)
                return

            if not await safe_defer(interaction):
                return

            target_part = f"{self.knife_id}:{part}"
            embed, view = await handle_combat_action(interaction, "throw_knife", target_part)
            if embed is None:
                return
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка throw_knife: {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            return

        grenades = combat.player.get_all_grenades()
        knives = combat.player.get_all_knives()

        lines = []
        for gid, count in grenades.items():
            g = WEAPONS.get(gid, {})
            lines.append(f"💣 **{g.get('name', gid)}** ×{count}")
        for kid, count in knives.items():
            k = WEAPONS.get(kid, {})
            lines.append(f"🔪 **{k.get('name', kid)}** ×{count}")

        embed = discord.Embed(
            title="🎯 Что метнуть?",
            description="\n".join(lines) + "\n\n⚠️ Метание = полноценный ход.",
            color=discord.Color.orange()
        )
        view = _ThrowSelectMenu(self.user_id, self.menu_id, grenades, knives)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            pass