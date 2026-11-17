# -*- coding: utf-8 -*-
# func/views/repair_view.py - Меню «Мастерить» (0.4.7.7)
#
# ИСТОРИЯ:
#   0.4.7.6 — изолента
#   0.4.7.7 — изолента + набор для ремонта

import discord
import uuid

from .helpers import game_manager, save_player
from ..repair_system import (
    get_repairable_items,
    get_available_tools,
    get_tool_count,
    get_repair_success_chance,
    repair_with_item,
    format_repair_status,
    format_repair_chance,
    REPAIR_TOOLS,
)


class RepairMenu(discord.ui.View):
    """
    Меню «Мастерить».
    Сначала игрок выбирает расходник, потом слот.

    target_tool = None → показываем выбор расходника
    target_tool = "изолента" → показываем слоты под изоленту
    """

    def __init__(self, player, target_tool: str = None):
        super().__init__(timeout=180)
        self.player = player
        self.target_tool = target_tool
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        if self.target_tool is None:
            self._add_tool_buttons()
        else:
            self._add_slot_buttons()

        # Назад — всегда
        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"rep_back_{self.menu_id}",
            row=4,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def _add_tool_buttons(self):
        """Показ выбора расходника."""
        tools = get_available_tools(self.player)
        if not tools:
            dis = discord.ui.Button(
                label="❌ Нет расходников для ремонта",
                style=discord.ButtonStyle.secondary,
                custom_id=f"rep_notools_{self.menu_id}",
                row=0,
                disabled=True,
            )
            self.add_item(dis)
            return

        for idx, tool in enumerate(tools[:4]):
            btn = discord.ui.Button(
                label=f"{tool['emoji']} {tool['name']} ×{tool['count']} (+{tool['restore']})",
                style=discord.ButtonStyle.success,
                custom_id=f"rep_tool_{self.menu_id}_{idx}",
                row=idx // 2,
            )
            btn.callback = self.create_tool_callback(tool["id"])
            self.add_item(btn)

    def _add_slot_buttons(self):
        """Показ слотов для выбранного расходника."""
        items = get_repairable_items(self.player)
        tool_id = self.target_tool
        tool_cfg = REPAIR_TOOLS.get(tool_id, {})
        tool_count = get_tool_count(self.player, tool_id)

        idx = 0
        for it in items:
            if not it["can_repair"]:
                btn = discord.ui.Button(
                    label=f"✅ {it['emoji']} {it['name']} ({it['percent']}%)"[:80],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"rep_ok_{self.menu_id}_{idx}",
                    row=idx // 2,
                    disabled=True,
                )
                self.add_item(btn)
                idx += 1
                continue

            label = f"🔧 {it['emoji']} {it['name']} ({it['current']:.0f}/{it['max']:.0f})"
            btn = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"rep_{it['slot']}_{self.menu_id}_{idx}",
                row=idx // 2,
                disabled=(tool_count <= 0),
            )
            btn.callback = self.create_repair_callback(it["slot"], tool_id)
            self.add_item(btn)
            idx += 1

    # ==================== CALLBACKS ====================

    def create_tool_callback(self, tool_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            new_view = RepairMenu(self.player, target_tool=tool_id)
            embed = new_view._build_embed()
            try:
                await interaction.response.edit_message(embed=embed, view=new_view)
            except Exception:
                pass

        return callback

    def create_repair_callback(self, slot: str, tool_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            result = repair_with_item(self.player, slot, tool_id=tool_id)
            await save_player(self.player)

            # После ремонта — возвращаем в выбор слотов того же расходника
            embed = self._build_embed(result=result)
            new_view = RepairMenu(self.player, target_tool=tool_id)

            try:
                await interaction.edit_original_response(embed=embed, view=new_view)
            except Exception:
                pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        # Если были в выборе слота — возвращаемся в выбор расходника.
        if self.target_tool is not None:
            new_view = RepairMenu(self.player, target_tool=None)
            embed = new_view._build_embed()
            try:
                await interaction.response.edit_message(embed=embed, view=new_view)
            except Exception:
                pass
            return

        # Иначе — назад в ActionMenu.
        try:
            from .action_menu import ActionMenu
            embed = discord.Embed(
                title="🎯 Действия",
                description="Выберите действие:",
                color=discord.Color.blue(),
            )
            await interaction.response.edit_message(embed=embed, view=ActionMenu())
        except Exception:
            pass

    # ==================== EMBED ====================

    def _build_embed(self, result: dict = None) -> discord.Embed:
        embed = discord.Embed(
            title="🔨 Мастерить",
            color=discord.Color.orange(),
        )

        if self.target_tool is None:
            embed.description = (
                "Выберите **расходник** для ремонта.\n\n"
                "• 🩹 **Изолента** — восстанавливает 5 прочности.\n"
                "• 🧰 **Набор для ремонта** — восстанавливает 25 прочности."
            )
        else:
            tool_cfg = REPAIR_TOOLS.get(self.target_tool, {})
            embed.description = (
                f"Ремонт через {tool_cfg.get('emoji', '🧰')} "
                f"**{tool_cfg.get('name', self.target_tool)}** "
                f"(+{tool_cfg.get('restore', 0)} прочности).\n"
                f"Выберите слот:"
            )

        embed.add_field(
            name="📦 Состояние снаряжения",
            value=format_repair_status(self.player),
            inline=False,
        )
        embed.add_field(
            name="🎲 Шансы и расходники",
            value=format_repair_chance(self.player),
            inline=False,
        )

        if result:
            embed.add_field(
                name="🧰 Результат",
                value=result.get("message", "—"),
                inline=False,
            )

        embed.set_footer(text="💡 Инженерия повышает шанс ремонта. Купить расходники — в Мастерской.")
        return embed


def build_repair_embed(player) -> discord.Embed:
    view = RepairMenu(player)
    return view._build_embed()