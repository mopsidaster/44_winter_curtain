# -*- coding: utf-8 -*-
# func/views/surface_events/raider_dialog.py - Диалог с Рейдером (0.4.8.9.1)
#
# ИСТОРИЯ:
#   0.4.8.8   — новый файл.
#   0.4.8.9   — parent_future: диалог завершается через future родителя.
#   0.4.8.9.1 — _quick_ack: сначала ответ, потом save_player.

import discord
import uuid
import asyncio

from database.db import save_player
from utils.logger import get_logger

logger = get_logger()


class RaiderDialogView(discord.ui.View):
    def __init__(self, interaction, leader, group_players: list,
                 success_chance: int, parent_future: asyncio.Future = None):
        super().__init__(timeout=300)
        self.interaction = interaction
        self.leader = leader
        self.group_players = list(group_players) or [leader]
        self.success_chance = success_chance
        self.menu_id = uuid.uuid4().hex[:8]
        self.parent_future = parent_future

        if success_chance >= 40:
            self._build_high()
        else:
            self._build_low()

    def _finish(self, combat_started: bool = False):
        if self.parent_future is not None and not self.parent_future.done():
            self.parent_future.set_result({
                "combat_started": combat_started,
            })

    async def _quick_ack(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    content="⏳ ...", embed=None, view=None
                )
        except discord.errors.NotFound:
            pass
        except Exception as e:
            logger.debug(f"[RAIDER] quick_ack: {e}")

    async def start(self):
        embed = self._embed()
        try:
            if not self.interaction.response.is_done():
                await self.interaction.response.edit_message(
                    embed=embed, view=self
                )
            else:
                await self.interaction.edit_original_response(
                    embed=embed, view=self
                )
        except Exception as e:
            logger.error(f"[RAIDER] start: {e}", exc_info=True)
            self._finish(combat_started=False)

    # ==================== EMBED ====================

    def _embed(self, text=None) -> discord.Embed:
        if text is None:
            if self.success_chance >= 40:
                text = (
                    "Рейдер: Кажется, я вас знаю! Начальник, ты ж со "
                    "своими Южку держишь в здравии, чего на поверхность "
                    "то сунулся?"
                )
            else:
                text = (
                    "Рейдер: Мальки, вы че тут забыли? Пиздуйте нахер "
                    "отседа, пока не прикокошил в сугроб!"
                )
        return discord.Embed(
            title="☠️ Рейдер",
            description=text,
            color=discord.Color.dark_red(),
        )

    # ==================== LOW CHANCE (<40%) ====================

    def _build_low(self):
        self.clear_items()

        b1 = discord.ui.Button(
            label="Ты как нас назвал, урод!",
            style=discord.ButtonStyle.danger,
            custom_id=f"rd_low_fight_{self.menu_id}",
        )
        b1.callback = self._low_fight
        self.add_item(b1)

        b2 = discord.ui.Button(
            label="Здоровяк, давай разойдемся",
            style=discord.ButtonStyle.primary,
            custom_id=f"rd_low_talk_{self.menu_id}",
        )
        b2.callback = self._low_talk
        self.add_item(b2)

    async def _low_fight(self, interaction):
        await self._quick_ack(interaction)
        await self._answer(
            interaction,
            embed=discord.Embed(
                title="☠️ Рейдер",
                description="Рейдер: Ну всё, ты покойник!",
                color=discord.Color.dark_red(),
            ),
            view=None,
        )
        await self._start_raider_combat(interaction, bonus_xp=False)

    async def _low_talk(self, interaction):
        # Сначала просто перерисовываем сообщение с новым текстом
        text = (
            "Рейдер: Никели при себе? Начальник, готовь 50% с каждого, "
            "мне на проставиться нужно будет..."
        )
        self.clear_items()

        b1 = discord.ui.Button(
            label="Нет у нас щас денег, давай иначе!",
            style=discord.ButtonStyle.danger,
            custom_id=f"rd_low_nomoney_{self.menu_id}",
        )
        b1.callback = self._low_nomoney
        self.add_item(b1)

        b2 = discord.ui.Button(
            label="Бросить коробку никелей Рейдеру",
            style=discord.ButtonStyle.success,
            custom_id=f"rd_low_pay_{self.menu_id}",
        )
        b2.callback = self._low_pay
        self.add_item(b2)

        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    embed=self._embed(text), view=self
                )
            else:
                await interaction.edit_original_response(
                    embed=self._embed(text), view=self
                )
        except Exception as e:
            logger.error(f"[RAIDER] low_talk: {e}")

    async def _low_nomoney(self, interaction):
        await self._quick_ack(interaction)
        await self._answer(
            interaction,
            embed=discord.Embed(
                title="☠️ Рейдер",
                description="Рейдер: Тогда сдохните!",
                color=discord.Color.dark_red(),
            ),
            view=None,
        )
        await self._start_raider_combat(interaction, bonus_xp=False)

    async def _low_pay(self, interaction):
        await self._quick_ack(interaction)

        total_paid = 0
        for p in self.group_players:
            nickels = p.inventory.get("никели", 0)
            pay = nickels // 2
            p.inventory["никели"] = nickels - pay
            total_paid += pay
            await save_player(p)

        await self._answer(
            interaction,
            embed=discord.Embed(
                title="💰 Рейдер доволен",
                description=(
                    f"Вы отдали Рейдеру **{total_paid}** никелей "
                    f"(50% с каждого).\n\n"
                    f"Рейдер: Идите, мальки. И не попадайтесь мне "
                    f"больше на глаза."
                ),
                color=discord.Color.gold(),
            ),
            view=None,
        )
        self._finish(combat_started=False)

    # ==================== HIGH CHANCE (>=40%) ====================

    def _build_high(self):
        self.clear_items()

        b1 = discord.ui.Button(
            label="Показать, что и здесь не промах!",
            style=discord.ButtonStyle.danger,
            custom_id=f"rd_high_fight_{self.menu_id}",
        )
        b1.callback = self._high_fight
        self.add_item(b1)

        b2 = discord.ui.Button(
            label="Брат, давай разойдемся по хорошему",
            style=discord.ButtonStyle.success,
            custom_id=f"rd_high_talk_{self.menu_id}",
        )
        b2.callback = self._high_talk
        self.add_item(b2)

    async def _high_fight(self, interaction):
        await self._quick_ack(interaction)
        await self._answer(
            interaction,
            embed=discord.Embed(
                title="☠️ Рейдер",
                description=(
                    "Рейдер: Ну-ну, посмотрим, чего вы стоите!\n\n"
                    "⚔️ **Бой!** Все в группе получат **+50% опыта** "
                    "за победу над Рейдером!"
                ),
                color=discord.Color.dark_red(),
            ),
            view=None,
        )
        await self._start_raider_combat(interaction, bonus_xp=True)

    async def _high_talk(self, interaction):
        await self._quick_ack(interaction)
        await self._answer(
            interaction,
            embed=discord.Embed(
                title="☠️ Рейдер",
                description=(
                    "Рейдер: Идите. И чтобы я вас больше не видел."
                ),
                color=discord.Color.green(),
            ),
            view=None,
        )
        self._finish(combat_started=False)

    # ==================== HELPERS ====================

    async def _answer(self, interaction, *, embed=None, content=None,
                      view=None, ephemeral=False):
        kwargs = {}
        if embed is not None:
            kwargs["embed"] = embed
        if content is not None:
            kwargs["content"] = content
        if view is not None:
            kwargs["view"] = view
        try:
            if not interaction.response.is_done():
                kwargs["ephemeral"] = ephemeral
                await interaction.response.edit_message(**kwargs)
            else:
                await interaction.edit_original_response(**kwargs)
        except Exception:
            try:
                await interaction.followup.send(**kwargs, ephemeral=ephemeral)
            except Exception:
                pass

    async def _start_raider_combat(self, interaction, bonus_xp: bool):
        from ...combat import start_combat as start_combat_func

        leader = self.leader
        extra = [p for p in self.group_players if p.user_id != leader.user_id]

        if bonus_xp:
            for p in self.group_players:
                p.raider_bonus_xp = True

        try:
            await start_combat_func(
                interaction, leader, danger_level=5,
                hostile_station=False, extra_players=extra,
                forced_enemy_ids=["рейдер", "носач_рафик", "носач_жуля"],
            )
        except Exception as e:
            logger.error(f"[RAIDER] start_combat: {e}", exc_info=True)

        self._finish(combat_started=True)