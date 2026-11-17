# -*- coding: utf-8 -*-
# func/views/combat_views/multishot.py - Распределение очереди (0.4.4.8)
#
# ИСТОРИЯ:
#   0.4.4.7.4 — confirmed через __init__
#   0.4.4.7.5 — ИСПРАВЛЕНИЕ: защита от повторного нажатия после
#               финализации (флаг _finalized + disable_all).
#               Убрано двойное обновление сообщения.
#   0.4.4.8   — safe_defer вынесен в utils/discord_helpers

import discord
import uuid

from ..helpers import combat_manager, handle_combat_action
from utils.discord_helpers import safe_defer
from utils.logger import get_logger

logger = get_logger()


class _MultiShotMenu(discord.ui.View):
    """Меню распределения очереди (assault=2, smg=4, mg=3)."""

    def __init__(self, user_id: int, menu_id: str, combat,
                 shots_count: int, plan: list, confirmed: int = 1):
        super().__init__(timeout=90)
        self.user_id = user_id
        self.menu_id = uuid.uuid4().hex[:8]
        self.shots_count = shots_count
        self.plan = list(plan)
        self.confirmed = max(1, min(confirmed, shots_count))
        self._finalized = False
        self._add_buttons(combat)

    def _add_buttons(self, combat):
        same_btn = discord.ui.Button(
            label=f"🎯 В ту же цель (враг #{combat.target_index + 1}, {self.plan[0][1]})",
            style=discord.ButtonStyle.secondary,
            custom_id=f"ms_same_{self.menu_id}",
            row=0
        )
        same_btn.callback = self.same_callback
        self.add_item(same_btn)

        alive_indices = [i for i, e in enumerate(combat.enemies) if e.is_alive]
        other_indices = [i for i in alive_indices if i != combat.target_index]

        for idx in other_indices[:4]:
            enemy_obj = combat.enemies[idx]
            btn = discord.ui.Button(
                label=f"🔄 В врага #{idx + 1} ({enemy_obj.display_name})",
                style=discord.ButtonStyle.primary,
                custom_id=f"ms_other_{self.menu_id}_{idx}",
                row=1
            )
            btn.callback = self.create_other_target_callback(idx)
            self.add_item(btn)

        cancel_btn = discord.ui.Button(
            label="🔙 Отмена",
            style=discord.ButtonStyle.danger,
            custom_id=f"ms_cancel_{self.menu_id}",
            row=3
        )
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    def _disable_all(self):
        for child in self.children:
            child.disabled = True

    def _build_embed(self, combat) -> discord.Embed:
        embed = combat.get_status_embed()
        next_shot = min(self.confirmed + 1, self.shots_count)
        embed.add_field(
            name=f"🎯 Выстрел {next_shot}/{self.shots_count}",
            value="Куда направить **следующий** выстрел?",
            inline=False
        )
        return embed

    async def same_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        if self._finalized:
            await interaction.response.send_message("⏳ Уже обрабатывается...", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            return

        if self.confirmed >= self.shots_count:
            await self._finalize(interaction, combat)
            return

        self.plan[self.confirmed] = self.plan[0]
        new_confirmed = self.confirmed + 1

        if new_confirmed >= self.shots_count:
            self.confirmed = new_confirmed
            await self._finalize(interaction, combat)
            return

        embed = combat.get_status_embed()
        next_shot = new_confirmed + 1
        embed.add_field(
            name=f"🎯 Выстрел {next_shot}/{self.shots_count}",
            value="Куда направить **следующий** выстрел?",
            inline=False
        )
        view = _MultiShotMenu(
            self.user_id, self.menu_id, combat,
            shots_count=self.shots_count,
            plan=self.plan,
            confirmed=new_confirmed,
        )
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка перехода: {e}")

    def create_other_target_callback(self, target_idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return
            if self._finalized:
                await interaction.response.send_message("⏳ Уже обрабатывается...", ephemeral=True)
                return
            combat = combat_manager.get_combat(self.user_id)
            if not combat:
                await interaction.response.send_message("❌ Бой не найден!", ephemeral=True)
                return

            embed = combat.get_status_embed()
            next_shot = min(self.confirmed + 1, self.shots_count)
            embed.add_field(
                name=f"🎯 Выстрел {next_shot}/{self.shots_count} → враг #{target_idx + 1}",
                value="Выберите часть тела:",
                inline=False
            )
            view = _MultiShotPartMenu(
                self.user_id, self.menu_id, combat,
                shots_count=self.shots_count,
                plan=self.plan,
                confirmed=self.confirmed,
                target_idx=target_idx,
            )
            await interaction.response.edit_message(embed=embed, view=view)

        return callback

    async def _finalize(self, interaction: discord.Interaction, combat):
        if self._finalized:
            logger.warning("⚠️ [MULTISHOT] Повторный _finalize — игнорируем")
            return
        self._finalized = True
        self._disable_all()

        if not await safe_defer(interaction):
            return
        parts = []
        for idx, part in self.plan:
            parts.append(f"{idx}:{part}")
        payload = ",".join(parts)

        logger.info(f"🎯 [MULTISHOT] Финализация: shots_count={self.shots_count}, payload={payload}")

        embed, view = await handle_combat_action(interaction, "shoot_secondary", payload)
        if embed is None:
            return
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка финализации очереди: {e}")

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        if self._finalized:
            await interaction.response.send_message("⏳ Уже обрабатывается...", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            return

        from .main_view import CombatView

        embed = combat.get_status_embed()
        view = CombatView(self.user_id)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            pass


class _MultiShotPartMenu(discord.ui.View):
    def __init__(self, user_id: int, menu_id: str, combat,
                 shots_count: int, plan: list, confirmed: int, target_idx: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.shots_count = shots_count
        self.plan = list(plan)
        self.confirmed = max(0, min(confirmed, shots_count - 1))
        self.target_idx = target_idx
        self.menu_id = uuid.uuid4().hex[:8]
        self._finalized = False

        target = combat.enemies[target_idx] if 0 <= target_idx < len(combat.enemies) else None
        if not target:
            return

        available = target.get_available_parts()
        part_emojis = {"голова": "🎯", "торс": "🫀", "руки": "💪", "ноги": "🦵"}

        for idx, part in enumerate(["голова", "торс", "руки", "ноги"]):
            if part not in available:
                continue
            btn = discord.ui.Button(
                label=f"{part_emojis.get(part, '')} {part.capitalize()}",
                style=discord.ButtonStyle.danger if part == "голова" else discord.ButtonStyle.primary,
                custom_id=f"msp_{self.menu_id}_{idx}"[:100],
                row=0
            )
            btn.callback = self.create_part_callback(part)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"msp_back_{self.menu_id}",
            row=1
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def _disable_all(self):
        for child in self.children:
            child.disabled = True

    def create_part_callback(self, part: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
                return
            if self._finalized:
                await interaction.response.send_message("⏳ Уже обрабатывается...", ephemeral=True)
                return

            combat = combat_manager.get_combat(self.user_id)
            if not combat:
                return

            self._finalized = True
            self._disable_all()

            self.plan[self.confirmed] = (self.target_idx, part)
            new_confirmed = self.confirmed + 1

            if new_confirmed >= self.shots_count:
                if not await safe_defer(interaction):
                    return
                parts = [f"{i}:{p}" for i, p in self.plan]
                payload = ",".join(parts)
                logger.info(f"🎯 [MULTISHOT] Финализация: shots_count={self.shots_count}, payload={payload}")
                embed, view = await handle_combat_action(interaction, "shoot_secondary", payload)
                if embed is None:
                    return
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка финализации очереди: {e}")
                return

            embed = combat.get_status_embed()
            next_shot = new_confirmed + 1
            embed.add_field(
                name=f"🎯 Выстрел {next_shot}/{self.shots_count}",
                value="Куда направить **следующий** выстрел?",
                inline=False
            )
            view = _MultiShotMenu(
                self.user_id, self.menu_id, combat,
                shots_count=self.shots_count,
                plan=self.plan,
                confirmed=new_confirmed,
            )
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка перехода: {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваш бой!", ephemeral=True)
            return
        if self._finalized:
            await interaction.response.send_message("⏳ Уже обрабатывается...", ephemeral=True)
            return
        combat = combat_manager.get_combat(self.user_id)
        if not combat:
            return
        embed = combat.get_status_embed()
        next_shot = min(self.confirmed + 1, self.shots_count)
        embed.add_field(
            name=f"🎯 Выстрел {next_shot}/{self.shots_count}",
            value="Куда направить **следующий** выстрел?",
            inline=False
        )
        view = _MultiShotMenu(
            self.user_id, self.menu_id, combat,
            shots_count=self.shots_count,
            plan=self.plan,
            confirmed=self.confirmed,
        )
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            pass