# -*- coding: utf-8 -*-
# func/views/faction_npc/task_board_view.py - Доска заданий NPC (0.4.8.3)
#
# ИСТОРИЯ:
#   0.4.8.3 — ФИКС: доставка не может указывать на текущую станцию игрока.

import discord
import uuid
import random

from ...factions import (
    get_faction_name, format_task, get_player_loyalty, get_player_loyalty_level,
    claim_task, TASK_TYPE_KILL, TASK_TYPE_GATHER, TASK_TYPE_PAY,
)
from ...task_board_manager import task_board_manager
from ...map_data import MAP_DATA
from database.db import save_player
from ...game_manager import game_manager
from utils.logger import get_logger

logger = get_logger()


def _fix_board_for_player(player, board: list) -> list:
    """
    Проверяет задания на доске. Если пункт назначения совпадает с локацией игрока,
    заменяет его на другую торговую станцию.
    """
    trade_stations = [
        sid for sid, st in MAP_DATA["станции"].items()
        if ("торговая" in st.get("types", []) or st.get("type") == "торговая")
    ]

    # Если торговых станций меньше 2, мы не сможем ничего изменить
    if len(trade_stations) < 2:
        return board

    for task in board:
        if task.get("type") == "delivery" and task.get("target_station") == player.location:
            # Ищем альтернативу
            valid_targets = [s for s in trade_stations if s != player.location]
            if valid_targets:
                new_target = random.choice(valid_targets)
                task["target_station"] = new_target
                task["target_faction"] = MAP_DATA["станции"][new_target].get("faction", "")
                logger.info(f"[TASKS] Исправлена доставка: цель изменена на {new_target} (игрок на {player.location})")

    return board


def build_task_board_embed(player, faction_id: str, message: str = "") -> discord.Embed:
    embed = discord.Embed(
        title=f"📋 Задания: {get_faction_name(faction_id)}",
        description=(
            f"Ваша лояльность: **{get_player_loyalty(player, faction_id)}** "
            f"очков (ур. {get_player_loyalty_level(player, faction_id)}/5)\n\n"
            f"Возьмите задание — выполните — сдайте за награду."
        ),
        color=discord.Color.dark_gold(),
    )

    if message:
        embed.add_field(name="📢 Сообщение", value=message, inline=False)

    # Получаем доску и чиним её под текущего игрока
    board = task_board_manager.get_board(faction_id, player.location)
    board = _fix_board_for_player(player, board)

    active = getattr(player, 'active_tasks', []) or []
    active_ids = {t.get("task_id") for t in active}

    for idx, task in enumerate(board):
        status = "📋 Доступно"
        if task.get("task_id") in active_ids:
            p = next((t for t in active if t.get("task_id") == task.get("task_id")), None)
            if p and p.get("completed"): status = "✅ Выполнено"
            elif p and p.get("ready_to_claim"): status = "🎁 Готово к сдаче"
            else: status = "⏳ В процессе"

        embed.add_field(
            name=f"Задание #{idx + 1} ({status})",
            value=format_task(task),
            inline=False,
        )

    embed.set_footer(text="Задания обновляются раз в 3 часа • Кнопка «Обновить» стоит 500 никелей")
    return embed


class TaskBoardView(discord.ui.View):
    def __init__(self, user_id: int, faction_id: str, npc_id: str, message: str = ""):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.faction_id = faction_id
        self.npc_id = npc_id
        self.message = message
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        player = game_manager.get_player(self.user_id)
        if not player: return

        board = task_board_manager.get_board(self.faction_id, player.location)
        board = _fix_board_for_player(player, board)

        active = getattr(player, 'active_tasks', []) or []
        active_by_id = {t.get("task_id"): t for t in active}

        for idx, task in enumerate(board[:3]):
            task_id = task.get("task_id")
            existing = active_by_id.get(task_id)

            if existing is None:
                btn = discord.ui.Button(label=f"📋 Взять #{idx + 1}", style=discord.ButtonStyle.primary, custom_id=f"tb_take_{self.menu_id}_{idx}", row=idx // 2)
                btn.callback = self.create_take_callback(task)
                self.add_item(btn)
            elif existing.get("completed"):
                btn = discord.ui.Button(label=f"✅ #{idx + 1} выполнено", style=discord.ButtonStyle.success, custom_id=f"tb_done_{self.menu_id}_{idx}", row=idx // 2, disabled=True)
                self.add_item(btn)
            else:
                btn = discord.ui.Button(label=f"🎁 Сдать #{idx + 1}", style=discord.ButtonStyle.success, custom_id=f"tb_claim_{self.menu_id}_{idx}", row=idx // 2)
                btn.callback = self.create_claim_callback(task_id)
                self.add_item(btn)

        refresh_btn = discord.ui.Button(label="🔄 Обновить (500 никелей)", style=discord.ButtonStyle.danger, custom_id=f"tb_refresh_{self.menu_id}", row=3)
        refresh_btn.callback = self.refresh_callback
        self.add_item(refresh_btn)

        back_btn = discord.ui.Button(label="🔙 Назад к NPC", style=discord.ButtonStyle.secondary, custom_id=f"tb_back_{self.menu_id}", row=3)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def _rebuild(self):
        self.clear_items()
        self._add_buttons()

    def create_take_callback(self, task: dict):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id: return

            player = game_manager.get_player(self.user_id)
            if not player: return

            if any(t.get("task_id") == task.get("task_id") for t in (getattr(player, 'active_tasks', []) or [])):
                await interaction.response.send_message("❌ Это задание уже взято.", ephemeral=True)
                return

            new_task = dict(task)
            new_task["progress"] = 0
            new_task["completed"] = False
            new_task["ready_to_claim"] = False

            # Дополнительная защита: если вдруг пункт назначения все еще совпадает
            if new_task.get("type") == "delivery" and new_task.get("target_station") == player.location:
                trade_stations = [sid for sid, st in MAP_DATA["станции"].items() if ("торговая" in st.get("types", []) or st.get("type") == "торговая") and sid != player.location]
                if trade_stations:
                    new_target = random.choice(trade_stations)
                    new_task["target_station"] = new_target
                    new_task["target_faction"] = MAP_DATA["станции"][new_target].get("faction", "")

            msg_extra = ""
            if new_task.get("type") == "delivery":
                player.inventory['хлам'] = player.inventory.get('хлам', []) + [new_task['cargo_id']]
                msg_extra = f"\n📦 Получен **Груз ({new_task['cargo_id']})**."
                if new_task.get("target_faction") == "gutagi":
                    if "временный_пропуск" not in player.inventory['хлам']:
                        player.inventory['хлам'].append("временный_пропуск")
                        msg_extra += "\n🎫 Получен **Временный пропуск Гутагов**."

            player.add_task(new_task)
            await save_player(player)

            self._rebuild()
            embed = build_task_board_embed(player, self.faction_id)
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception: pass

            try:
                await interaction.followup.send(f"✅ Задание взято: {format_task(new_task)}{msg_extra}", ephemeral=True)
            except Exception: pass

        return callback

    def create_claim_callback(self, task_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id: return

            player = game_manager.get_player(self.user_id)
            if not player: return

            ok, message = claim_task(player, task_id)
            await save_player(player)

            self._rebuild()
            embed = build_task_board_embed(player, self.faction_id)
            try: await interaction.response.edit_message(embed=embed, view=self)
            except Exception: pass
            try: await interaction.followup.send(message, ephemeral=True)
            except Exception: pass

        return callback

    async def refresh_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return
        embed = discord.Embed(title="🔄 Обновление заданий", description="Вы уверены, что хотите обновить доску заданий?\n\n💰 Стоимость: **500 никелей**\n⚠️ Это действие нельзя отменить.", color=discord.Color.orange())
        view = RefreshConfirmView(self.user_id, self.faction_id, self.npc_id)
        await interaction.response.edit_message(embed=embed, view=view)

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id: return

        player = game_manager.get_player(self.user_id)
        if not player: return

        try:
            from .dialog_view import DialogView
            new_view = DialogView(self.user_id, self.npc_id, "greeting")
            await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)
        except Exception as e:
            logger.error(f"task board back: {e}")


class RefreshConfirmView(discord.ui.View):
    def __init__(self, user_id: int, faction_id: str, npc_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.faction_id = faction_id
        self.npc_id = npc_id
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="✅ Да, обновить (500)", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваше меню!", ephemeral=True)
            return

        player = game_manager.get_player(self.user_id)
        if not player:
            await interaction.response.send_message("❌ Персонаж не найден.", ephemeral=True)
            return

        if player.inventory.get('никели', 0) < 500:
            await interaction.response.send_message("❌ У вас недостаточно никелей (нужно 500)!", ephemeral=True)
            return

        player.inventory['никели'] -= 500
        await save_player(player)

        task_board_manager.refresh_board_force(self.faction_id, player.location)

        embed = build_task_board_embed(player, self.faction_id, message="🔄 Задания обновлены за 500 никелей!")
        view = TaskBoardView(self.user_id, self.faction_id, self.npc_id)

        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваше меню!", ephemeral=True)
            return

        player = game_manager.get_player(self.user_id)
        if not player: return

        embed = build_task_board_embed(player, self.faction_id)
        view = TaskBoardView(self.user_id, self.faction_id, self.npc_id)

        await interaction.response.edit_message(embed=embed, view=view)