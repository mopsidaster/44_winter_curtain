# -*- coding: utf-8 -*-
# func/views/combat_views/semi_auto_menu.py - Меню второго выстрела semi-auto (0.4.7.6.3)
#
# ИСТОРИЯ:
#   0.4.7.6.2 — новый файл
#   0.4.7.6.3 — добавлена смена цели при втором выстреле

import discord
import uuid

from ..helpers import combat_manager, handle_combat_action
from utils.discord_helpers import safe_defer
from utils.logger import get_logger

logger = get_logger()


class SemiAutoMenu(discord.ui.View):
    """
    Меню второго выстрела semi-auto.
    Можно выбрать:
      • Часть тела текущей цели
      • Другую цель (с последующим выбором части тела)
      • Отказаться
    """
    def __init__(self, user_id: int, target_idx: int = None):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.menu_id = uuid.uuid4().hex[:8]

        combat = combat_manager.get_combat(user_id)
        if combat is not None and target_idx is None:
            target_idx = combat.target_index
        self.target_idx = target_idx if target_idx is not None else 0

        self._add_buttons()

    def _add_buttons(self):
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            return

        current_enemy = None
        if 0 <= self.target_idx < len(combat.enemies):
            current_enemy = combat.enemies[self.target_idx]

        available_parts = []
        if current_enemy and current_enemy.is_alive:
            available_parts = current_enemy.get_available_parts()

        # === Ряд 0: части тела текущей цели ===
        parts = ["голова", "торс", "руки", "ноги"]
        part_emojis = {"голова": "🎯", "торс": "🫀", "руки": "💪", "ноги": "🦵"}

        for idx, part in enumerate(parts):
            is_avail = part in available_parts
            style = discord.ButtonStyle.danger if part == "голова" else discord.ButtonStyle.primary
            btn = discord.ui.Button(
                label=f"🔁 {part_emojis.get(part, '')} {part.capitalize()}",
                style=style,
                custom_id=f"semi_part_{self.menu_id}_{idx}",
                row=0,
                disabled=not is_avail,
            )
            btn.callback = self.create_shot_callback(part)
            self.add_item(btn)

        # === Ряд 1: смена цели ===
        alive_enemies = combat.get_alive_enemies()
        other_targets = [
            (idx, e) for idx, e in enumerate(combat.enemies)
            if e.is_alive and idx != self.target_idx
        ]

        for idx, (enemy_idx, enemy_obj) in enumerate(other_targets[:4]):
            label = f"🔄 {enemy_obj.emoji} {enemy_obj.display_name} #{enemy_idx + 1}"
            btn = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"semi_target_{self.menu_id}_{enemy_idx}",
                row=1,
            )
            btn.callback = self.create_change_target_callback(enemy_idx)
            self.add_item(btn)

        if not other_targets:
            # нет других целей — покажем неактивную кнопку
            dis = discord.ui.Button(
                label="🔄 Нет других целей",
                style=discord.ButtonStyle.secondary,
                custom_id=f"semi_noother_{self.menu_id}",
                row=1,
                disabled=True,
            )
            self.add_item(dis)

        # === Ряд 2: отказ ===
        skip_btn = discord.ui.Button(
            label="❌ Отказаться",
            style=discord.ButtonStyle.danger,
            custom_id=f"semi_skip_{self.menu_id}",
            row=2,
        )
        skip_btn.callback = self.skip_callback
        self.add_item(skip_btn)

    def _build_embed(self) -> discord.Embed:
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            return discord.Embed(
                title="❌ Ошибка",
                description="Бой не найден",
                color=discord.Color.red(),
            )

        embed = combat.get_status_embed()

        target_name = "?"
        if 0 <= self.target_idx < len(combat.enemies):
            target_name = combat.enemies[self.target_idx].display_name

        embed.add_field(
            name="🎯 Semi-auto — второй выстрел",
            value=(
                f"Текущая цель: **{target_name}** (#{self.target_idx + 1})\n"
                f"Точность: **−15%**\n"
                f"Выберите часть тела или смените цель"
            ),
            inline=False,
        )
        return embed

    def create_shot_callback(self, part: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return

            combat = combat_manager.get_combat(self.user_id)
            if not combat:
                await interaction.response.send_message("❌ Бой не найден!", ephemeral=True)
                return

            if not await safe_defer(interaction):
                return

            # Переключаем target_index на выбранную цель перед выстрелом
            combat.target_index = self.target_idx

            payload = f"{self.target_idx}:{part}"
            embed, view = await handle_combat_action(interaction, "shoot_second_semi", payload)
            if embed is None:
                return
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка semi-auto shot: {e}")

        return callback

    def create_change_target_callback(self, new_target_idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return

            combat = combat_manager.get_combat(self.user_id)
            if not combat:
                await interaction.response.send_message("❌ Бой не найден!", ephemeral=True)
                return

            new_view = SemiAutoMenu(self.user_id, target_idx=new_target_idx)
            embed = new_view._build_embed()

            try:
                await interaction.response.edit_message(embed=embed, view=new_view)
            except Exception as e:
                logger.error(f"Ошибка semi-auto смены цели: {e}")

        return callback

    async def skip_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return

        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            await interaction.response.send_message("❌ Бой не найден!", ephemeral=True)
            return

        if not await safe_defer(interaction):
            return

        embed, view = await handle_combat_action(interaction, "skip_second_semi")
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка semi-auto skip: {e}")