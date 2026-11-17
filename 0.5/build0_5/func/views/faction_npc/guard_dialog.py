# -*- coding: utf-8 -*-
# func/views/faction_npc/guard_dialog.py - Диалог с Охранником Гутагов (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.8.3 — базовый диалог (временный пропуск).
#   0.4.8.6 — Постоянный пропуск: 100% успех.
#             Временный пропуск: 95% / 5% подделка.
#             Нет пропуска: бой. Кнопка «Уйти».
#   0.4.8.7 — Кнопка «Меню» после исхода.
#             Подтверждение взятки.
#             Шанс отказа охранника от взятки.

import discord
import uuid
import random

from ...game_manager import game_manager
from database.db import save_player
from utils.logger import get_logger

logger = get_logger()

BRIBE_COST = 500
BRIBE_REFUSE_CHANCE = 10      # % — охранник не берёт деньги
BRIBE_SCAM_CHANCE = 20        # % — берёт деньги и не пускает


# ==================== ХЕЛПЕРЫ ====================

async def _show_main_menu(interaction: discord.Interaction, user_id: int):
    """Открывает главное меню игрока."""
    from ..main_menu import MainMenu, build_main_embed
    from ...map_data import MAP_DATA

    player = game_manager.get_player(user_id)
    if not player:
        return

    station_data = MAP_DATA["станции"].get(player.location, {})
    embed = build_main_embed(player, station_data)

    try:
        if not interaction.response.is_done():
            await interaction.response.edit_message(
                embed=embed, view=MainMenu(player)
            )
        else:
            await interaction.edit_original_response(
                embed=embed, view=MainMenu(player)
            )
    except Exception as e:
        logger.error(f"[GUARD] menu: {e}", exc_info=True)


# ==================== START ====================

async def start_guard_check(interaction: discord.Interaction, player, station_id: str):
    embed = discord.Embed(
        title="🛡️ Охранник Гутагов",
        description=(
            "*Охранник преграждает вам путь и протягивает руку.*\n\n"
            "— Стой. Пропуск есть?"
        ),
        color=discord.Color.dark_red(),
    )
    view = GuardDialogView(player.user_id, station_id, "check")
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        logger.error(f"[GUARD] start: {e}", exc_info=True)


# ==================== VIEW ====================

class GuardDialogView(discord.ui.View):
    def __init__(self, user_id: int, station_id: str, node: str):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.station_id = station_id
        self.node = node
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        if self.node == "check":
            show_btn = discord.ui.Button(
                label="Показать пропуск", style=discord.ButtonStyle.primary
            )
            show_btn.callback = self.show_pass
            self.add_item(show_btn)

            bribe_btn = discord.ui.Button(
                label=f"Дать взятку ({BRIBE_COST} никелей)",
                style=discord.ButtonStyle.success,
            )
            bribe_btn.callback = self.bribe_confirm
            self.add_item(bribe_btn)

            leave_btn = discord.ui.Button(
                label="Уйти", style=discord.ButtonStyle.secondary
            )
            leave_btn.callback = self.leave
            self.add_item(leave_btn)

    # ---------- Показать пропуск ----------

    async def show_pass(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return

        player = game_manager.get_player(self.user_id)
        hlam = player.inventory.get("хлам", []) if player else []

        # 1. Постоянный пропуск — 100%
        if "постоянный_пропуск" in hlam:
            embed = discord.Embed(
                title="✅ Постоянный пропуск",
                description=(
                    "*Охранник кивает, едва взглянув на жетон.*\n\n"
                    "— Свой. Проходи."
                ),
                color=discord.Color.green(),
            )
            await interaction.response.edit_message(
                embed=embed, view=_AfterGuardView(self.user_id)
            )
            if player:
                player.location = self.station_id
                await save_player(player)
            return

        # 2. Временный пропуск — 95% / 5%
        if "временный_пропуск" in hlam:
            if random.randint(1, 100) <= 95:
                embed = discord.Embed(
                    title="✅ Временный пропуск действителен",
                    description=(
                        "*Охранник долго изучает бумагу, затем кивает.*\n\n"
                        "— Проходи. Не задерживайся."
                    ),
                    color=discord.Color.green(),
                )
                await interaction.response.edit_message(
                    embed=embed, view=_AfterGuardView(self.user_id)
                )
                if player:
                    player.location = self.station_id
                    await save_player(player)
            else:
                embed = discord.Embed(
                    title="❌ Подделка!",
                    description=(
                        "*Охранник хмурится и достает оружие.*\n\n"
                        "— Это фальшивка. Ты покойник."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.response.edit_message(
                    embed=embed, view=_AfterGuardView(self.user_id)
                )

                if player:
                    for t in player.active_tasks:
                        if (
                                t.get("type") == "delivery"
                                and t.get("target_station") == self.station_id
                        ):
                            t["completed"] = True
                            t["failed"] = True
                            break
                    await save_player(player)

                    from ...combat import start_combat
                    await start_combat(
                        interaction, player, danger_level=3,
                        hostile_station=True, forced_enemy_ids=["бандит"],
                    )
            return

        # 3. Пропуска нет — бой
        embed = discord.Embed(
            title="❌ Пропуска нет",
            description=(
                "*Вы шарите по карманам, но охранник уже понял — "
                "пропуска у вас нет.*\n\n"
                "— Ты кто такой? А ну стоять!\n\n"
                "⚠️ Охранник вызывает подмогу!"
            ),
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(
            embed=embed, view=_AfterGuardView(self.user_id)
        )

        if player:
            from ...combat import start_combat
            await start_combat(
                interaction, player, danger_level=3,
                hostile_station=True, forced_enemy_ids=["бандит"],
            )

    # ---------- Взятка: подтверждение ----------

    async def bribe_confirm(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return

        player = game_manager.get_player(self.user_id)
        if not player:
            return

        nickels = player.inventory.get("никели", 0)

        embed = discord.Embed(
            title="💰 Подтверждение взятки",
            description=(
                f"Вы хотите предложить охраннику **{BRIBE_COST}** никелей.\n\n"
                f"💰 У вас: **{nickels}** никелей\n\n"
                f"⚠️ Охранник может **отказаться** или **обмануть**.\n"
                f"Вы уверены?"
            ),
            color=discord.Color.orange(),
        )
        view = _BribeConfirmView(self.user_id, self.station_id)
        await interaction.response.edit_message(embed=embed, view=view)

    # ---------- Уйти ----------

    async def leave(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return

        embed = discord.Embed(
            title="🚪 Вы ушли",
            description=(
                "*Вы решаете не связываться с охраной.*\n\n"
                "— Как знаешь."
            ),
            color=discord.Color.dark_gray(),
        )
        await interaction.response.edit_message(
            embed=embed, view=_AfterGuardView(self.user_id)
        )


# ==================== ПОДТВЕРЖДЕНИЕ ВЗЯТКИ ====================

class _BribeConfirmView(discord.ui.View):
    def __init__(self, user_id: int, station_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.station_id = station_id

    @discord.ui.button(label="✅ Да, дать взятку", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return

        player = game_manager.get_player(self.user_id)
        if not player:
            return

        if player.inventory.get("никели", 0) < BRIBE_COST:
            await interaction.response.send_message(
                f"❌ У вас нет {BRIBE_COST} никелей!", ephemeral=True
            )
            return

        roll = random.randint(1, 100)

        # --- 1. Отказ брать деньги (деньги НЕ списываются) ---
        if roll <= BRIBE_REFUSE_CHANCE:
            embed = discord.Embed(
                title="❌ Охранник отказался",
                description=(
                    "*Охранник отталкивает вашу руку с никелями.*\n\n"
                    "— Думаешь, я куплюсь? Иди отсюда, пока цел."
                ),
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(
                embed=embed, view=_AfterGuardView(self.user_id)
            )
            return

        # --- 2. Обман: берёт деньги, но не пускает ---
        if roll <= BRIBE_REFUSE_CHANCE + BRIBE_SCAM_CHANCE:
            player.inventory["никели"] = max(
                0, player.inventory.get("никели", 0) - BRIBE_COST
            )
            await save_player(player)

            embed = discord.Embed(
                title="💸 Вас обманули",
                description=(
                    f"*Охранник прячет никели и усмехается.*\n\n"
                    f"— Спасибо за **{BRIBE_COST}** никелей. Но пропуска "
                    f"у тебя нет. Убирайся.\n\n"
                    f"💰 Потеряно: **{BRIBE_COST}** никелей"
                ),
                color=discord.Color.dark_red(),
            )
            await interaction.response.edit_message(
                embed=embed, view=_AfterGuardView(self.user_id)
            )
            return

        # --- 3. Успех: берёт деньги и пускает ---
        player.inventory["никели"] = max(
            0, player.inventory.get("никели", 0) - BRIBE_COST
        )
        player.location = self.station_id
        await save_player(player)

        embed = discord.Embed(
            title="💰 Взятка принята",
            description=(
                f"*Охранник прячет никели в карман.*\n\n"
                f"— Я тебя не видел. Проходи.\n\n"
                f"💰 Потрачено: **{BRIBE_COST}** никелей"
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.edit_message(
            embed=embed, view=_AfterGuardView(self.user_id)
        )

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return

        embed = discord.Embed(
            title="🛡️ Охранник Гутагов",
            description=(
                "*Охранник преграждает вам путь и протягивает руку.*\n\n"
                "— Стой. Пропуск есть?"
            ),
            color=discord.Color.dark_red(),
        )
        view = GuardDialogView(self.user_id, self.station_id, "check")
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== ПОСЛЕ ИСХОДА ====================

class _AfterGuardView(discord.ui.View):
    """
    Кнопки после любого исхода диалога с охранником.
    Даёт возможность сразу перейти в главное меню.
    """

    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="🎮 Меню", style=discord.ButtonStyle.success)
    async def menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return

        await _show_main_menu(interaction, self.user_id)