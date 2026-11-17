# -*- coding: utf-8 -*-
# func/views/faction_npc/journal_view.py - Журнал (0.4.8.9)
# ИСТОРИЯ:
#   0.4.8.9 — Добавлена вкладка "📖 Обучение" (Туториал).

import discord
import uuid

from ...factions import (
    format_task, get_faction_name, get_join_quest_requirements,
)
from ...task_board_manager import task_board_manager
from config.map_config import ITEMS
from ..tutorial import TutorialView, build_tutorial_page

class JournalView(discord.ui.View):
    def __init__(self, player, page: int = 0):
        super().__init__(timeout=180)
        self.player = player
        self.page = page  # 0 = Личные, 1 = Контракты
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        # Вкладки
        personal_btn = discord.ui.Button(
            label="Личные", emoji="📜",
            style=discord.ButtonStyle.success if self.page == 0 else discord.ButtonStyle.secondary,
            custom_id=f"jrnl_p_{self.menu_id}", row=0, disabled=(self.page == 0),
        )
        personal_btn.callback = self.create_nav_callback(0)
        self.add_item(personal_btn)

        contracts_btn = discord.ui.Button(
            label="Контракты", emoji="📋",
            style=discord.ButtonStyle.success if self.page == 1 else discord.ButtonStyle.secondary,
            custom_id=f"jrnl_c_{self.menu_id}", row=0, disabled=(self.page == 1),
        )
        contracts_btn.callback = self.create_nav_callback(1)
        self.add_item(contracts_btn)

        # Вкладка обучения (всегда активна для нажатия)
        tutorial_btn = discord.ui.Button(
            label="Обучение", emoji="📖",
            style=discord.ButtonStyle.primary,
            custom_id=f"jrnl_t_{self.menu_id}", row=0
        )
        tutorial_btn.callback = self.open_tutorial_callback()
        self.add_item(tutorial_btn)

        back_btn = discord.ui.Button(
            label="Назад", emoji="🔙", style=discord.ButtonStyle.danger,
            custom_id=f"jrnl_b_{self.menu_id}", row=4,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_nav_callback(self, target_page: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return
            new_view = JournalView(self.player, page=target_page)
            embed = new_view.build_embed()
            await interaction.response.edit_message(embed=embed, view=new_view)
        return callback

    def open_tutorial_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return
            embed = build_tutorial_page(1)
            view = TutorialView(self.player.user_id, page=1)
            await interaction.response.edit_message(embed=embed, view=view)
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        from ..action_menu import ActionMenu
        embed = discord.Embed(
            title="🎯 Действия",
            description="Выберите действие:",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=ActionMenu())

    def build_embed(self) -> discord.Embed:
        if self.page == 0:
            return _build_personal_embed(self.player)
        return _build_contracts_embed(self.player)

def _build_personal_embed(player) -> discord.Embed:
    tasks = getattr(player, 'active_tasks', []) or []
    embed = discord.Embed(title="📜 Личные квесты", color=discord.Color.gold())

    personal_ids = ("quest_surface", "quest_south_perimeter", "quest_security_pass")
    personal = [t for t in tasks if t.get("task_id") in personal_ids and not t.get("rewarded")]

    if not personal:
        embed.description = "У вас нет личных квестов.\n\n💡 Поговорите с Дмитрием Борисовичем или Варягом."
        return embed

    for t in personal:
        tid = t.get("task_id")
        status = "🎁 Готово к сдаче" if t.get("ready_to_claim") else "⏳ Выполняется"

        if tid == "quest_surface":
            title = "📜 **На поверхность!**"
            desc = "Принести 5 шкур Мерзляка"
        elif tid == "quest_south_perimeter":
            title = "📜 **За Южный периметр**"
            desc = "Найти Илью \"Варяга\" на Павелецкой-Зелёной"
        elif tid == "quest_security_pass":
            progress = t.get("progress", 0)
            count = t.get("count", 5)
            title = "📜 **Плата за безопасность**"
            desc = f"Зачистить схрон бандитов на «Нагатинской» ({progress}/{count})"
        else:
            title = f"📜 {t.get('name', tid)}"
            desc = t.get("desc", "")

        embed.add_field(name=f"{title} — {status}", value=desc, inline=False)

    return embed

def _build_contracts_embed(player) -> discord.Embed:
    tasks = getattr(player, 'active_tasks', []) or []
    embed = discord.Embed(title="📋 Контракты", color=discord.Color.dark_gold())

    join_tasks = [t for t in tasks if t.get("task_id", "").startswith("join_") and not t.get("rewarded")]
    if join_tasks:
        embed.add_field(name="📜 Вступление во фракции", value="", inline=False)
        for t in join_tasks:
            fid = t.get("faction_id")
            fname = get_faction_name(fid)
            req = get_join_quest_requirements(fid)
            req_text = []
            if req.get("nickels"):
                req_text.append(f"💰 {req['nickels']} никелей")
            for item, cnt in req.get("items", {}).items():
                item_name = ITEMS.get('sell', {}).get(item, {}).get('name', item)
                req_text.append(f"📦 {cnt}× {item_name}")
            embed.add_field(name=f"Вступить в {fname}", value="\n".join(req_text), inline=False)

    from ...independent_traders import (
        get_all_traders, get_trader_board, get_trader_name, format_trader_task,
    )
    trader_ids = list(get_all_traders().keys())

    board_tasks = []
    for t in tasks:
        if t.get("rewarded") or t.get("task_id") in (
                "quest_surface", "quest_south_perimeter", "quest_security_pass"
        ):
            continue
        if t.get("task_id", "").startswith("join_"):
            continue

        faction_id = t.get("faction_id")
        if not faction_id:
            continue

        if faction_id in trader_ids:
            board = get_trader_board(faction_id)
            board_task = next((bt for bt in board if bt.get("task_id") == t.get("task_id")), None)
            if board_task or t.get("ready_to_claim"):
                board_tasks.append((t, get_trader_name(faction_id), True))
        else:
            board = task_board_manager.get_board(faction_id, player.location)
            board_task = next((bt for bt in board if bt.get("task_id") == t.get("task_id")), None)
            if board_task or t.get("ready_to_claim"):
                board_tasks.append((t, get_faction_name(faction_id), False))

    if board_tasks:
        embed.add_field(name="⏳ Задания с доски", value="", inline=False)
        for t, source_name, is_trader in board_tasks:
            status = "🎁 Готово к сдаче" if t.get("ready_to_claim") else "⏳ Выполняется"
            task_text = format_trader_task(t) if is_trader else format_task(t)
            embed.add_field(name=f"{source_name} — {status}", value=task_text, inline=False)

    if not join_tasks and not board_tasks:
        embed.description = "У вас нет контрактов.\n\n💡 Возьмите задания у NPC или торговцев."

    return embed

def build_journal_embed(player) -> discord.Embed:
    """Обратная совместимость — для /status."""
    return _build_personal_embed(player)