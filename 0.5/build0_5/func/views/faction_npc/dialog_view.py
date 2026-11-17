# -*- coding: utf-8 -*-
# func/views/faction_npc/dialog_view.py - Универсальная view диалога NPC (0.4.8.7.3)
#
# ИСТОРИЯ:
#   0.4.8.3 — Квесты на вступление, Бутовская линия, «На поверхность!».
#   0.4.8.4 — Истомин «За Южный периметр», Варяг «Плата за безопасность».
#   0.4.8.5 — БЕЗ defer. _safe_answer.
#   0.4.8.6 — Гарантия fallback, передержка пропуска.
#   0.4.8.7 — open_trader (Ганс, Радеон), __trader_loyalty_text__.
#   0.4.8.7.3 — Сдача «За Южный периметр» у Варяга.

import discord
import uuid
import re

from .dialog_trees import DIALOG_TREES
from ...factions import (
    get_npc_data, get_faction_name, get_faction_emoji,
    get_player_loyalty, get_player_loyalty_level, get_loyalty_progress,
    get_player_relation_to, get_relation_meta,
    can_join_faction, join_faction, get_join_quest_requirements,
    get_npc_faction_for_tasks, add_player_loyalty,
)
from ...task_board_manager import task_board_manager
from config.map_config import ITEMS
from utils.logger import get_logger

logger = get_logger()

# === константы квестов ===
SOUTH_PERIMETER_INFO_PRICE = 1000
SECURITY_QUEST_ID = "quest_security_pass"
SECURITY_QUEST_LOYALTY_REWARD = 25
SECURITY_QUEST_PASS_ID = "постоянный_пропуск"


# ==================== ХЕЛПЕРЫ ====================

def _extract_emoji_for_button(emoji_str: str):
    if not emoji_str:
        return None
    match = re.match(r'<(a?):([a-zA-Z0-9_]+):(\d+)>', emoji_str)
    if match:
        return discord.PartialEmoji(
            name=match.group(2), id=int(match.group(3)),
            animated=bool(match.group(1)),
        )
    return emoji_str


def _replace_vars(text: str, player, npc: dict) -> str:
    if "__loyalty_text__" in text:
        faction_id = npc.get("faction") or npc.get("mediates_for")
        if faction_id:
            loyalty = get_player_loyalty(player, faction_id)
            level = get_player_loyalty_level(player, faction_id)
            progress = get_loyalty_progress(player, faction_id)
            relation = get_player_relation_to(player, faction_id)
            relation_meta = get_relation_meta(relation)
            faction_name = get_faction_name(faction_id)

            if not progress.get("next_threshold"):
                next_line = "Максимальный уровень."
            else:
                next_line = (
                    f"До следующего уровня: "
                    f"**{progress['next_threshold'] - loyalty}** очков"
                )

            text = (
                f"Фракция: **{faction_name}**\n"
                f"Отношение: {relation_meta['emoji']} {relation_meta['name']}\n"
                f"Лояльность: **{loyalty}** очков (уровень {level})\n"
                f"{next_line}"
            )
        else:
            text = "Неизвестно."

    # 0.4.8.7: __trader_loyalty_text__<id>__
    for match in re.finditer(r"__trader_loyalty_text__(\w+)__", text):
        trader_id = match.group(1)
        try:
            from ...independent_traders import (
                get_trader_loyalty_progress, get_trader_name,
            )
            progress = get_trader_loyalty_progress(player, trader_id)
            tname = get_trader_name(trader_id)
            replacement = (
                f"Торговец: **{tname}**\n"
                f"Лояльность: **{progress['points']}** очков "
                f"(ур. {progress['level']}/2)"
            )
        except Exception:
            replacement = "—"
        text = text.replace(match.group(0), replacement)

    text = text.replace("{player_name}", getattr(player, "name", "?"))
    text = text.replace(
        "{player_origin}", getattr(player, "origin", "неизвестно")
    )
    return text


def _get_player(user_id: int):
    try:
        from ...game_manager import game_manager
        return game_manager.get_player(user_id)
    except Exception as e:
        logger.error(f"[NPC] _get_player: {e}")
        return None


def _has_security_quest(player) -> bool:
    tasks = getattr(player, 'active_tasks', []) or []
    return any(t.get("task_id") == SECURITY_QUEST_ID for t in tasks)


def _has_security_pass(player) -> bool:
    hlam = player.inventory.get("хлам", []) or []
    return SECURITY_QUEST_PASS_ID in hlam


def _security_quest_ready(player) -> bool:
    for t in (getattr(player, 'active_tasks', []) or []):
        if t.get("task_id") == SECURITY_QUEST_ID:
            return bool(t.get("ready_to_claim")) and not t.get("rewarded")
    return False


def _security_quest_taken(player) -> bool:
    for t in (getattr(player, 'active_tasks', []) or []):
        if t.get("task_id") == SECURITY_QUEST_ID:
            return not t.get("ready_to_claim") and not t.get("rewarded")
    return False


def _varyag_keeps_pass(player) -> bool:
    return bool(getattr(player, 'varyag_pass_kept', False))


async def _safe_answer(interaction, *, embed=None, content=None, view=None,
                       ephemeral=False, edit=False):
    kwargs = {}
    if embed is not None:
        kwargs["embed"] = embed
    if content is not None:
        kwargs["content"] = content
    if view is not None:
        kwargs["view"] = view
    if not edit:
        kwargs["ephemeral"] = ephemeral

    try:
        if edit:
            if not interaction.response.is_done():
                await interaction.response.edit_message(**kwargs)
            else:
                await interaction.edit_original_response(**kwargs)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(**kwargs)
            else:
                await interaction.followup.send(**kwargs)
    except discord.errors.NotFound:
        logger.warning("[NPC] interaction истёк (NotFound)")
    except discord.errors.InteractionResponded:
        try:
            await interaction.followup.send(**kwargs)
        except Exception as e:
            logger.error(f"[NPC] followup: {e}")
    except Exception as e:
        logger.error(f"[NPC] answer: {e}", exc_info=True)


# ==================== DIALOG VIEW ====================

class DialogView(discord.ui.View):
    def __init__(self, user_id: int, npc_id: str, node_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.npc_id = npc_id
        self.node_id = node_id
        self.menu_id = uuid.uuid4().hex[:8]
        try:
            self._add_buttons()
        except Exception as e:
            logger.error(
                f"[NPC] _add_buttons({npc_id}/{node_id}): {e}",
                exc_info=True,
            )

    def _get_npc(self) -> dict:
        return get_npc_data(self.npc_id) or {}

    def _get_tree(self) -> dict:
        return DIALOG_TREES.get(self._get_npc().get("dialog_tree"), {})

    def _get_node(self) -> dict:
        return self._get_tree().get("nodes", {}).get(self.node_id, {})

    def _add_buttons(self):
        node = self._get_node()
        options = node.get("options", [])
        player = _get_player(self.user_id)

        logger.info(
            f"[NPC] _add_buttons: npc={self.npc_id}, node={self.node_id}, "
            f"options={len(options)}, player={'yes' if player else 'no'}"
        )

        for idx, opt in enumerate(options[:5]):
            label = opt.get("label", "…")
            style = discord.ButtonStyle.primary
            action = opt.get("action")
            next_node = opt.get("next")

            if next_node == "boutovskaya_ask":
                if player and get_player_loyalty_level(player, "antiquars") < 3:
                    continue

            if next_node == "south_perimeter":
                if player and get_player_loyalty_level(player, "gess") < 3:
                    continue

            if next_node == "security_quest":
                if player:
                    if _has_security_pass(player):
                        btn = discord.ui.Button(
                            label="Постоянный пропуск получен", emoji="✅",
                            style=discord.ButtonStyle.secondary,
                            custom_id=f"npc_pass_done_{self.menu_id}",
                            disabled=True,
                            row=0,
                        )
                        self.add_item(btn)
                        continue
                    if _varyag_keeps_pass(player):
                        btn = discord.ui.Button(
                            label="Пропуск на передержке", emoji="🎫",
                            style=discord.ButtonStyle.secondary,
                            custom_id=f"npc_pass_kept_{self.menu_id}",
                            disabled=True,
                            row=0,
                        )
                        self.add_item(btn)
                        continue
                    if _security_quest_ready(player):
                        btn = discord.ui.Button(
                            label="Сдать квест «Плата за безопасность»",
                            emoji="✅",
                            style=discord.ButtonStyle.success,
                            custom_id=f"npc_security_turnin_{self.menu_id}",
                            row=0,
                        )
                        btn.callback = self.turnin_security_quest_callback()
                        self.add_item(btn)
                        continue
                    if _security_quest_taken(player):
                        btn = discord.ui.Button(
                            label="Квест «Плата за безопасность» выполняется",
                            emoji="⏳",
                            style=discord.ButtonStyle.secondary,
                            custom_id=f"npc_security_active_{self.menu_id}",
                            disabled=True,
                            row=0,
                        )
                        self.add_item(btn)
                        continue

            if action in (
                    "join_faction", "unlock_surface", "pay_for_info",
                    "take_security_quest", "turnin_security_quest",
                    "open_trader",
            ):
                style = discord.ButtonStyle.success
            elif next_node is None and not action:
                style = discord.ButtonStyle.secondary

            btn = discord.ui.Button(
                label=label[:80], style=style,
                custom_id=f"npc_{self.npc_id}_{idx}_{self.menu_id}",
                row=0 if idx < 4 else 1,
            )

            if action:
                btn.callback = self.create_action_callback(action)
            else:
                btn.callback = self.create_next_callback(next_node)

            self.add_item(btn)

        try:
            task_faction = get_npc_faction_for_tasks(self.npc_id)
        except Exception as e:
            logger.error(f"[NPC] task_faction: {e}")
            task_faction = ""

        if task_faction and self.node_id == "greeting" and not self._is_trader():
            tb_btn = discord.ui.Button(
                label="Задания", emoji="📋",
                style=discord.ButtonStyle.success,
                custom_id=f"npc_tb_{self.npc_id}_{self.menu_id}", row=2,
            )
            tb_btn.callback = self.open_task_board_callback(task_faction)
            self.add_item(tb_btn)

        if player and self.node_id == "greeting":
            ready_cargo = [
                t for t in (getattr(player, 'active_tasks', []) or [])
                if t.get("type") == "delivery"
                   and t.get("completed")
                   and not t.get("rewarded")
                   and t.get("faction_id") == task_faction
            ]

            if ready_cargo:
                cargo_btn = discord.ui.Button(
                    label="Сдать выручку", emoji="💰",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"npc_cargo_{self.npc_id}_{self.menu_id}",
                    row=2,
                )
                cargo_btn.callback = self.open_cargo_turnin_callback(
                    task_faction, ready_cargo
                )
                self.add_item(cargo_btn)

            if self.npc_id == "посредник_бандитов":
                bandit_cargo = [
                    t for t in (getattr(player, 'active_tasks', []) or [])
                    if t.get("type") == "delivery"
                       and not t.get("rewarded")
                ]
                if bandit_cargo:
                    b_cargo_btn = discord.ui.Button(
                        label="Сдать груз Бандитам", emoji="📦",
                        style=discord.ButtonStyle.danger,
                        custom_id=f"npc_bandit_cargo_{self.menu_id}",
                        row=2,
                    )
                    b_cargo_btn.callback = self.bandit_cargo_callback(
                        bandit_cargo
                    )
                    self.add_item(b_cargo_btn)

            if (
                    self.npc_id == "дмитрий_борисович"
                    and get_player_loyalty_level(player, "antiquars") >= 3
            ):
                has_quest = any(
                    t.get("task_id") == "quest_surface"
                    for t in (getattr(player, 'active_tasks', []) or [])
                )
                has_completed = any(
                    t.get("task_id") == "quest_surface" and t.get("rewarded")
                    for t in (getattr(player, 'active_tasks', []) or [])
                )

                if (
                        not has_quest
                        and not has_completed
                        and getattr(player, 'surface_unlocked', False)
                ):
                    take_btn = discord.ui.Button(
                        label="Взять квест «На поверхность!»",
                        emoji="📜",
                        style=discord.ButtonStyle.primary,
                        custom_id=f"npc_take_surface_{self.menu_id}",
                        row=3,
                    )
                    take_btn.callback = self.take_surface_quest_callback()
                    self.add_item(take_btn)

                elif has_quest and not has_completed:
                    quest = next(
                        (t for t in player.active_tasks
                         if t.get("task_id") == "quest_surface"),
                        None,
                    )
                    if quest:
                        hlam = player.inventory.get("хлам", [])
                        if hlam.count("шкура_мерзляка") >= 5:
                            turnin_btn = discord.ui.Button(
                                label="Сдать квест (На поверхность!)",
                                emoji="✅",
                                style=discord.ButtonStyle.success,
                                custom_id=f"npc_quest_turnin_{self.menu_id}",
                                row=3,
                            )
                            turnin_btn.callback = (
                                self.turnin_surface_quest_callback()
                            )
                            self.add_item(turnin_btn)
                        else:
                            info_btn = discord.ui.Button(
                                label="Нужно 5 шкур Мерзляка",
                                emoji="❌",
                                style=discord.ButtonStyle.secondary,
                                custom_id=f"npc_quest_info_{self.menu_id}",
                                row=3, disabled=True,
                            )
                            self.add_item(info_btn)

            if self.npc_id == "илья_варяг":
                has_pass_in_inv = _has_security_pass(player)
                kept = _varyag_keeps_pass(player)

                if has_pass_in_inv and not kept:
                    keep_btn = discord.ui.Button(
                        label="Оставить пропуск на передержку",
                        emoji="🎫",
                        style=discord.ButtonStyle.primary,
                        custom_id=f"npc_keep_pass_{self.menu_id}",
                        row=3,
                    )
                    keep_btn.callback = self.keep_pass_callback()
                    self.add_item(keep_btn)

                elif kept and not has_pass_in_inv:
                    take_btn = discord.ui.Button(
                        label="Забрать пропуск",
                        emoji="🎫",
                        style=discord.ButtonStyle.success,
                        custom_id=f"npc_take_pass_{self.menu_id}",
                        row=3,
                    )
                    take_btn.callback = self.take_pass_callback()
                    self.add_item(take_btn)

                # 0.4.8.7.3: сдача квеста «За Южный периметр»
                quest_south = next(
                    (t for t in (getattr(player, 'active_tasks', []) or [])
                     if t.get("task_id") == "quest_south_perimeter"
                     and not t.get("rewarded")),
                    None,
                )
                if quest_south:
                    turnin_btn = discord.ui.Button(
                        label="Сдать квест «За Южный периметр»",
                        emoji="✅",
                        style=discord.ButtonStyle.success,
                        custom_id=f"npc_south_turnin_{self.menu_id}",
                        row=2,
                    )
                    turnin_btn.callback = self.turnin_south_perimeter_callback()
                    self.add_item(turnin_btn)

        if len(self.children) == 0:
            logger.warning(
                f"[NPC] ВНИМАНИЕ: 0 кнопок для {self.npc_id}/{self.node_id} "
                f"(options={len(options)}), добавляю fallback"
            )
            fallback = discord.ui.Button(
                label="🔙 Назад",
                style=discord.ButtonStyle.secondary,
                custom_id=f"npc_fallback_back_{self.menu_id}",
                row=0,
            )
            fallback.callback = self.create_next_callback(None)
            self.add_item(fallback)

    def _is_trader(self) -> bool:
        npc = self._get_npc()
        return bool(npc.get("trader_id"))

    # ==================== CALLBACKS ====================

    def create_next_callback(self, next_node):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await _safe_answer(
                    interaction, content="❌ Не ваш диалог!",
                    ephemeral=True,
                )
                return

            if next_node is None:
                try:
                    player = _get_player(self.user_id)
                    if not player:
                        await _safe_answer(
                            interaction, content="❌ Игрок не найден.",
                            ephemeral=True,
                        )
                        return

                    from ..main_menu import MainMenu, build_main_embed
                    from ...map_data import MAP_DATA

                    station_data = MAP_DATA["станции"].get(
                        player.location, {}
                    )
                    embed = build_main_embed(player, station_data)
                    await _safe_answer(
                        interaction, embed=embed,
                        view=MainMenu(player), edit=True,
                    )
                except Exception as e:
                    logger.error(f"[NPC] finish: {e}", exc_info=True)
                    await _safe_answer(
                        interaction, content=f"❌ Ошибка: {e}",
                        ephemeral=True,
                    )
                return

            try:
                new_view = DialogView(self.user_id, self.npc_id, next_node)
                embed = new_view.build_embed()
                await _safe_answer(
                    interaction, embed=embed, view=new_view, edit=True,
                )
            except Exception as e:
                logger.error(f"[NPC] next: {e}", exc_info=True)
                await _safe_answer(
                    interaction, content=f"❌ Ошибка: {e}",
                    ephemeral=True,
                )

        return callback

    def create_action_callback(self, action: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await _safe_answer(
                    interaction, content="❌ Не ваш диалог!",
                    ephemeral=True,
                )
                return

            npc = self._get_npc()
            faction_id = npc.get("faction") or npc.get("mediates_for")
            if not faction_id and action != "open_trader":
                await _safe_answer(
                    interaction, content="❌ Ошибка NPC.",
                    ephemeral=True,
                )
                return

            try:
                if action == "join_faction":
                    await self._handle_join_faction(interaction, npc, faction_id)
                elif action == "unlock_surface":
                    await self._handle_unlock_surface(interaction)
                elif action == "pay_for_info":
                    await self._handle_pay_for_info(interaction)
                elif action == "take_security_quest":
                    await self._handle_take_security_quest(interaction)
                elif action == "turnin_security_quest":
                    await self._handle_turnin_security_quest(interaction)
                elif action == "open_trader":
                    await self._handle_open_trader(interaction)
            except Exception as e:
                logger.error(
                    f"[NPC] action {action}: {e}", exc_info=True
                )
                await _safe_answer(
                    interaction, content=f"❌ Ошибка: {e}",
                    ephemeral=True,
                )

        return callback

    def turnin_security_quest_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await _safe_answer(
                    interaction, content="❌ Не ваш диалог!",
                    ephemeral=True,
                )
                return
            try:
                await self._handle_turnin_security_quest(interaction)
            except Exception as e:
                logger.error(
                    f"[NPC] turnin_security: {e}", exc_info=True
                )
                await _safe_answer(
                    interaction, content=f"❌ Ошибка: {e}",
                    ephemeral=True,
                )

        return callback

    def keep_pass_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await _safe_answer(
                    interaction, content="❌ Не ваш диалог!",
                    ephemeral=True,
                )
                return
            from database.db import save_player

            player = _get_player(self.user_id)
            if not player:
                return

            if not _has_security_pass(player):
                await _safe_answer(
                    interaction,
                    content="❌ У вас нет постоянного пропуска.",
                    ephemeral=True,
                )
                return

            hlam = player.inventory.get("хлам", []) or []
            if SECURITY_QUEST_PASS_ID in hlam:
                hlam.remove(SECURITY_QUEST_PASS_ID)
            player.inventory['хлам'] = hlam
            player.varyag_pass_kept = True
            await save_player(player)

            embed = discord.Embed(
                title="🎫 Пропуск оставлен у Варяга",
                description=(
                    "Варяг убирает жетон в сейф.\n\n"
                    "«Будет ждать тебя здесь. Захочешь — заберёшь.»\n\n"
                    "⚠️ Пока пропуск у Варяга, проход на территорию Гутагов "
                    "будет через охранника (возможен провал)."
                ),
                color=discord.Color.blue(),
            )

            try:
                new_view = DialogView(self.user_id, self.npc_id, "greeting")
                await _safe_answer(
                    interaction, embed=new_view.build_embed(),
                    view=new_view, edit=True,
                )
            except Exception:
                pass

            await _safe_answer(interaction, embed=embed, ephemeral=True)

        return callback

    def take_pass_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await _safe_answer(
                    interaction, content="❌ Не ваш диалог!",
                    ephemeral=True,
                )
                return
            from database.db import save_player

            player = _get_player(self.user_id)
            if not player:
                return

            if not _varyag_keeps_pass(player):
                await _safe_answer(
                    interaction,
                    content="❌ У Варяга нет вашего пропуска.",
                    ephemeral=True,
                )
                return

            if _has_security_pass(player):
                await _safe_answer(
                    interaction,
                    content="✅ Пропуск уже у вас в инвентаре.",
                    ephemeral=True,
                )
                return

            hlam = player.inventory.get("хлам", []) or []
            if SECURITY_QUEST_PASS_ID not in hlam:
                hlam.append(SECURITY_QUEST_PASS_ID)
            player.inventory['хлам'] = hlam
            player.varyag_pass_kept = False
            await save_player(player)

            embed = discord.Embed(
                title="🎫 Пропуск возвращён",
                description=(
                    "Варяг достаёт жетон из сейфа и протягивает вам.\n\n"
                    "«Держи. Больше не теряй.»"
                ),
                color=discord.Color.green(),
            )

            try:
                new_view = DialogView(self.user_id, self.npc_id, "greeting")
                await _safe_answer(
                    interaction, embed=new_view.build_embed(),
                    view=new_view, edit=True,
                )
            except Exception:
                pass

            await _safe_answer(interaction, embed=embed, ephemeral=True)

        return callback

    # 0.4.8.7.3: сдача «За Южный периметр»
    def turnin_south_perimeter_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return
            from database.db import save_player

            player = _get_player(self.user_id)
            if not player:
                return

            quest = next(
                (t for t in (getattr(player, 'active_tasks', []) or [])
                 if t.get("task_id") == "quest_south_perimeter"
                 and not t.get("rewarded")),
                None,
            )
            if not quest:
                await _safe_answer(
                    interaction,
                    content="❌ Квест не найден.",
                    ephemeral=True,
                )
                return

            quest["completed"] = True
            quest["rewarded"] = True

            add_player_loyalty(player, "gess", 25)
            await save_player(player)

            embed = discord.Embed(
                title="✅ Информация получена",
                description=(
                    "Варяг кивает.\n\n"
                    "«Ты знаешь, где я. Если понадобится — "
                    "приходи. Пропуск получишь за работу.»\n\n"
                    "💠 Лояльность ГЭС: **+25**"
                ),
                color=discord.Color.gold(),
            )

            try:
                new_view = DialogView(self.user_id, self.npc_id, "greeting")
                await _safe_answer(
                    interaction, embed=new_view.build_embed(),
                    view=new_view, edit=True,
                )
            except Exception:
                pass

            await _safe_answer(interaction, embed=embed, ephemeral=True)

        return callback

    # ==================== ОБРАБОТЧИКИ ДЕЙСТВИЙ ====================

    async def _handle_open_trader(self, interaction: discord.Interaction):
        from ...independent_traders import get_trader
        from ..independent_trader_view import IndependentTraderView

        npc = self._get_npc()
        trader_id = npc.get("trader_id")
        if not trader_id or not get_trader(trader_id):
            await _safe_answer(
                interaction, content="❌ Ошибка торговца.",
                ephemeral=True,
            )
            return

        player = _get_player(self.user_id)
        if not player:
            return

        view = IndependentTraderView(player, trader_id, page="buy")
        embed = view.build_embed()
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    embed=embed, view=view
                )
            else:
                await interaction.edit_original_response(
                    embed=embed, view=view
                )
        except Exception as e:
            logger.error(f"[NPC] open_trader: {e}", exc_info=True)

    async def _handle_join_faction(self, interaction, npc, faction_id):
        from database.db import save_player

        player = _get_player(self.user_id)
        if not player:
            await _safe_answer(
                interaction, content="❌ Игрок не найден.",
                ephemeral=True,
            )
            return

        target_faction = npc.get("mediates_for") or npc.get("faction")

        ok, reason = can_join_faction(player, target_faction)
        if not ok:
            join_task_id = f"join_{target_faction}"
            has_task = any(
                t.get("task_id") == join_task_id
                for t in player.active_tasks
            )

            if not has_task:
                req = get_join_quest_requirements(target_faction)
                req_text = []
                if req.get("nickels"):
                    req_text.append(f"💰 {req['nickels']} никелей")
                for item, cnt in req.get("items", {}).items():
                    item_name = ITEMS.get('sell', {}).get(
                        item, {}
                    ).get('name', item)
                    req_text.append(f"📦 {cnt}× {item_name}")

                player.add_task({
                    "task_id": join_task_id,
                    "type": "join_faction",
                    "faction_id": target_faction,
                    "name": f"Вступление: {get_faction_name(target_faction)}",
                    "completed": False,
                    "ready_to_claim": False,
                    "desc": ", ".join(req_text),
                })
                await save_player(player)
                await _safe_answer(
                    interaction,
                    content=(
                        f"📜 **Вы взяли задание на вступление!**\n"
                        f"Требования: {', '.join(req_text)}\n"
                        f"Оно появилось в вашем журнале."
                    ),
                    ephemeral=True,
                )
            else:
                await _safe_answer(
                    interaction, content=reason, ephemeral=True
                )
            return

        ok, reason = join_faction(player, target_faction)
        if ok:
            await save_player(player)

        try:
            new_view = DialogView(self.user_id, self.npc_id, "greeting")
            await _safe_answer(
                interaction, embed=new_view.build_embed(),
                view=new_view, edit=True,
            )
        except Exception:
            pass
        await _safe_answer(
            interaction, content=reason, ephemeral=True
        )

    async def _handle_unlock_surface(self, interaction):
        from database.db import save_player

        player = _get_player(self.user_id)
        if not player:
            await _safe_answer(
                interaction, content="❌ Игрок не найден.",
                ephemeral=True,
            )
            return

        if get_player_loyalty_level(player, "antiquars") < 3:
            await _safe_answer(
                interaction,
                content="❌ Вам нужно 3-й уровень лояльности!",
                ephemeral=True,
            )
            return

        player.surface_unlocked = True
        await save_player(player)

        embed = discord.Embed(
            title="🌐 Бутовская линия открыта!",
            description=(
                "Дмитрий Борисович дал вам координаты безопасного прохода.\n\n"
                "Теперь вы можете выходить на поверхность через станции "
                "**Бутовской линии** (Скобелевская и др.).\n\n"
                "⚠️ **Осторожно:** На поверхности очень холодно и водятся "
                "Мерзляки. Готовьтесь к бою!"
            ),
            color=discord.Color.green(),
        )

        try:
            new_view = DialogView(self.user_id, self.npc_id, "greeting")
            await _safe_answer(
                interaction, embed=new_view.build_embed(),
                view=new_view, edit=True,
            )
        except Exception:
            pass

        await _safe_answer(interaction, embed=embed, ephemeral=True)

    async def _handle_pay_for_info(self, interaction):
        from database.db import save_player

        player = _get_player(self.user_id)
        if not player:
            await _safe_answer(
                interaction, content="❌ Игрок не найден.",
                ephemeral=True,
            )
            return

        if get_player_loyalty_level(player, "gess") < 3:
            await _safe_answer(
                interaction,
                content=(
                    "❌ Истомин не станет говорить с вами на такие темы "
                    "(нужна лояльность ГЭС 3+)."
                ),
                ephemeral=True,
            )
            return

        already = any(
            t.get("task_id") == "quest_south_perimeter"
            for t in (getattr(player, 'active_tasks', []) or [])
        )
        if already:
            await _safe_answer(
                interaction,
                content=(
                    "ℹ️ Истомин уже дал вам наводку. Ищите Илью \"Варяга\" "
                    "на Павелецкой-Зелёной."
                ),
                ephemeral=True,
            )
            return

        if player.inventory.get('никели', 0) < SOUTH_PERIMETER_INFO_PRICE:
            await _safe_answer(
                interaction,
                content=(
                    f"❌ Нужно **{SOUTH_PERIMETER_INFO_PRICE}** никелей, "
                    f"у вас **{player.inventory.get('никели', 0)}**."
                ),
                ephemeral=True,
            )
            return

        player.inventory['никели'] -= SOUTH_PERIMETER_INFO_PRICE

        player.add_task({
            "task_id": "quest_south_perimeter",
            "type": "special",
            "faction_id": "gess",
            "name": "За Южный периметр",
            "desc": (
                "Найти Илью \"Варяга\" на Павелецкой-Зелёной и получить "
                "постоянный пропуск Гутагов."
            ),
            "completed": False,
            "ready_to_claim": False,
            "progress": 0,
            "count": 1,
        })
        await save_player(player)

        embed = discord.Embed(
            title="📜 Информация получена",
            description=(
                f"Истомин забирает **{SOUTH_PERIMETER_INFO_PRICE}** никелей "
                f"и понижает голос.\n\n"
                f"«Илья \"Варяг\", посредник Гутагов. Сейчас он на "
                f"**Павелецкой-Зелёной**. Скажи, что от Истомина — он "
                f"поймёт. Но учти: просто так пропуск он не даст. "
                f"Придётся поработать.»\n\n"
                f"📋 Задание добавлено в журнал: **За Южный периметр**"
            ),
            color=discord.Color.green(),
        )

        try:
            new_view = DialogView(self.user_id, self.npc_id, "greeting")
            await _safe_answer(
                interaction, embed=new_view.build_embed(),
                view=new_view, edit=True,
            )
        except Exception:
            pass

        await _safe_answer(interaction, embed=embed, ephemeral=True)

    async def _handle_take_security_quest(self, interaction):
        from database.db import save_player

        player = _get_player(self.user_id)
        if not player:
            await _safe_answer(
                interaction, content="❌ Игрок не найден.",
                ephemeral=True,
            )
            return

        if _has_security_pass(player):
            await _safe_answer(
                interaction,
                content="✅ У вас уже есть постоянный пропуск.",
                ephemeral=True,
            )
            return

        if _varyag_keeps_pass(player):
            await _safe_answer(
                interaction,
                content="ℹ️ Ваш пропуск уже лежит у Варяга. Заберите его.",
                ephemeral=True,
            )
            return

        if _has_security_quest(player):
            await _safe_answer(
                interaction,
                content=(
                    "ℹ️ Квест уже взят. Зачистите схрон на «Нагатинской»."
                ),
                ephemeral=True,
            )
            return

        player.add_task({
            "task_id": SECURITY_QUEST_ID,
            "type": "kill",
            "faction_id": "gutagi",
            "name": "Плата за безопасность",
            "desc": (
                "Зачистить схрон бандитов на станции «Нагатинская» "
                "(5 бандитов)."
            ),
            "target": "бандит",
            "target_name": "Бандит",
            "count": 5,
            "progress": 0,
            "completed": False,
            "ready_to_claim": False,
        })
        await save_player(player)

        embed = discord.Embed(
            title="📜 Квест взят: Плата за безопасность",
            description=(
                "Варяг кивает.\n\n"
                "«Схрон на **Нагатинской**. Бандиты, человек пять. "
                "Зачистишь — жетон твой. Не зачистишь — не возвращайся.»\n\n"
                "📋 Задание добавлено в журнал."
            ),
            color=discord.Color.green(),
        )

        try:
            new_view = DialogView(self.user_id, self.npc_id, "greeting")
            await _safe_answer(
                interaction, embed=new_view.build_embed(),
                view=new_view, edit=True,
            )
        except Exception:
            pass

        await _safe_answer(interaction, embed=embed, ephemeral=True)

    async def _handle_turnin_security_quest(self, interaction):
        from database.db import save_player

        player = _get_player(self.user_id)
        if not player:
            await _safe_answer(
                interaction, content="❌ Игрок не найден.",
                ephemeral=True,
            )
            return

        if not _security_quest_ready(player):
            await _safe_answer(
                interaction,
                content="❌ Сначала зачистите схрон на «Нагатинской».",
                ephemeral=True,
            )
            return

        if _has_security_pass(player) or _varyag_keeps_pass(player):
            await _safe_answer(
                interaction,
                content="✅ У вас уже есть постоянный пропуск.",
                ephemeral=True,
            )
            return

        for t in (getattr(player, 'active_tasks', []) or []):
            if t.get("task_id") == SECURITY_QUEST_ID:
                t["rewarded"] = True
                t["completed"] = True
                break

        hlam = player.inventory.get("хлам", []) or []
        if SECURITY_QUEST_PASS_ID not in hlam:
            hlam.append(SECURITY_QUEST_PASS_ID)
        player.inventory['хлам'] = hlam
        add_player_loyalty(player, "gutagi", SECURITY_QUEST_LOYALTY_REWARD)

        await save_player(player)

        embed = discord.Embed(
            title="✅ Постоянный пропуск получен",
            description=(
                f"Варяг протягивает вам металлический жетон.\n\n"
                f"«Держи. Теперь Гутаги тебя знают. Не подведи.»\n\n"
                f"🎫 **Постоянный пропуск** добавлен в инвентарь.\n"
                f"💠 Лояльность Гутагов: "
                f"**+{SECURITY_QUEST_LOYALTY_REWARD}**"
            ),
            color=discord.Color.gold(),
        )

        try:
            new_view = DialogView(self.user_id, self.npc_id, "greeting")
            await _safe_answer(
                interaction, embed=new_view.build_embed(),
                view=new_view, edit=True,
            )
        except Exception:
            pass

        await _safe_answer(interaction, embed=embed, ephemeral=True)

    # ==================== СТАРЫЕ ОБРАБОТЧИКИ ====================

    def open_task_board_callback(self, faction_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return

            try:
                player = _get_player(self.user_id)
                if not player:
                    await _safe_answer(
                        interaction, content="❌ Персонаж не найден.",
                        ephemeral=True,
                    )
                    return

                from .task_board_view import (
                    TaskBoardView, build_task_board_embed,
                )

                embed = build_task_board_embed(player, faction_id)
                view = TaskBoardView(self.user_id, faction_id, self.npc_id)
                await _safe_answer(
                    interaction, embed=embed, view=view, edit=True,
                )
            except Exception as e:
                logger.error(f"[NPC] task board: {e}", exc_info=True)
                await _safe_answer(
                    interaction, content=f"❌ Ошибка: {e}",
                    ephemeral=True,
                )

        return callback

    def open_cargo_turnin_callback(self, faction_id: str, ready_cargo: list):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return
            from database.db import save_player

            player = _get_player(self.user_id)
            if not player:
                return

            total_reward = 0
            total_loyalty = 0

            for t in ready_cargo:
                if not t.get("rewarded"):
                    t["rewarded"] = True
                    total_reward += t.get("reward", 0)
                    total_loyalty += t.get("loyalty_reward", 0)
                    player.inventory['никели'] += t.get("reward", 0)

            if total_reward > 0:
                add_player_loyalty(player, faction_id, total_loyalty)
                await save_player(player)

                embed = discord.Embed(
                    title="💰 Груз сдан!",
                    description=(
                        f"Вы отдали выручку.\n\n"
                        f"💰 Получено: **{total_reward}** никелей\n"
                        f"💠 Лояльность: **+{total_loyalty}**"
                    ),
                    color=discord.Color.green(),
                )

                try:
                    new_view = DialogView(
                        self.user_id, self.npc_id, "greeting"
                    )
                    await _safe_answer(
                        interaction, embed=new_view.build_embed(),
                        view=new_view, edit=True,
                    )
                except Exception:
                    pass

                await _safe_answer(
                    interaction, embed=embed, ephemeral=True
                )
            else:
                await _safe_answer(
                    interaction,
                    content="❌ Нет грузов для сдачи.",
                    ephemeral=True,
                )

        return callback

    def bandit_cargo_callback(self, cargo_tasks):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return
            from database.db import save_player

            player = _get_player(self.user_id)
            if not player:
                return

            total_loyalty = 0
            for t in cargo_tasks:
                if not t.get("rewarded"):
                    t["rewarded"] = True
                    total_loyalty += 25

            if total_loyalty > 0:
                add_player_loyalty(player, "bandits", total_loyalty)
                await save_player(player)

                embed = discord.Embed(
                    title="🕴️ Груз сдан Бандитам",
                    description=(
                        f"Посредник забрал груз.\n\n"
                        f"💠 Лояльность Бандитов: **+{total_loyalty}**"
                    ),
                    color=discord.Color.dark_red(),
                )

                try:
                    new_view = DialogView(
                        self.user_id, self.npc_id, "greeting"
                    )
                    await _safe_answer(
                        interaction, embed=new_view.build_embed(),
                        view=new_view, edit=True,
                    )
                except Exception:
                    pass

                await _safe_answer(
                    interaction, embed=embed, ephemeral=True
                )
            else:
                await _safe_answer(
                    interaction,
                    content="❌ Нет грузов для сдачи.",
                    ephemeral=True,
                )

        return callback

    def take_surface_quest_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return
            from database.db import save_player

            player = _get_player(self.user_id)
            if not player:
                return

            quest = {
                "task_id": "quest_surface",
                "type": "special",
                "faction_id": "antiquars",
                "name": "На поверхность!",
                "completed": False,
                "ready_to_claim": False,
                "progress": 0,
                "count": 1,
            }
            player.add_task(quest)
            await save_player(player)

            embed = discord.Embed(
                title="📜 Квест взят",
                description=(
                    "Дмитрий Борисович ждет от вас 5 шкур Мерзляка. "
                    "Возвращайтесь, когда принесете их."
                ),
                color=discord.Color.green(),
            )

            try:
                new_view = DialogView(self.user_id, self.npc_id, "greeting")
                await _safe_answer(
                    interaction, embed=new_view.build_embed(),
                    view=new_view, edit=True,
                )
            except Exception:
                pass

            await _safe_answer(interaction, embed=embed, ephemeral=True)

        return callback

    def turnin_surface_quest_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return
            from database.db import save_player

            player = _get_player(self.user_id)
            if not player:
                return

            quest = next(
                (t for t in player.active_tasks
                 if t.get("task_id") == "quest_surface"),
                None,
            )
            if not quest or quest.get("rewarded"):
                return

            hlam = player.inventory.get("хлам", [])
            if hlam.count("шкура_мерзляка") < 5:
                await _safe_answer(
                    interaction,
                    content="❌ Вам нужно 5 шкур Мерзляка!",
                    ephemeral=True,
                )
                return

            for _ in range(5):
                if "шкура_мерзляка" in hlam:
                    hlam.remove("шкура_мерзляка")
            player.inventory['хлам'] = hlam

            quest["rewarded"] = True
            quest["completed"] = True

            player.inventory['никели'] = (
                    player.inventory.get('никели', 0) + 1500
            )
            player.add_xp(500)
            player.inventory['тактическая_аптечка'] = (
                    player.inventory.get('тактическая_аптечка', 0) + 5
            )

            if "бутовский_странник_броня" not in player.armor_inventory:
                player.armor_inventory.append("бутовский_странник_броня")
            if "бутовский_странник_шлем" not in player.armor_inventory:
                player.armor_inventory.append("бутовский_странник_шлем")

            await save_player(player)

            embed = discord.Embed(
                title="✅ Квест сдан!",
                description=(
                    "Вы получили награду:\n"
                    "💰 1500 никелей\n"
                    "⭐ 500 опыта\n"
                    "🧥 Сет Бутовского Странника\n"
                    "💊 5 тактических аптечек"
                ),
                color=discord.Color.gold(),
            )

            try:
                new_view = DialogView(self.user_id, self.npc_id, "greeting")
                await _safe_answer(
                    interaction, embed=new_view.build_embed(),
                    view=new_view, edit=True,
                )
            except Exception:
                pass

            await _safe_answer(interaction, embed=embed, ephemeral=True)

        return callback

    def build_embed(self) -> discord.Embed:
        player = _get_player(self.user_id)

        npc = self._get_npc()
        node = self._get_node()

        speaker = node.get("speaker", npc.get("name", "Неизвестный"))
        raw_text = node.get("text", "...")
        text = _replace_vars(raw_text, player, npc) if player else raw_text

        faction_id = npc.get("faction") or npc.get("mediates_for")

        embed = discord.Embed(
            title=f"{npc.get('name', speaker)}",
            description=f"**{speaker}:** {text}",
            color=(
                discord.Color.dark_gold()
                if faction_id else discord.Color.greyple()
            ),
        )

        if faction_id:
            faction_name = get_faction_name(faction_id)
            emoji_str = get_faction_emoji(faction_id)
            emoji_obj = _extract_emoji_for_button(emoji_str)

            if isinstance(emoji_obj, discord.PartialEmoji):
                embed.set_author(
                    name=f"{faction_name}", icon_url=emoji_obj.url
                )
            else:
                embed.set_footer(text=f"{emoji_str} {faction_name}")
        else:
            embed.set_footer(text="Метро 44: White Curtain")

        return embed


def build_npc_embed(user_id: int, npc_id: str, node_id: str) -> discord.Embed:
    return DialogView(user_id, npc_id, node_id).build_embed()