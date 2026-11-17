# -*- coding: utf-8 -*-
# func/commands.py - Все слеш-команды (Билд 0.4.8.3)
#
# ИСТОРИЯ:
#   0.4.8.3 — Стабильная версия (убран defer из /menu).

import discord
from discord.ext import commands
from discord import app_commands
import random
import traceback
import asyncio
import aiohttp
from .game_manager import game_manager
from .map_data import MAP_DATA, LINES, LINE_ICONS
from config.map_config import WEAPONS, ITEMS, BALANCE
from .views import CreateCharacterModal, MainMenu
from database.db import save_player, init_db
from utils.logger import get_logger, log_error
from .global_events import (
    current_event, get_active_effects, get_event_color,
    get_event_icon, GLOBAL_EVENTS_ENABLED
)
from .melee_system import get_melee_weapon

try:
    from utils.calculations import calculate_xp_to_level, get_heal_amount
except ImportError as e:
    log_error(e, "Импорт calculations")
    def calculate_xp_to_level(level):
        return 100 + (level - 1) * 50

    def get_heal_amount():
        return 5.0

logger = get_logger()

# ==================== КЛЮЧИ ДОСТУПА: АДМИН-ПАРОЛЬ (0.4.7.1) ====================

ADMIN_KEY_PASSWORD = "2044metro_dev"


class AdminKeyPasswordModal(discord.ui.Modal, title="🔐 Админ-пароль"):
    """0.4.7.1: запрос пароля для генерации ключа доступа."""

    password = discord.ui.TextInput(
        label="Пароль администратора",
        placeholder="Введите пароль...",
        min_length=1,
        max_length=64,
        required=True,
        style=discord.TextStyle.short,
    )

    def __init__(self, key_type: str):
        super().__init__()
        self.key_type = key_type

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.password.value.strip() != ADMIN_KEY_PASSWORD:
                logger.warning(
                    f"[KEY] Неверный админ-пароль от {interaction.user.id} "
                    f"({interaction.user.name})"
                )
                try:
                    await interaction.response.send_message(
                        "❌ Неверный пароль!", ephemeral=True
                    )
                except:
                    pass
                return

            from database.db import create_access_key
            key = await create_access_key(self.key_type)

            type_names = {
                "permanent": "Постоянный",
                "1_day": "На 1 день",
                "7_days": "На 7 дней",
            }

            embed = discord.Embed(
                title="🔑 Ключ доступа создан",
                description=(
                    f"**Тип:** {type_names.get(self.key_type, self.key_type)}\n"
                    f"**Ключ:** `{key}`\n\n"
                    f"💡 Передайте игроку. Он вводит его через `/start`."
                ),
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            logger.info(
                f"[KEY] {interaction.user.id} создал ключ {key} ({self.key_type})"
            )

        except Exception as e:
            logger.error(f"[KEY] Ошибка в AdminKeyPasswordModal: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    f"❌ Ошибка: {str(e)}", ephemeral=True
                )
            except:
                pass


def setup_commands(bot: commands.Bot, gm):
    global game_manager
    game_manager = gm
    logger.info("Настройка команд...")

    async def _safe_send(interaction: discord.Interaction, **kwargs):
        """Безопасная отправка ответа."""
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(**kwargs)
                return True
        except discord.errors.NotFound:
            logger.warning(f"⚠️ Interaction истёк для {interaction.user.id} (NotFound)")
            return False
        except discord.errors.InteractionResponded:
            pass
        except Exception as e:
            logger.error(f"❌ Ошибка response.send_message: {e}")

        try:
            await interaction.followup.send(**kwargs)
            return True
        except discord.errors.NotFound:
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка followup.send: {e}")
            return False

    # ==================== /start ====================

    @bot.tree.command(name="start", description="Создать персонажа")
    async def start_game(interaction: discord.Interaction):
        logger.info(f"Команда /start от {interaction.user.id}")
        try:
            user = interaction.user
            if game_manager.get_player(user.id):
                await _safe_send(
                    interaction,
                    content="❌ У вас уже есть персонаж! Используйте /menu",
                    ephemeral=True
                )
                return

            from database.db import check_player_access
            has_access, reason = await check_player_access(user.id)

            if not has_access:
                from .views.modal import AccessKeyModal
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_modal(AccessKeyModal())
                    return
                except discord.errors.NotFound:
                    logger.warning(f"⚠️ /start: interaction истёк у {user.id}")
                    return

            from .views.modal import CreateCharacterModal
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_modal(CreateCharacterModal())
                    return
                except (ConnectionResetError, aiohttp.client_exceptions.ClientOSError, OSError) as e:
                    logger.warning(f"Попытка {attempt + 1}/{max_retries} отправки модалки: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                    else:
                        raise
                except discord.errors.NotFound:
                    logger.warning(f"⚠️ /start: interaction истёк у {user.id}")
                    return

        except Exception as e:
            log_error(e, f"start_game для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /menu ====================

    @bot.tree.command(name="menu", description="Открыть главное меню")
    async def cmd_menu(interaction: discord.Interaction):
        logger.info(f"Команда /menu от {interaction.user.id}")
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(
                    interaction,
                    content="❌ Создайте персонажа командой /start"
                )
                return

            from .combat.manager import combat_manager
            from .combat.pvp_manager import pvp_manager
            if combat_manager.get_combat(interaction.user.id) or pvp_manager.is_user_in_combat(interaction.user.id):
                await _safe_send(
                    interaction,
                    content="⚔️ Вы в бою! Меню недоступно до конца боя.",
                    ephemeral=True,
                )
                return

            station_data = MAP_DATA["станции"].get(player.location)
            if not station_data:
                await _safe_send(
                    interaction,
                    content="❌ Ошибка: ваша локация не найдена на карте.",
                    ephemeral=True
                )
                return

            if getattr(player, 'is_sleeping', False):
                from .views.social.sleep_view import SleepingMenuView, build_sleeping_embed
                sleep_embed = build_sleeping_embed(player)
                await _safe_send(
                    interaction,
                    embed=sleep_embed,
                    view=SleepingMenuView(player.user_id),
                )
                return

            total_hp = player.get_total_health()
            max_hp = player.get_max_total_health()

            embed = discord.Embed(
                title="🎮 Меню 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
                description=f"Добро пожаловать, **{player.name}**!\nУровень: **{player.level}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
            embed.add_field(name="📍 Локация", value=station_data["name"], inline=True)
            embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)

            try:
                from .factions import get_faction_name, get_faction_emoji, get_player_loyalty_level
                _fid = player.get_faction()
                _fname = get_faction_name(_fid)
                _femoji = get_faction_emoji(_fid)
                _fline = f"{_femoji} {_fname}"
                if _fid != "loners":
                    _lvl = get_player_loyalty_level(player, _fid)
                    _fline += f" (лояльность ур. {_lvl}/5)"
                embed.add_field(name="🏴 Фракция", value=_fline, inline=False)
            except Exception as e:
                logger.error(f"[MENU] faction: {e}")

            if getattr(player, 'radiation', 0) > 0 or getattr(player, 'chemical', 0) > 0:
                embed.add_field(
                    name="☣️ Заражение",
                    value=f"☢️ {player.radiation:.0f} | ☣️ {player.chemical:.0f}",
                    inline=True
                )

            melee_data = get_melee_weapon(player.melee_weapon)
            if melee_data:
                melee_name = melee_data.get('name', 'Кулаки')
                melee_emoji = melee_data.get('emoji', '👊')
                embed.add_field(name="🗡️ Ближний бой", value=f"{melee_emoji} {melee_name}", inline=True)

            from .social.brigade_manager import brigade_manager
            brigade = brigade_manager.get_user_brigade(player.user_id)
            if brigade:
                role = "👑" if brigade.is_leader(player.user_id) else "👤"
                state = "🚶" if brigade.is_active() else "🔀"
                embed.add_field(
                    name="🤝 Бригада",
                    value=f"{state} {role} **{brigade.name}** ({brigade.member_count()}/3)",
                    inline=False,
                )

            view = MainMenu(player)  # <--- ПЕРЕДАЕМ ИГРОКА
            await _safe_send(interaction, embed=embed, view=view)

        except KeyError as e:
            log_error(e, f"cmd_menu KeyError для {interaction.user.id}")
            await _safe_send(
                interaction,
                content=f"❌ Ошибка данных: ключ {str(e)} не найден.",
                ephemeral=True
            )
        except Exception as e:
            log_error(e, f"cmd_menu для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /map ====================

    @bot.tree.command(name="map", description="Показать карту метро")
    async def cmd_show_map(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)

            try:
                await interaction.response.defer()
            except discord.errors.NotFound:
                return
            except discord.errors.InteractionResponded:
                pass

            from .views.map_render import MapPaginationView, build_overview_embed

            view = MapPaginationView()
            embed = build_overview_embed(player)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            log_error(e, f"cmd_show_map для {interaction.user.id}")
            try:
                await interaction.followup.send(
                    f"❌ Ошибка: {e}", ephemeral=True
                )
            except Exception:
                pass

    # ==================== /status ====================

    @bot.tree.command(name="status", description="Показать статус персонажа")
    async def cmd_status(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(interaction, content="❌ Создайте персонажа командой /start")
                return

            status = player.get_status()

            embed = discord.Embed(title=f"📊 Статус {status['имя']}", color=discord.Color.green())

            total_health = player.get_total_health()
            max_health = player.get_max_total_health()

            embed.add_field(name="❤️ Части тела", value=player.get_body_parts_status(), inline=False)
            embed.add_field(name="📊 Общее здоровье", value=f"{total_health:.1f}/{max_health:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
            embed.add_field(name="🍖 Еда", value=len(player.food_inventory), inline=True)
            embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)
            embed.add_field(name="📍 Локация", value=status['локация'], inline=True)
            embed.add_field(name="🎯 Меткость", value=f"{player.skills.get('меткость', 0)}/10", inline=True)
            embed.add_field(name="💪 Сила", value=f"{player.skills.get('сила', 0)}/10", inline=True)
            embed.add_field(name="🛡️ Стойкость", value=f"{player.skills.get('стойкость', 0)}/10", inline=True)
            embed.add_field(name="❤️ Здоровье", value=f"{player.skills.get('здоровье', 0)}/10", inline=True)
            embed.add_field(name="🔧 Инженерия", value=f"{player.skills.get('инженерия', 0)}/10", inline=True)
            embed.add_field(name="🔫 Оружие", value=status['оружие'], inline=True)

            try:
                from .factions import get_faction_name, get_faction_emoji, get_player_loyalty_level
                _fid = player.get_faction()
                _fname = get_faction_name(_fid)
                _femoji = get_faction_emoji(_fid)
                _fline = f"{_femoji} {_fname}"
                if _fid != "loners":
                    _lvl = get_player_loyalty_level(player, _fid)
                    _fline += f" (ур. {_lvl}/5)"
                embed.add_field(name="🏴 Фракция", value=_fline, inline=True)

                _tasks = player.get_active_tasks() if hasattr(player, 'get_active_tasks') else []
                if _tasks:
                    _active = sum(1 for t in _tasks if not t.get("completed"))
                    embed.add_field(name="📋 Задания", value=f"Активных: **{_active}**", inline=True)
            except Exception as e:
                logger.error(f"[STATUS] faction: {e}")

            from .disease_system import ensure_disease_fields, get_disease_data
            ensure_disease_fields(player)

            embed.add_field(name="☢️ Радиация", value=f"{player.radiation:.0f}/100", inline=True)
            embed.add_field(name="☣️ Химия", value=f"{player.chemical:.0f}/100", inline=True)

            if player.diseases:
                disease_names = []
                for d_id in player.diseases:
                    d = get_disease_data(d_id)
                    disease_names.append(f"{d.get('emoji', '💀')} {d.get('name', d_id)}")
                embed.add_field(name="💀 Болезни", value="\n".join(disease_names), inline=False)
            else:
                embed.add_field(name="💀 Болезни", value="✅ Нет", inline=True)

            from .armor_system import get_armor_item
            armor_name = "❌"
            if player.armor:
                a = get_armor_item(player.armor)
                armor_name = f"{a.get('emoji', '')} {a.get('name', '')}"
            helmet_name = "❌"
            if player.helmet:
                h = get_armor_item(player.helmet)
                helmet_name = f"{h.get('emoji', '')} {h.get('name', '')}"

            embed.add_field(name="🧥 Броня", value=armor_name, inline=True)
            embed.add_field(name="⛑️ Шлем", value=helmet_name, inline=True)

            melee_data = get_melee_weapon(player.melee_weapon)
            if melee_data:
                melee_name = melee_data.get('name', 'Кулаки')
                melee_emoji = melee_data.get('emoji', '👊')
                melee_durability = player.get_melee_weapon_durability_percent()
                embed.add_field(
                    name="🗡️ Ближний бой",
                    value=f"{melee_emoji} {melee_name} ({melee_durability}%)",
                    inline=True
                )

            embed.add_field(
                name="🎒 Противогаз",
                value=f"{status['противогаз']} (прочность: {status['прочность_маски']})",
                inline=True
            )
            embed.add_field(name="🧪 Фильтры", value=status['фильтры'], inline=True)
            embed.add_field(
                name="💀 Дебаффы",
                value=", ".join(status['дебаффы']) if status['дебаффы'] else "Нет",
                inline=True
            )

            if getattr(player, 'is_sleeping', False):
                embed.add_field(name="😴 Сон", value="**Спит**", inline=False)

            await _safe_send(interaction, embed=embed)
        except Exception as e:
            log_error(e, f"cmd_status для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /move ====================

    @bot.tree.command(name="move", description="Переместиться на станцию")
    @app_commands.describe(station="Название станции")
    async def cmd_move(interaction: discord.Interaction, station: str):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(interaction, content="❌ Создайте персонажа командой /start")
                return
            if not player.is_alive:
                await _safe_send(interaction, content="💀 Вы мертвы! Используйте /revive")
                return

            if getattr(player, 'is_sleeping', False):
                await _safe_send(
                    interaction,
                    content="😴 Вы спите. Проснитесь через /menu.",
                    ephemeral=True,
                )
                return

            from .combat.manager import combat_manager
            from .combat.pvp_manager import pvp_manager
            if combat_manager.get_combat(interaction.user.id) or pvp_manager.is_user_in_combat(interaction.user.id):
                await _safe_send(interaction, content="⚔️ Вы в бою! Завершите бой перед перемещением.", ephemeral=True)
                return

            station = station.lower().replace(" ", "_")
            if station not in MAP_DATA["станции"]:
                await _safe_send(interaction, content="❌ Станция не найдена!")
                return

            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except discord.errors.NotFound:
                logger.warning(f"⚠️ /move: interaction истёк у {interaction.user.id}")
                return

            result = await game_manager.move_player(interaction.user.id, station, interaction)

            if "Бой начался" in result or "БОЙ!" in result or "боя" in result.lower():
                embed = discord.Embed(title="⚔️ БОЙ", description=result, color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return

            embed = discord.Embed(title="🚇 Перемещение", description=result, color=discord.Color.blue())

            from .views.move import MoveResultView
            view = MoveResultView(player)
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            log_error(e, f"cmd_move для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /eat ====================

    @bot.tree.command(name="eat", description="Съесть еду для восстановления выносливости")
    async def cmd_eat(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(interaction, content="❌ Создайте персонажа командой /start")
                return
            if not player.is_alive:
                await _safe_send(interaction, content="💀 Вы мертвы!")
                return
            if not player.food_inventory:
                await _safe_send(interaction, content="❌ Нет еды!")
                return
            if player.stamina >= player.max_stamina:
                await _safe_send(interaction, content="🏃 Полная выносливость!")
                return

            from .food_system import eat_food
            food_id = player.food_inventory[0]
            result = await eat_food(player, food_id)
            await save_player(player)

            total_health = player.get_total_health()
            max_health = player.get_max_total_health()

            embed = discord.Embed(title="🍽️ Результат", description=result, color=discord.Color.green())
            embed.add_field(name="❤️ Здоровье", value=f"{total_health:.1f}/{max_health:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
            await _safe_send(interaction, embed=embed)
        except Exception as e:
            log_error(e, f"cmd_eat для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /fight ====================

    @bot.tree.command(name="fight", description="Вызвать игрока на PvP-бой")
    @app_commands.describe(target="Игрок, которого вы вызываете")
    async def cmd_fight(interaction: discord.Interaction, target: discord.Member):
        try:
            from .combat.pvp_manager import pvp_manager
            from .combat.manager import combat_manager
            from .views.combat_views.pvp_invite_view import PvPInviteView

            initiator = game_manager.get_player(interaction.user.id)
            target_player = game_manager.get_player(target.id)

            if not initiator or not target_player:
                await _safe_send(interaction, content="❌ Один из игроков не создан!", ephemeral=True)
                return
            if initiator.user_id == target_player.user_id:
                await _safe_send(interaction, content="❌ Нельзя вызвать самого себя!", ephemeral=True)
                return
            if not initiator.is_alive or not target_player.is_alive:
                await _safe_send(interaction, content="❌ Один из игроков мёртв!", ephemeral=True)
                return

            if getattr(initiator, 'is_sleeping', False):
                await _safe_send(interaction, content="😴 Вы спите. Проснитесь через /menu.", ephemeral=True)
                return
            if getattr(target_player, 'is_sleeping', False):
                await _safe_send(interaction, content="😴 Цель спит — нельзя вызвать.", ephemeral=True)
                return

            if initiator.location != target_player.location:
                await _safe_send(interaction, content="❌ Вы должны быть на одной станции!", ephemeral=True)
                return

            station_data = MAP_DATA["станции"].get(initiator.location, {})
            is_dangerous = station_data.get("ruined", False) or station_data.get("danger", 0) >= 3
            if not is_dangerous:
                await _safe_send(
                    interaction,
                    content="❌ PvP-бой возможен только на опасной станции (ruined или danger ≥ 3)!",
                    ephemeral=True,
                )
                return

            if combat_manager.get_combat(initiator.user_id) or pvp_manager.is_user_in_combat(initiator.user_id):
                await _safe_send(interaction, content="❌ Вы уже в бою!", ephemeral=True)
                return
            if combat_manager.get_combat(target_player.user_id) or pvp_manager.is_user_in_combat(target_player.user_id):
                await _safe_send(interaction, content="❌ Цель уже в бою!", ephemeral=True)
                return

            from .social.brigade_manager import brigade_manager
            init_brigade = brigade_manager.get_user_brigade(initiator.user_id)
            if init_brigade and init_brigade.has_member(target_player.user_id):
                await _safe_send(
                    interaction,
                    content="❌ Нельзя вызвать на бой члена своей бригады!",
                    ephemeral=True,
                )
                return

            invite = pvp_manager.create_invite(
                initiator.user_id, target_player.user_id, interaction.channel.id
            )

            from .views.combat_views.pvp_start import _get_brigade_allies_for_pvp
            a_allies = _get_brigade_allies_for_pvp(initiator, initiator.location)
            b_allies = _get_brigade_allies_for_pvp(target_player, target_player.location)

            allies_line = ""
            if a_allies or b_allies:
                a_names = [a.name for a in a_allies]
                b_names = [b.name for b in b_allies]
                allies_line = (
                        f"\n\n🤝 **Бригады втягиваются в бой!**\n"
                        f"🅰️ {initiator.name}" + (f", {', '.join(a_names)}" if a_names else "") + "\n"
                                                                                                  f"🅱️ {target_player.name}" + (f", {', '.join(b_names)}" if b_names else "")
                )

            embed = discord.Embed(
                title="⚔️ Вызов на PvP-бой!",
                description=(
                    f"**{initiator.name}** вызывает **{target_player.name}** на смертный бой!\n\n"
                    f"📍 Станция: **{station_data.get('name', '—')}**\n"
                    f"⚠️ Победитель забирает ВСЁ снаряжение проигравшего.\n"
                    f"💀 Проигравший умирает и должен будет использовать /revive."
                    f"{allies_line}\n\n"
                    f"🎯 **{target_player.name}**, ваш ответ?"
                ),
                color=discord.Color.dark_red(),
            )
            embed.set_footer(text="⏱️ У вас 60 секунд на ответ")

            view = PvPInviteView(invite.invite_id, initiator.user_id, target_player.user_id)
            await _safe_send(interaction, embed=embed, view=view)

        except Exception as e:
            log_error(e, f"cmd_fight для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /heal ====================

    @bot.tree.command(name="heal", description="Использовать аптечку")
    async def cmd_heal(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(interaction, content="❌ Создайте персонажа командой /start")
                return
            if not player.is_alive:
                await _safe_send(interaction, content="💀 Вы мертвы! Используйте /revive")
                return

            total_health = player.get_total_health()
            max_health = player.get_max_total_health()

            if total_health >= max_health:
                await _safe_send(
                    interaction,
                    content=f"❤️ Полное здоровье ({total_health:.1f}/{max_health:.1f})!",
                    ephemeral=True
                )
                return

            from .pharmacy_system import use_medkit

            if player.inventory.get('мед_подсумок', 0) > 0:
                result = use_medkit(player, 'мед_подсумок')
            elif player.inventory.get('аптечка_аи2', 0) > 0:
                result = use_medkit(player, 'аптечка_аи2')
            else:
                await _safe_send(interaction, content="❌ Нет аптечек! Купите в Аптеке.", ephemeral=True)
                return

            await save_player(player)

            if not result.get('success'):
                await _safe_send(interaction, content=result.get('message', '❌ Ошибка'), ephemeral=True)
                return

            new_total = player.get_total_health()
            await _safe_send(
                interaction,
                content=f"{result.get('message', '')}\n"
                        f"❤️ Восстановлено: {new_total:.1f}/{max_health:.1f}\n"
                        f"📊 Части тела:\n{player.get_body_parts_status()}",
                ephemeral=True
            )
        except Exception as e:
            log_error(e, f"cmd_heal для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /revive ====================

    @bot.tree.command(name="revive", description="[ВНИМАНИЕ] Смерть = вайп персонажа. Команда удаляет персонажа.")
    async def cmd_revive(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(
                    interaction,
                    content="❌ У вас нет персонажа. Введите `/start`.",
                    ephemeral=True,
                )
                return

            if player.is_alive:
                await _safe_send(
                    interaction,
                    content="❌ Вы ещё живы. Команда нужна только для подтверждения удаления персонажа после смерти.",
                    ephemeral=True,
                )
                return

            result = await game_manager.revive_player(interaction.user.id)
            await _safe_send(interaction, content=result)
        except Exception as e:
            log_error(e, f"cmd_revive для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /leaderboard ====================

    @bot.tree.command(name="leaderboard", description="Таблица лидеров")
    async def cmd_leaderboard(interaction: discord.Interaction):
        try:
            if not game_manager.players:
                await _safe_send(interaction, content="❌ Нет игроков!")
                return

            alive_players = [p for p in game_manager.players.values() if p.is_alive]
            sorted_players = sorted(
                alive_players,
                key=lambda p: (p.level, p.get_total_health()),
                reverse=True
            )

            embed = discord.Embed(title="🏆 Таблица лидеров Метро", color=discord.Color.gold())
            for i, player in enumerate(sorted_players[:10], 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
                total_health = player.get_total_health()
                max_health = player.get_max_total_health()
                embed.add_field(
                    name=f"{medal} {player.name} (Ур. {player.level})",
                    value=f"❤️ {total_health:.1f}/{max_health:.1f} | "
                          f"🏃 {player.stamina:.1f} | "
                          f"📍 {MAP_DATA['станции'][player.location]['name']}",
                    inline=False
                )
            await _safe_send(interaction, embed=embed)
        except Exception as e:
            log_error(e, f"cmd_leaderboard для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /set_channel ====================

    @bot.tree.command(name="set_channel", description="Установить канал для ивентов")
    @app_commands.describe(channel="Канал для отправки ивентов")
    async def cmd_set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        try:
            if not interaction.user.guild_permissions.administrator:
                await _safe_send(interaction, content="❌ Только администраторы!", ephemeral=True)
                return
            game_manager.game_channel = channel.id
            await _safe_send(interaction, content=f"✅ Канал для ивентов: {channel.mention}")
        except Exception as e:
            log_error(e, f"cmd_set_channel для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /save ====================

    @bot.tree.command(name="save", description="Принудительно сохранить прогресс")
    async def cmd_save(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(interaction, content="❌ Создайте персонажа командой /start")
                return

            await save_player(player)

            total_health = player.get_total_health()
            max_health = player.get_max_total_health()

            melee_data = get_melee_weapon(player.melee_weapon)
            melee_name = melee_data.get('name', 'Кулаки') if melee_data else 'Кулаки'

            await _safe_send(
                interaction,
                content=f"✅ Прогресс сохранен!\n"
                        f"📊 {player.name} - Уровень {player.level}, ❤️ {total_health:.1f}/{max_health:.1f}, "
                        f"🍖 {len(player.food_inventory)} еды, 🗡️ {melee_name}",
                ephemeral=True
            )
        except Exception as e:
            log_error(e, f"cmd_save для {interaction.user.id}")
            await _safe_send(interaction, content=f"❌ Ошибка сохранения: {str(e)}", ephemeral=True)

    # ==================== /event ====================

    @bot.tree.command(name="event", description="Информация о текущем глобальном ивенте")
    async def cmd_event(interaction: discord.Interaction):
        try:
            if not GLOBAL_EVENTS_ENABLED:
                embed = discord.Embed(
                    title="🌍 Глобальные ивенты",
                    description="Глобальные ивенты отключены в конфигурации.",
                    color=discord.Color.orange()
                )
                await _safe_send(interaction, embed=embed, ephemeral=True)
                return

            if not current_event.active:
                embed = discord.Embed(
                    title="🌍 Глобальные ивенты",
                    description="В данный момент нет активных глобальных ивентов.",
                    color=discord.Color.green()
                )
                active_effects = get_active_effects(game_manager)
                if active_effects:
                    effect_names = {
                        "trade_discount": "🛒 Скидка 20%",
                        "mutant_wave": "💀 Мутанты опаснее",
                        "loot_boost": "📦 +50% опыта и лута",
                        "flood": "🌊 Переходы дороже",
                        "radiation_spike": "☢️ Радиация сильнее",
                        "power_outage": "⚡ Темнота",
                        "shop_sale": "🏪 Скидка 30%",
                        "x2_exp": "⭐ Двойной опыт",
                        "earthquake": "🌍 Переходы заблокированы",
                        "gas_leak": "☠️ Утечка газа",
                        "station_celebration": "🎉 Праздник",
                        "station_fire": "🔥 Пожар",
                        "stalker_workshop": "🔧 Мастерская",
                        "mutant_breach": "🧟 Прорыв"
                    }
                    effects_text = "\n".join([f"• {effect_names.get(e, e)}" for e in active_effects.keys()])
                    embed.add_field(name="💡 Активные эффекты", value=effects_text, inline=False)
                embed.set_footer(text="Следующий ивент скоро начнется")
                await _safe_send(interaction, embed=embed, ephemeral=True)
                return

            event = current_event.event
            color = get_event_color(event["type"])
            icon = get_event_icon(event["type"])

            embed = discord.Embed(
                title=f"{icon} Активный глобальный ивент",
                description=event["text"],
                color=color
            )
            embed.add_field(name="⏱️ Осталось", value=f"{current_event.time_remaining} минут", inline=True)
            embed.add_field(
                name="📊 Тип",
                value="✅ Бафф" if event["type"] == "buff"
                else "❌ Дебафф" if event["type"] == "debuff"
                else "ℹ️ Нейтральный",
                inline=True
            )
            embed.add_field(name="💡 Эффект", value=event.get("description", "Нет описания"), inline=False)

            await _safe_send(interaction, embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Ошибка в cmd_event: {e}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /admin_key ====================

    @bot.tree.command(name="admin_key", description="[АДМИН] Создать ключ доступа")
    @app_commands.describe(key_type="Тип ключа")
    @app_commands.choices(key_type=[
        app_commands.Choice(name="Постоянный", value="permanent"),
        app_commands.Choice(name="На 1 день", value="1_day"),
        app_commands.Choice(name="На 7 дней", value="7_days"),
    ])
    async def cmd_admin_key(interaction: discord.Interaction, key_type: app_commands.Choice[str]):
        try:
            if not interaction.user.guild_permissions.administrator:
                await _safe_send(interaction, content="❌ Только администраторы!", ephemeral=True)
                return

            try:
                if not interaction.response.is_done():
                    await interaction.response.send_modal(
                        AdminKeyPasswordModal(key_type.value)
                    )
                return
            except discord.errors.NotFound:
                logger.warning(f"⚠️ /admin_key: interaction истёк у {interaction.user.id}")
                return

        except Exception as e:
            logger.error(f"Ошибка в cmd_admin_key: {e}", exc_info=True)
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /sync ====================

    @bot.tree.command(name="sync", description="[АДМИН] Принудительно синхронизировать команды")
    @app_commands.default_permissions(administrator=True)
    async def cmd_sync(interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await _safe_send(interaction, content="❌ Только администраторы!", ephemeral=True)
                return

            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except discord.errors.NotFound:
                return

            await bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send("✅ Команды синхронизированы для этого сервера!", ephemeral=True)

        except Exception as e:
            logger.error(f"Ошибка в cmd_sync: {e}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /event_force ====================

    @bot.tree.command(name="event_force", description="[АДМИН] Принудительно запустить случайный ивент")
    @app_commands.default_permissions(administrator=True)
    async def cmd_event_force(interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await _safe_send(interaction, content="❌ Только администраторы!", ephemeral=True)
                return

            if not GLOBAL_EVENTS_ENABLED:
                await _safe_send(interaction, content="❌ Глобальные ивенты отключены!", ephemeral=True)
                return

            from .global_events import trigger_event
            await trigger_event(bot, game_manager)
            await _safe_send(interaction, content="✅ Глобальный ивент принудительно запущен!", ephemeral=True)

        except Exception as e:
            logger.error(f"Ошибка в cmd_event_force: {e}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    # ==================== /event_toggle ====================

    @bot.tree.command(name="event_toggle", description="[АДМИН] Включить/выключить глобальные ивенты")
    @app_commands.default_permissions(administrator=True)
    async def cmd_event_toggle(interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await _safe_send(interaction, content="❌ Только администраторы!", ephemeral=True)
                return

            from .global_events import GLOBAL_EVENTS_ENABLED as current_state

            embed = discord.Embed(
                title="⚙️ Управление глобальными ивентами",
                description=f"Глобальные ивенты сейчас **{'ВКЛЮЧЕНЫ' if current_state else 'ОТКЛЮЧЕНЫ'}**",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="⚠️ Важно",
                value="Для изменения состояния перезагрузите бота и измените GLOBAL_EVENTS_ENABLED в global_events.py",
                inline=False
            )
            await _safe_send(interaction, embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Ошибка в cmd_event_toggle: {e}")
            await _safe_send(interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True)

    logger.info("Все команды успешно зарегистрированы")

    # ==================== /faction ====================

    @bot.tree.command(name="faction", description="Меню фракций: отношения, лояльность, бонусы")
    async def cmd_faction(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(
                    interaction,
                    content="❌ Создайте персонажа командой /start",
                    ephemeral=True,
                )
                return

            from .views.faction_view import FactionsMenu, build_factions_embed

            embed = build_factions_embed(player)
            view = FactionsMenu(player)

            await _safe_send(interaction, embed=embed, view=view)
        except Exception as e:
            log_error(e, f"cmd_faction для {interaction.user.id}")
            await _safe_send(
                interaction,
                content=f"❌ Ошибка: {str(e)}",
                ephemeral=True,
            )

    @bot.tree.command(name="faction_info", description="Подробная информация о фракции")
    @app_commands.describe(faction_id="ID фракции: loners, bandits, antiquars, gess, yasenevo, gutagi")
    async def cmd_faction_info(interaction: discord.Interaction, faction_id: str):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(
                    interaction,
                    content="❌ Создайте персонажа командой /start",
                    ephemeral=True,
                )
                return

            from .views.faction_view import FactionDetailView, build_faction_detail_embed
            from .factions import get_faction_data

            faction_id = faction_id.lower().strip()
            if not get_faction_data(faction_id):
                await _safe_send(
                    interaction,
                    content=f"❌ Фракция `{faction_id}` не найдена.",
                    ephemeral=True,
                )
                return

            embed = build_faction_detail_embed(player, faction_id)
            view = FactionDetailView(player, faction_id)
            await _safe_send(interaction, embed=embed, view=view)
        except Exception as e:
            log_error(e, f"cmd_faction_info для {interaction.user.id}")
            await _safe_send(
                interaction,
                content=f"❌ Ошибка: {str(e)}",
                ephemeral=True,
            )