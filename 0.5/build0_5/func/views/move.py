# -*- coding: utf-8 -*-
# func/views/move.py - Меню перемещения (0.4.8.7.5)
#
# ИСТОРИЯ:
#   0.4.8.3 — surface_lock
#   0.4.8.6 — Гутаги: кнопка активна
#   0.4.8.7 — иконка Гутагов
#   0.4.8.7.3 — ФИКС: PartialEmoji вместо <:gutag:...>
#   0.4.8.7.4 — ФИКС: не блокировать Гутагов в move.py, чтобы запустился охранник
#   0.4.8.7.5 — ИКОНКИ: emoji станции = цвет опасности (🟢🟡🟠🔴💀)

import discord
import traceback

from .helpers import game_manager, MAP_DATA
from ..station_utils import is_blocked_station
from utils.logger import get_logger

logger = get_logger()

GUTAGI_STATIONS = {
    "павелецкая_кольцо", "добрынинская", "октябрьская_кольцо",
    "серпуховская", "тульская",
}

# Эмодзи Гутагов (логотип)
GUTAGI_EMOJI = discord.PartialEmoji(name="gutag", id=1564608459939389500)

# 0.4.8.7.5: цвет опасности
DANGER_EMOJI = {
    0: "🟢",
    1: "🟡",
    2: "🟠",
    3: "🔴",
    4: "💀",
    5: "☠️",
}


class MoveMenu(discord.ui.View):
    def __init__(self, connections: list, player):
        super().__init__(timeout=60)
        self.player = player

        hlam = player.inventory.get("хлам", []) or []
        has_perm_pass = "постоянный_пропуск" in hlam
        has_temp_pass = "временный_пропуск" in hlam

        for station in connections:
            station_data = MAP_DATA["станции"][station]
            is_blocked = is_blocked_station(station)

            is_surface = (
                    station_data.get("surface_lock", False)
                    or station_data.get("type") == "на_поверхности"
            )
            if is_surface and getattr(self.player, 'surface_unlocked', False):
                is_blocked = False

            # Для Гутагов кнопка всегда активна, чтобы move_player вызвал охранника
            if station in GUTAGI_STATIONS:
                is_blocked = False

            label = f"{station_data['name']}"
            if is_blocked:
                label = f"🚫 {station_data['name']}"
            label = label[:80]

            # 0.4.8.7.5: emoji = цвет опасности
            danger = station_data.get("danger", 0)
            emoji = DANGER_EMOJI.get(danger, "⬤")

            # Гутаги с пропуском — показываем логотип
            if station in GUTAGI_STATIONS and (has_perm_pass or has_temp_pass):
                emoji = GUTAGI_EMOJI

            button = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=(
                    discord.ButtonStyle.danger
                    if is_blocked
                    else discord.ButtonStyle.primary
                ),
                custom_id=f"move_{station}",
                disabled=is_blocked,
            )
            button.callback = self.create_callback(station)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id="move_back",
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, destination: str):
        async def callback(interaction: discord.Interaction):
            logger.info(
                f"[MOVE] Нажата станция '{destination}' от {interaction.user.id}"
            )

            try:
                # 0.4.8.7.4: Пропускаем заблокированные станции, НО НЕ Гутагов
                # (для Гутагов охранник обрабатывается в move_player)
                if is_blocked_station(destination) and destination not in GUTAGI_STATIONS:
                    station_data = MAP_DATA['станции'][destination]
                    is_surface = (
                            station_data.get("surface_lock", False)
                            or station_data.get("type") == "на_поверхности"
                    )
                    if not (is_surface and getattr(self.player, 'surface_unlocked', False)):
                        await interaction.response.send_message(
                            f"🚫 Станция **{MAP_DATA['станции'][destination]['name']}** "
                            f"заблокирована. Проход закрыт.",
                            ephemeral=True,
                        )
                        return

                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer(thinking=True)
                except discord.errors.NotFound:
                    logger.warning("[MOVE] interaction истёк (NotFound)")
                    return

                player = game_manager.get_player(interaction.user.id)
                if not player:
                    await interaction.followup.send(
                        "❌ Персонаж не найден!", ephemeral=True
                    )
                    return

                logger.info(
                    f"[MOVE] Вызываю move_player для {player.name} → {destination}"
                )
                try:
                    result = await game_manager.move_player(
                        interaction.user.id, destination, interaction
                    )
                except Exception as e:
                    logger.error(f"[MOVE] ОШИБКА в move_player: {e}")
                    logger.error(traceback.format_exc())
                    try:
                        await interaction.followup.send(
                            f"❌ Ошибка перемещения: {e}", ephemeral=True
                        )
                    except Exception:
                        pass
                    return

                if not result:
                    # move_player вернул пустую строку — например, охранник
                    # уже отправил своё сообщение
                    return

                logger.info(f"[MOVE] move_player вернул: {result[:80]}...")

                try:
                    await interaction.message.delete()
                except Exception as e:
                    logger.debug(f"[MOVE] Не удалось удалить сообщение: {e}")

                lower = result.lower()
                if (
                        "бой начался" in lower
                        or "бой" in lower
                        or "⚔️" in result
                        or "Бандиты!" in result
                        or "Мутант!" in result
                ):
                    embed = discord.Embed(
                        title="⚔️ БОЙ",
                        description=result,
                        color=discord.Color.red(),
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

                embed = discord.Embed(
                    title="🚇 Перемещение",
                    description=result,
                    color=discord.Color.blue(),
                )
                view = MoveResultView(player)
                await interaction.followup.send(
                    embed=embed, view=view, ephemeral=True
                )

            except Exception as e:
                logger.error(f"[MOVE] НЕИЗВЕСТНАЯ ОШИБКА: {e}")
                logger.error(traceback.format_exc())
                try:
                    await interaction.followup.send(
                        f"❌ Ошибка: {e}", ephemeral=True
                    )
                except Exception:
                    pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        from .main_menu import MainMenu

        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message(
                    "❌ Ошибка!", ephemeral=True
                )
                return

            station_data = MAP_DATA["станции"][player.location]
            total_hp = player.get_total_health()
            max_hp = player.get_max_total_health()

            embed = discord.Embed(
                title="🎮 Меню 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
                description=f"Добро пожаловать, **{player.name}**!\nУровень: **{player.level}**",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}",
                inline=True,
            )
            embed.add_field(
                name="🏃 Выносливость",
                value=f"{player.stamina:.1f}/{player.max_stamina}",
                inline=True,
            )
            embed.add_field(
                name="📍 Локация", value=station_data["name"], inline=True
            )
            embed.add_field(
                name="💰 Никели",
                value=player.inventory.get('никели', 0),
                inline=True,
            )

            view = MainMenu(player)
            try:
                await interaction.response.edit_message(
                    embed=embed, view=view
                )
            except discord.errors.InteractionResponded:
                await interaction.followup.send(
                    embed=embed, view=view, ephemeral=True
                )

        except Exception as e:
            logger.error(f"[MOVE] Ошибка в back_callback: {e}")
            logger.error(traceback.format_exc())


class MoveResultView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=180)
        self.player = player

    @discord.ui.button(
        label="🚇 Идти дальше", style=discord.ButtonStyle.primary
    )
    async def continue_move(
            self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваш персонаж!", ephemeral=True
            )
            return

        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message(
                    "❌ Персонаж не найден!", ephemeral=True
                )
                return

            if not player.is_alive:
                await interaction.response.send_message(
                    "💀 Вы мертвы!", ephemeral=True
                )
                return

            current = player.location
            connections = MAP_DATA["станции"][current]["connections"]

            if not connections:
                await interaction.response.send_message(
                    "🚇 Конечная станция!", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🗺️ Куда идем?",
                description=(
                    f"Текущая: **{MAP_DATA['станции'][current]['name']}**\n"
                    f"🏃 Выносливость: "
                    f"{player.stamina:.1f}/{player.max_stamina}"
                ),
                color=discord.Color.blue(),
            )

            view = MoveMenu(connections, player)
            try:
                await interaction.response.edit_message(
                    embed=embed, view=view
                )
            except discord.errors.InteractionResponded:
                await interaction.followup.send(
                    embed=embed, view=view, ephemeral=True
                )

        except Exception as e:
            logger.error(f"[MOVE] Ошибка в continue_move: {e}")
            logger.error(traceback.format_exc())
            try:
                await interaction.response.send_message(
                    f"❌ Ошибка: {e}", ephemeral=True
                )
            except Exception:
                pass

    @discord.ui.button(
        label="🎮 Меню", style=discord.ButtonStyle.success
    )
    async def back_to_menu(
            self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваш персонаж!", ephemeral=True
            )
            return

        from .main_menu import MainMenu

        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message(
                    "❌ Персонаж не найден!", ephemeral=True
                )
                return

            station_data = MAP_DATA["станции"][player.location]
            total_hp = player.get_total_health()
            max_hp = player.get_max_total_health()

            embed = discord.Embed(
                title="🎮 Меню 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
                description=f"Добро пожаловать, **{player.name}**!\nУровень: **{player.level}**",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}",
                inline=True,
            )
            embed.add_field(
                name="🏃 Выносливость",
                value=f"{player.stamina:.1f}/{player.max_stamina}",
                inline=True,
            )
            embed.add_field(
                name="📍 Локация", value=station_data["name"], inline=True
            )
            embed.add_field(
                name="💰 Никели",
                value=player.inventory.get('никели', 0),
                inline=True,
            )

            view = MainMenu(player)
            try:
                await interaction.response.edit_message(
                    embed=embed, view=view
                )
            except discord.errors.InteractionResponded:
                await interaction.followup.send(
                    embed=embed, view=view, ephemeral=True
                )

        except Exception as e:
            logger.error(f"[MOVE] Ошибка в back_to_menu: {e}")
            logger.error(traceback.format_exc())