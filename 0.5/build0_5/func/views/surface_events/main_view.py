# -*- coding: utf-8 -*-
# func/views/surface_events/main_view.py - 9 интерактивных ивентов (0.4.8.9.1)
#
# ИСТОРИЯ:
#   0.4.8.8   — новый файл: 9 ивентов поверхности.
#   0.4.8.9   — Ждём завершения ивента через asyncio.Future.
#   0.4.8.9.1 — ФИКС: "Приложение не ответило вовремя".
#               _quick_ack() первым делом, потом save_player/урон.

import discord
import uuid
import random
import asyncio

from config.map_config import BALANCE, WEAPONS
from ...disease_system import add_chemical, add_radiation
from ...combat import start_combat
from database.db import save_player
from utils.logger import get_logger

logger = get_logger()


class SurfaceEventView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction,
                 leader, group_players: list, event_id: str):
        super().__init__(timeout=300)
        self.interaction = interaction
        self.leader = leader
        self.group_players = list(group_players) or [leader]
        self.event_id = event_id
        self.menu_id = uuid.uuid4().hex[:8]
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        self.result_future: asyncio.Future = loop.create_future()
        self._build()

    def finish(self, combat_started: bool = False):
        if not self.result_future.done():
            self.result_future.set_result({
                "combat_started": combat_started,
            })

    def _is_group(self) -> bool:
        return len(self.group_players) > 1

    async def start(self):
        embed = self._build_embed()
        try:
            if not self.interaction.response.is_done():
                await self.interaction.response.edit_message(
                    embed=embed, view=self
                )
            else:
                await self.interaction.edit_original_response(
                    embed=embed, view=self
                )
        except discord.errors.NotFound:
            logger.warning("[SURFACE] interaction истёк (start)")
            self.finish(combat_started=False)
        except Exception as e:
            logger.error(f"[SURFACE] start send: {e}", exc_info=True)
            self.finish(combat_started=False)

    # ==================== EMBED ====================

    def _build_embed(self) -> discord.Embed:
        is_group = self._is_group()
        group_note = (
            f"\n\n👥 **Группа: {len(self.group_players)} чел.**"
            f" (решение принимает **{self.leader.name}**)"
            if is_group else ""
        )
        data = self._data()
        return discord.Embed(
            title=data["title"],
            description=data["description"] + group_note,
            color=data["color"],
        )

    def _data(self) -> dict:
        eid = self.event_id
        if eid == "pack_merzlyaks":
            return {
                "title": "🐺 Стая Мерзляков",
                "description": (
                    "Вы замечаете стаю Мерзляков, проходящих мимо..."
                ),
                "color": discord.Color.dark_orange(),
            }
        if eid == "snowdrift":
            return {
                "title": "❄️ Сугроб",
                "description": (
                    "Вы идете по переходу, как вдруг замечаете, что впереди "
                    "довольно мягкий снег..."
                ),
                "color": discord.Color.light_grey(),
            }
        if eid == "pack_strazh":
            return {
                "title": "🐕 Стая Стражей",
                "description": (
                    "Вы услышали знакомый вой. Не Мерзляки, однако "
                    "не менее опасны..."
                ),
                "color": discord.Color.dark_red(),
            }
        if eid == "demon":
            return {
                "title": "🦅 Демон",
                "description": (
                    "Вы идете вдоль Бутовских метро-мостов, как вдруг "
                    "на Вас набрасывается Демон..."
                ),
                "color": discord.Color.dark_purple(),
            }
        if eid == "encirclement":
            return {
                "title": "🐕 Окружение",
                "description": (
                    "По пути вдоль Бутовских метро-мостов Вас подстерегла "
                    "стая Стражей..."
                ),
                "color": discord.Color.dark_red(),
            }
        if eid == "lured_merzlyak":
            return {
                "title": "🐺 Ведомый Мерзляк",
                "description": (
                    "По пути вдоль Бутовских метро-мостов перед Вами "
                    "выпрыгивает облизывающийся Мерзляк..."
                ),
                "color": discord.Color.dark_orange(),
            }
        if eid == "raider":
            return {
                "title": "☠️ Рейдер",
                "description": (
                    "Идя вдоль Бутовских метро-мостов, вы замечаете "
                    "впереди массивную фигуру, идущую навстречу. Как тут же "
                    "союзник замечает, как из сугроба выпрыгивает Носач..."
                ),
                "color": discord.Color.dark_red(),
            }
        if eid == "artifact_bridge":
            return {
                "title": "💠 Артефакт под мостом",
                "description": (
                    "Вы проходите под очередной секцией метро-моста, "
                    "как вдруг замечаете свечение под одной из колонн..."
                ),
                "color": discord.Color.teal(),
            }
        if eid == "artifact_lobby":
            return {
                "title": "💎 Артефакт в вестибюле",
                "description": (
                    "Проходя вестибюль станции, вы начинаете слышать "
                    "скрежет..."
                ),
                "color": discord.Color.teal(),
            }
        return {
            "title": "🌫️ Поверхность",
            "description": "...",
            "color": discord.Color.light_grey(),
        }

    # ==================== BUTTONS ====================

    def _clear(self):
        self.clear_items()

    def _add_btn(self, label, style, callback):
        btn = discord.ui.Button(
            label=label[:80], style=style,
            custom_id=f"se_{self.event_id}_{len(self.children)}_{self.menu_id}",
        )
        btn.callback = callback
        self.add_item(btn)

    def _build(self):
        self._clear()
        eid = self.event_id

        if eid == "pack_merzlyaks":
            self._add_btn("Пропустить", discord.ButtonStyle.secondary,
                          self._merzlyak_skip)
            self._add_btn("Начать обстрел", discord.ButtonStyle.danger,
                          self._merzlyak_shoot)
        elif eid == "snowdrift":
            self._add_btn("Идти дальше", discord.ButtonStyle.primary,
                          self._snowdrift_go)
        elif eid == "pack_strazh":
            self._add_btn("Затаиться", discord.ButtonStyle.secondary,
                          self._strazh_hide)
            self._add_btn("Начать бой", discord.ButtonStyle.danger,
                          self._strazh_fight)
            self._add_btn("Бросить гранату", discord.ButtonStyle.success,
                          self._strazh_grenade)
        elif eid == "demon":
            self._add_btn("Вступить в бой", discord.ButtonStyle.danger,
                          self._demon_fight)
            self._add_btn("Укрыться в здании", discord.ButtonStyle.secondary,
                          self._demon_hide)
        elif eid == "encirclement":
            self._add_btn("Принять бой", discord.ButtonStyle.danger,
                          self._encircle_fight)
            self._add_btn("Отвлекающая граната", discord.ButtonStyle.success,
                          self._encircle_grenade)
        elif eid == "lured_merzlyak":
            self._add_btn("Принять бой", discord.ButtonStyle.danger,
                          self._lured_fight)
            self._add_btn("Убежать", discord.ButtonStyle.secondary,
                          self._lured_flee)
        elif eid == "raider":
            self._add_btn("Принять бой", discord.ButtonStyle.danger,
                          self._raider_fight)
            self._add_btn("Попытаться поговорить", discord.ButtonStyle.primary,
                          self._raider_talk)
            self._add_btn("Нашуметь", discord.ButtonStyle.success,
                          self._raider_noise)
        elif eid == "artifact_bridge":
            self._add_btn("Посмотреть поближе", discord.ButtonStyle.primary,
                          self._artifact_bridge_near)
            self._add_btn("Идти дальше", discord.ButtonStyle.secondary,
                          self._artifact_bridge_skip)
        elif eid == "artifact_lobby":
            self._add_btn("Уйти", discord.ButtonStyle.secondary,
                          self._artifact_lobby_skip)
            self._add_btn("Остаться и слушать", discord.ButtonStyle.primary,
                          self._artifact_lobby_listen)

    # ==================== HELPERS ====================

    async def _quick_ack(self, interaction: discord.Interaction):
        """
        0.4.8.9.1: мгновенный ответ, чтобы не было таймаута 3 сек.
        Вызывается ПЕРВЫМ в тяжёлых callback'ах.
        """
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    content="⏳ ...", embed=None, view=None
                )
        except discord.errors.NotFound:
            pass
        except Exception as e:
            logger.debug(f"[SURFACE] quick_ack: {e}")

    async def _finish_and_answer(self, interaction: discord.Interaction,
                                 text: str, combat_started: bool = False):
        """
        Финальный embed после тяжёлых операций.
        Использует edit_original_response (response уже вызван в _quick_ack).
        """
        embed = discord.Embed(
            description=text, color=discord.Color.dark_gray()
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    embed=embed, content=None, view=None
                )
            else:
                await interaction.edit_original_response(
                    embed=embed, content=None, view=None
                )
        except discord.errors.NotFound:
            pass
        except Exception as e:
            logger.error(
                f"[SURFACE] finish_and_answer: {e}", exc_info=True
            )

        self.finish(combat_started=combat_started)

    async def _answer(self, interaction: discord.Interaction, *,
                      embed=None, content=None, view=None, ephemeral=False):
        kwargs = {}
        if embed is not None:
            kwargs["embed"] = embed
        if content is not None:
            kwargs["content"] = content
        if view is not None:
            kwargs["view"] = view
        if not view and not embed and not content:
            kwargs["content"] = "…"
        if not interaction.response.is_done():
            kwargs["ephemeral"] = ephemeral
            try:
                await interaction.response.edit_message(**kwargs)
                return
            except Exception:
                pass
        try:
            await interaction.edit_original_response(**kwargs)
        except Exception:
            try:
                await interaction.followup.send(**kwargs, ephemeral=ephemeral)
            except Exception:
                pass

    async def _close(self, interaction, text: str, combat_started: bool = False):
        await self._quick_ack(interaction)
        await self._finish_and_answer(interaction, text, combat_started)

    async def _apply_damage_to_all(self, amount_per_part: float):
        for p in self.group_players:
            alive_parts = p.get_alive_body_parts()
            if not alive_parts:
                continue
            part = random.choice(alive_parts)
            p.take_body_part_damage(part, amount_per_part)
            await save_player(p)

    async def _add_cold_to_all(self, amount: float):
        for p in self.group_players:
            from ...cold_system import ensure_cold_fields
            ensure_cold_fields(p)
            p.cold = min(100.0, (getattr(p, "cold", 0.0) or 0.0) + amount)
            await save_player(p)

    async def _add_chem_to_all(self, amount: float):
        for p in self.group_players:
            add_chemical(p, amount)
            await save_player(p)

    async def _start_combat_for_group(self, interaction, enemy_ids: list):
        from ...combat import start_combat as start_combat_func

        leader = self.leader
        extra = [p for p in self.group_players if p.user_id != leader.user_id]

        try:
            await start_combat_func(
                interaction, leader, danger_level=5,
                hostile_station=False, extra_players=extra,
                forced_enemy_ids=enemy_ids,
            )
        except Exception as e:
            logger.error(f"[SURFACE] start_combat: {e}", exc_info=True)

        self.finish(combat_started=True)

    # ==================== 1. PACK MERZLYAKS ====================

    async def _merzlyak_skip(self, interaction):
        await self._close(
            interaction,
            "🐺 Вы тихо обошли стаю. Мерзляки вас не заметили."
        )

    async def _merzlyak_shoot(self, interaction):
        await self._close(
            interaction,
            "🔫 Вы открыли огонь по стае! Мерзляки бросаются на вас!"
        )
        await self._start_combat_for_group(
            interaction,
            ["мерзляк", "мерзляк_охотник", "мерзляк"]
        )

    # ==================== 2. SNOWDRIFT ====================

    async def _snowdrift_go(self, interaction):
        await self._quick_ack(interaction)

        roll = random.randint(1, 100)
        if roll <= 50:
            await self._finish_and_answer(
                interaction,
                "❄️ Вы аккуратно прошли по мягкому снегу. Обошлось."
            )
            return

        await self._add_cold_to_all(25.0)
        await self._apply_damage_to_all(8.0)
        await self._finish_and_answer(
            interaction,
            "❄️ **Вы провалились в снег!**\n"
            "🥶 Холод: **+25** (вне зависимости от брони)\n"
            "💥 Урон: **8** по случайным частям тела"
        )

    # ==================== 3. PACK STRAZH ====================

    async def _strazh_hide(self, interaction):
        await self._quick_ack(interaction)

        roll = random.randint(1, 100)
        if roll <= 75:
            await self._finish_and_answer(
                interaction,
                "🐕 Вы затаились. Стражи прошли мимо."
            )
            return

        embed = discord.Embed(
            description="🐕 Стражи вас заметили! Бой!",
            color=discord.Color.dark_gray(),
        )
        try:
            await interaction.edit_original_response(
                embed=embed, content=None, view=None
            )
        except Exception:
            pass
        await self._start_combat_for_group(interaction, ["страж", "страж"])

    async def _strazh_fight(self, interaction):
        await self._close(interaction, "🐕 Вы бросаетесь в бой со Стражами!")
        await self._start_combat_for_group(interaction, ["страж", "страж"])

    async def _strazh_grenade(self, interaction):
        await self._quick_ack(interaction)

        leader = self.leader
        grenades = (
            leader.get_all_grenades()
            if hasattr(leader, "get_all_grenades") else {}
        )
        if not grenades:
            embed = discord.Embed(
                description="💣 У вас нет гранат! Придётся драться.",
                color=discord.Color.dark_gray(),
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, content=None, view=None
                )
            except Exception:
                pass
            await self._start_combat_for_group(
                interaction, ["страж", "страж"]
            )
            return

        gid = next(iter(grenades))
        if hasattr(leader, "consume_grenade"):
            leader.consume_grenade(gid)
            await save_player(leader)

        roll = random.randint(1, 100)
        if roll <= 50:
            await self._finish_and_answer(
                interaction,
                "💣 Граната взорвалась в стае! Стражи разбежались."
            )
        else:
            embed = discord.Embed(
                description="💣 Граната не остановила стаю! Бой!",
                color=discord.Color.dark_gray(),
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, content=None, view=None
                )
            except Exception:
                pass
            await self._start_combat_for_group(
                interaction, ["страж", "страж"]
            )

    # ==================== 4. DEMON ====================

    async def _demon_fight(self, interaction):
        await self._close(interaction, "🦅 Вы вступаете в бой с Демоном!")
        await self._start_combat_for_group(interaction, ["демон"])

    async def _demon_hide(self, interaction):
        await self._quick_ack(interaction)

        roll = random.randint(1, 100)
        if roll <= 75:
            await self._finish_and_answer(
                interaction,
                "🏚️ Вы укрылись в ближайшем здании. Демон улетел."
            )
            return

        embed = discord.Embed(
            description="🦅 Демон заметил вас! Бой!",
            color=discord.Color.dark_gray(),
        )
        try:
            await interaction.edit_original_response(
                embed=embed, content=None, view=None
            )
        except Exception:
            pass
        await self._start_combat_for_group(interaction, ["демон"])

    # ==================== 5. ENCIRCLEMENT (solo only) ====================

    async def _encircle_fight(self, interaction):
        await self._close(
            interaction, "🐕 Вы приняли бой со стаей Стражей!"
        )
        await self._start_combat_for_group(
            interaction, ["страж", "страж", "страж"]
        )

    async def _encircle_grenade(self, interaction):
        await self._quick_ack(interaction)

        leader = self.leader
        grenades = (
            leader.get_all_grenades()
            if hasattr(leader, "get_all_grenades") else {}
        )
        if not grenades:
            embed = discord.Embed(
                description="💣 У вас нет гранат! Придётся драться.",
                color=discord.Color.dark_gray(),
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, content=None, view=None
                )
            except Exception:
                pass
            await self._start_combat_for_group(
                interaction, ["страж", "страж", "страж"]
            )
            return

        gid = next(iter(grenades))
        if hasattr(leader, "consume_grenade"):
            leader.consume_grenade(gid)
            await save_player(leader)

        roll = random.randint(1, 100)
        if roll <= 50:
            await self._finish_and_answer(
                interaction,
                "💣 Граната отвлекла стаю! Вы проскочили."
            )
        else:
            embed = discord.Embed(
                description="💣 Граната не помогла! Бой!",
                color=discord.Color.dark_gray(),
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, content=None, view=None
                )
            except Exception:
                pass
            await self._start_combat_for_group(
                interaction, ["страж", "страж", "страж"]
            )

    # ==================== 6. LURED MERZLYAK (solo only) ====================

    async def _lured_fight(self, interaction):
        await self._close(interaction, "🐺 Вы приняли бой с Мерзляком!")
        await self._start_combat_for_group(interaction, ["мерзляк"])

    async def _lured_flee(self, interaction):
        await self._quick_ack(interaction)

        roll = random.randint(1, 100)
        if roll <= 25:
            await self._finish_and_answer(
                interaction,
                "🏃 Вам удалось убежать!"
            )
            return

        await self._apply_damage_to_all(10.0)

        embed = discord.Embed(
            description=(
                "🐺 **Вы не успели убежать!**\n"
                "💥 Урон: **10** по всему телу\n"
                "⚔️ Бой!"
            ),
            color=discord.Color.dark_gray(),
        )
        try:
            await interaction.edit_original_response(
                embed=embed, content=None, view=None
            )
        except Exception:
            pass

        await self._start_combat_for_group(interaction, ["мерзляк"])

    # ==================== 7. RAIDER (group only) ====================

    async def _raider_fight(self, interaction):
        await self._close(interaction, "☠️ Вы приняли бой с Рейдером!")
        await self._start_combat_for_group(
            interaction, ["рейдер", "носач_рафик", "носач_жуля"]
        )

    async def _raider_talk(self, interaction):
        # Сначала отвечаем
        if not interaction.response.is_done():
            try:
                await interaction.response.defer()
            except Exception:
                pass

        leader_level = getattr(self.leader, "level", 1)
        chance = min(95, 5 + leader_level * 5)
        roll = random.randint(1, 100)

        if roll > chance:
            embed = discord.Embed(
                description=(
                    f"🗣️ Рейдер не стал слушать. Бой!\n"
                    f"🎲 Шанс был {chance}%, выпало {roll}."
                ),
                color=discord.Color.dark_gray(),
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, content=None, view=None
                )
            except Exception:
                pass
            await self._start_combat_for_group(
                interaction, ["рейдер", "носач_рафик", "носач_жуля"]
            )
            return

        from .raider_dialog import RaiderDialogView
        view = RaiderDialogView(
            interaction=interaction,
            leader=self.leader,
            group_players=self.group_players,
            success_chance=chance,
            parent_future=self.result_future,
        )
        await view.start()

    async def _raider_noise(self, interaction):
        await self._quick_ack(interaction)

        roll = random.randint(1, 100)
        if roll <= 25:
            embed = discord.Embed(
                description=(
                    "🔊 Вы нашумели! Мерзляки прибежали на шум, "
                    "Рейдер отступил.\n⚔️ Бой против стаи Мерзляков!"
                ),
                color=discord.Color.dark_gray(),
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, content=None, view=None
                )
            except Exception:
                pass
            await self._start_combat_for_group(
                interaction, ["мерзляк", "мерзляк_охотник", "мерзляк"]
            )
        else:
            embed = discord.Embed(
                description="🔊 Рейдер не испугался! Бой!",
                color=discord.Color.dark_gray(),
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, content=None, view=None
                )
            except Exception:
                pass
            await self._start_combat_for_group(
                interaction, ["рейдер", "носач_рафик", "носач_жуля"]
            )

    # ==================== 8. ARTIFACT UNDER BRIDGE ====================

    async def _artifact_bridge_skip(self, interaction):
        await self._close(
            interaction,
            "💠 Вы прошли мимо. Свечение осталось позади."
        )

    async def _artifact_bridge_near(self, interaction):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer()
            except Exception:
                pass

        embed = discord.Embed(
            title="💠 Свечение под мостом",
            description=(
                "Вы подходите ближе и замечаете хаотичную фигурку, "
                "висящую в воздухе."
            ),
            color=discord.Color.teal(),
        )
        view = _ArtifactBridgeStep2(self)
        try:
            await interaction.edit_original_response(
                embed=embed, view=view
            )
        except Exception as e:
            logger.error(f"[SURFACE] artifact bridge step2: {e}")
            self.finish(combat_started=False)

    async def _artifact_bridge_reach(self, interaction):
        await self._quick_ack(interaction)

        await self._add_chem_to_all(20.0)
        for p in self.group_players:
            hlam = p.inventory.get("хлам", []) or []
            hlam.append("артефакт_ледышка")
            p.inventory["хлам"] = hlam
            await save_player(p)

        await self._finish_and_answer(
            interaction,
            "💠 Вы дотянулись до артефакта **«Ледышка»**!\n"
            "☣️ Хим. заражение: **+20**\n"
            "🎁 Артефакт добавлен в хлам."
        )

    async def _artifact_bridge_leave(self, interaction):
        await self._close(
            interaction,
            "💠 Вы решили не рисковать. Артефакт остался висеть."
        )

    # ==================== 9. ARTIFACT IN LOBBY ====================

    async def _artifact_lobby_skip(self, interaction):
        await self._close(
            interaction,
            "💎 Вы ушли. Скрежет остался позади."
        )

    async def _artifact_lobby_listen(self, interaction):
        if not interaction.response.is_done():
            try:
                await interaction.response.defer()
            except Exception:
                pass

        embed = discord.Embed(
            title="💎 Скрежет в вестибюле",
            description=(
                "Возможно, там может быть артефакт... "
                "(подумали Вы про себя)"
            ),
            color=discord.Color.teal(),
        )
        view = _ArtifactLobbyStep2(self)
        try:
            await interaction.edit_original_response(
                embed=embed, view=view
            )
        except Exception as e:
            logger.error(f"[SURFACE] artifact lobby step2: {e}")
            self.finish(combat_started=False)

    async def _artifact_lobby_look(self, interaction):
        await self._quick_ack(interaction)

        roll = random.randint(1, 100)
        if roll <= 75:
            await self._add_chem_to_all(20.0)
            for p in self.group_players:
                hlam = p.inventory.get("хлам", []) or []
                hlam.append("артефакт_скрежет")
                p.inventory["хлам"] = hlam
                await save_player(p)
            await self._finish_and_answer(
                interaction,
                "💎 Вы нашли артефакт **«Скрежет»**!\n"
                "☣️ Хим. заражение: **+20**\n"
                "🎁 Артефакт добавлен в хлам."
            )
            return

        embed = discord.Embed(
            description="💀 В кабинке оказался **одинокий Мерзляк**! Бой!",
            color=discord.Color.dark_gray(),
        )
        try:
            await interaction.edit_original_response(
                embed=embed, content=None, view=None
            )
        except Exception:
            pass
        await self._start_combat_for_group(interaction, ["мерзляк"])

    async def _artifact_lobby_leave2(self, interaction):
        await self._close(
            interaction,
            "💎 Вы решили не рисковать. Ушли."
        )


# ==================== SUB-VIEWS ====================

class _ArtifactBridgeStep2(discord.ui.View):
    def __init__(self, parent: SurfaceEventView):
        super().__init__(timeout=120)
        self.parent = parent

    @discord.ui.button(label="Уйти", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction,
                    button: discord.ui.Button):
        if interaction.user.id != self.parent.leader.user_id:
            await interaction.response.send_message(
                "❌ Решение принимает лидер!", ephemeral=True
            )
            return
        await self.parent._artifact_bridge_leave(interaction)

    @discord.ui.button(label="Дотянуться рукой",
                       style=discord.ButtonStyle.primary)
    async def reach(self, interaction: discord.Interaction,
                    button: discord.ui.Button):
        if interaction.user.id != self.parent.leader.user_id:
            await interaction.response.send_message(
                "❌ Решение принимает лидер!", ephemeral=True
            )
            return
        await self.parent._artifact_bridge_reach(interaction)


class _ArtifactLobbyStep2(discord.ui.View):
    def __init__(self, parent: SurfaceEventView):
        super().__init__(timeout=120)
        self.parent = parent

    @discord.ui.button(label="Заглянуть в кабинку",
                       style=discord.ButtonStyle.primary)
    async def look(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        if interaction.user.id != self.parent.leader.user_id:
            await interaction.response.send_message(
                "❌ Решение принимает лидер!", ephemeral=True
            )
            return
        await self.parent._artifact_lobby_look(interaction)

    @discord.ui.button(label="Уйти", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction,
                    button: discord.ui.Button):
        if interaction.user.id != self.parent.leader.user_id:
            await interaction.response.send_message(
                "❌ Решение принимает лидер!", ephemeral=True
            )
            return
        await self.parent._artifact_lobby_leave2(interaction)