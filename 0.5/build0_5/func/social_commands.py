# -*- coding: utf-8 -*-
# func/social_commands.py - Социальные слеш-команды (0.4.8.8)
#
# ИСТОРИЯ:
#   0.4.6   — новый файл. /brigada, /money, /deliver, /trade.
#   0.4.7.2 — /deliver и /trade открывают UI-выбор предметов кнопками.
#   0.4.8.8 — Бригада создаётся с фракцией лидера (faction_id).

import discord
from discord import app_commands
from discord.ext import commands

from .game_manager import game_manager
from .social.brigade_manager import brigade_manager
from .social.brigade import STATE_ACTIVE, STATE_NO_ACTIVE
from .social.transfer import transfer_manager
from .views.social.brigade_view import build_brigade_list_embed
from .views.social.brigade_invite_view import BrigadeInviteView
from .views.social.brigade_modal import BrigadeCreateModal
from .views.social.money_transfer_view import MoneyTransferView
from .views.social.deliver_view import DeliverView, DeliverBuilder, _DeliverRootView
from .views.social.trade_view import TradeView
from utils.logger import get_logger

logger = get_logger()


def setup_social_commands(bot: commands.Bot):
    brigade_group = app_commands.Group(
        name="brigada", description="Группы (бригады)"
    )

    async def _safe_send(interaction: discord.Interaction, **kwargs):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(**kwargs)
                return True
        except discord.errors.NotFound:
            return False
        except discord.errors.InteractionResponded:
            pass
        try:
            await interaction.followup.send(**kwargs)
            return True
        except Exception:
            return False

    # ==================== /brigada ====================

    @brigade_group.command(name="new", description="Создать группу (бригаду)")
    async def brigade_new(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(
                    interaction,
                    content="❌ Создайте персонажа командой /start",
                    ephemeral=True,
                )
                return
            if not player.is_alive:
                await _safe_send(
                    interaction, content="💀 Вы мертвы!", ephemeral=True
                )
                return
            if brigade_manager.is_user_in_brigade(interaction.user.id):
                await _safe_send(
                    interaction, content="❌ Вы уже в группе!", ephemeral=True
                )
                return
            # 0.4.8.8: модалка сама передаст фракцию лидера
            await interaction.response.send_modal(BrigadeCreateModal())
        except Exception as e:
            logger.error(f"Ошибка в brigade_new: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    @brigade_group.command(
        name="add", description="Пригласить игрока в группу"
    )
    @app_commands.describe(target="Игрок для приглашения")
    async def brigade_add(interaction: discord.Interaction,
                          target: discord.Member):
        try:
            initiator = game_manager.get_player(interaction.user.id)
            target_player = game_manager.get_player(target.id)

            if not initiator or not target_player:
                await _safe_send(
                    interaction,
                    content="❌ Один из игроков не создан!",
                    ephemeral=True,
                )
                return
            if initiator.user_id == target_player.user_id:
                await _safe_send(
                    interaction,
                    content="❌ Нельзя пригласить самого себя!",
                    ephemeral=True,
                )
                return
            if not target_player.is_alive:
                await _safe_send(
                    interaction, content="❌ Цель мертва!", ephemeral=True
                )
                return
            if initiator.location != target_player.location:
                await _safe_send(
                    interaction,
                    content="❌ Вы должны быть на одной станции!",
                    ephemeral=True,
                )
                return

            brigade = brigade_manager.get_user_brigade(initiator.user_id)
            if not brigade:
                await _safe_send(
                    interaction,
                    content="❌ Вы не в группе! Создайте через /brigada new",
                    ephemeral=True,
                )
                return
            if not brigade.is_leader(initiator.user_id):
                await _safe_send(
                    interaction,
                    content="❌ Только лидер может приглашать!",
                    ephemeral=True,
                )
                return
            if brigade.is_full():
                await _safe_send(
                    interaction,
                    content="❌ В группе уже 3 человека!",
                    ephemeral=True,
                )
                return
            if brigade.has_member(target_player.user_id):
                await _safe_send(
                    interaction,
                    content="❌ Игрок уже в вашей группе!",
                    ephemeral=True,
                )
                return
            if brigade_manager.is_user_in_brigade(target_player.user_id):
                await _safe_send(
                    interaction,
                    content="❌ Игрок уже в другой группе!",
                    ephemeral=True,
                )
                return

            invite = brigade_manager.create_invite(
                brigade.brigade_id, initiator.user_id, target_player.user_id
            )

            embed = discord.Embed(
                title="🤝 Приглашение в бригаду",
                description=(
                    f"**{initiator.name}** приглашает "
                    f"**{target_player.name}** в группу "
                    f"**{brigade.name}**.\n\n"
                    f"📝 {brigade.description or '_без описания_'}\n"
                    f"👥 Состав: {brigade.member_count()}/3\n\n"
                    f"🎯 **{target_player.name}**, вы согласны?"
                ),
                color=discord.Color.blue(),
            )
            embed.set_footer(text="⏱️ У вас 60 секунд")

            view = BrigadeInviteView(
                invite.invite_id, initiator.user_id, target_player.user_id
            )
            await _safe_send(interaction, embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка в brigade_add: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    @brigade_group.command(name="view", description="Список всех групп")
    async def brigade_view(interaction: discord.Interaction):
        try:
            embed = build_brigade_list_embed(game_manager)
            await _safe_send(interaction, embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Ошибка в brigade_view: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    @brigade_group.command(name="leave", description="Покинуть группу")
    async def brigade_leave(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(
                    interaction,
                    content="❌ Создайте персонажа!",
                    ephemeral=True,
                )
                return
            brigade = brigade_manager.get_user_brigade(interaction.user.id)
            if not brigade:
                await _safe_send(
                    interaction, content="❌ Вы не в группе!", ephemeral=True
                )
                return
            if brigade.is_leader(interaction.user.id):
                await brigade_manager.disband_brigade(brigade.brigade_id)
                await _safe_send(
                    interaction,
                    content=f"🚪 Группа **{brigade.name}** распущена.",
                    ephemeral=True,
                )
                return
            await brigade_manager.remove_member(
                brigade.brigade_id, interaction.user.id
            )
            await _safe_send(
                interaction,
                content=f"🚪 Вы покинули группу **{brigade.name}**.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Ошибка в brigade_leave: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    @brigade_group.command(
        name="kick",
        description="Исключить игрока из группы (только лидер)",
    )
    @app_commands.describe(target="Игрок для исключения")
    async def brigade_kick(interaction: discord.Interaction,
                           target: discord.Member):
        try:
            initiator = game_manager.get_player(interaction.user.id)
            target_player = game_manager.get_player(target.id)
            if not initiator or not target_player:
                await _safe_send(
                    interaction,
                    content="❌ Один из игроков не создан!",
                    ephemeral=True,
                )
                return
            brigade = brigade_manager.get_user_brigade(initiator.user_id)
            if not brigade:
                await _safe_send(
                    interaction, content="❌ Вы не в группе!", ephemeral=True
                )
                return
            if not brigade.is_leader(initiator.user_id):
                await _safe_send(
                    interaction,
                    content="❌ Только лидер может исключать!",
                    ephemeral=True,
                )
                return
            if initiator.user_id == target_player.user_id:
                await _safe_send(
                    interaction,
                    content="❌ Нельзя исключить себя!",
                    ephemeral=True,
                )
                return
            if not brigade.has_member(target_player.user_id):
                await _safe_send(
                    interaction,
                    content="❌ Игрок не в вашей группе!",
                    ephemeral=True,
                )
                return
            await brigade_manager.remove_member(
                brigade.brigade_id, target_player.user_id
            )
            await _safe_send(
                interaction,
                content=(
                    f"👋 **{target_player.name}** исключён из группы "
                    f"**{brigade.name}**."
                ),
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Ошибка в brigade_kick: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    @brigade_group.command(
        name="active", description="Переключить в режим «Вместе»"
    )
    async def brigade_active(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(
                    interaction,
                    content="❌ Создайте персонажа!",
                    ephemeral=True,
                )
                return
            brigade = brigade_manager.get_user_brigade(interaction.user.id)
            if not brigade:
                await _safe_send(
                    interaction, content="❌ Вы не в группе!", ephemeral=True
                )
                return
            if not brigade.is_leader(interaction.user.id):
                await _safe_send(
                    interaction,
                    content="❌ Только лидер может менять режим!",
                    ephemeral=True,
                )
                return
            if brigade.is_active():
                await _safe_send(
                    interaction,
                    content="❌ Уже режим «Вместе».",
                    ephemeral=True,
                )
                return
            leader_loc = player.location
            for uid in brigade.get_member_ids():
                if uid == interaction.user.id:
                    continue
                m = game_manager.get_player(uid)
                if not m or m.location != leader_loc:
                    await _safe_send(
                        interaction,
                        content=(
                            "❌ Не все участники на одной станции "
                            "с лидером!"
                        ),
                        ephemeral=True,
                    )
                    return
            await brigade_manager.set_state(
                brigade.brigade_id, STATE_ACTIVE
            )
            await _safe_send(
                interaction,
                content=(
                    f"✅ Группа **{brigade.name}** теперь ходит **Вместе**."
                ),
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Ошибка в brigade_active: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    @brigade_group.command(
        name="no_active", description="Переключить в режим «Расход»"
    )
    async def brigade_no_active(interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await _safe_send(
                    interaction,
                    content="❌ Создайте персонажа!",
                    ephemeral=True,
                )
                return
            brigade = brigade_manager.get_user_brigade(interaction.user.id)
            if not brigade:
                await _safe_send(
                    interaction, content="❌ Вы не в группе!", ephemeral=True
                )
                return
            if not brigade.is_leader(interaction.user.id):
                await _safe_send(
                    interaction,
                    content="❌ Только лидер может менять режим!",
                    ephemeral=True,
                )
                return
            if brigade.is_no_active():
                await _safe_send(
                    interaction,
                    content="❌ Уже режим «Расход».",
                    ephemeral=True,
                )
                return
            await brigade_manager.set_state(
                brigade.brigade_id, STATE_NO_ACTIVE
            )
            await _safe_send(
                interaction,
                content=(
                    f"✅ Группа **{brigade.name}** теперь **Расход** "
                    f"(каждый ходит сам)."
                ),
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Ошибка в brigade_no_active: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    bot.tree.add_command(brigade_group)

    # ==================== /money ====================

    @bot.tree.command(name="money", description="Передать никели игроку")
    @app_commands.describe(target="Получатель", amount="Сумма (мин. 100)")
    async def cmd_money(interaction: discord.Interaction,
                        target: discord.Member, amount: int):
        try:
            sender = game_manager.get_player(interaction.user.id)
            receiver = game_manager.get_player(target.id)

            if not sender or not receiver:
                await _safe_send(
                    interaction,
                    content="❌ Один из игроков не создан!",
                    ephemeral=True,
                )
                return
            if sender.user_id == receiver.user_id:
                await _safe_send(
                    interaction,
                    content="❌ Нельзя передать самому себе!",
                    ephemeral=True,
                )
                return
            if sender.location != receiver.location:
                await _safe_send(
                    interaction,
                    content="❌ Вы должны быть на одной станции!",
                    ephemeral=True,
                )
                return
            if amount < 100:
                await _safe_send(
                    interaction,
                    content="❌ Минимум 100 никелей!",
                    ephemeral=True,
                )
                return
            if sender.inventory.get('никели', 0) < amount:
                await _safe_send(
                    interaction,
                    content="❌ Недостаточно никелей!",
                    ephemeral=True,
                )
                return

            t = transfer_manager.create_money_transfer(
                sender.user_id, receiver.user_id, amount
            )

            embed = discord.Embed(
                title="💰 Передача никелей",
                description=(
                    f"**{sender.name}** передаёт **{amount}** никелей "
                    f"игроку **{receiver.name}**.\n\n"
                    f"🎯 **{receiver.name}**, принять?"
                ),
                color=discord.Color.gold(),
            )
            embed.set_footer(text="⏱️ У вас 10 минут")

            view = MoneyTransferView(
                t.transfer_id, sender.user_id, receiver.user_id
            )
            await _safe_send(interaction, embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка в cmd_money: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    # ==================== /deliver ====================

    @bot.tree.command(name="deliver", description="Передать предметы игроку")
    @app_commands.describe(target="Получатель")
    async def cmd_deliver(interaction: discord.Interaction,
                          target: discord.Member):
        try:
            sender = game_manager.get_player(interaction.user.id)
            receiver = game_manager.get_player(target.id)

            if not sender or not receiver:
                await _safe_send(
                    interaction,
                    content="❌ Один из игроков не создан!",
                    ephemeral=True,
                )
                return
            if sender.user_id == receiver.user_id:
                await _safe_send(
                    interaction,
                    content="❌ Нельзя передать самому себе!",
                    ephemeral=True,
                )
                return
            if sender.location != receiver.location:
                await _safe_send(
                    interaction,
                    content="❌ Вы должны быть на одной станции!",
                    ephemeral=True,
                )
                return

            builder = DeliverBuilder(sender, receiver)

            embed = builder._build_builder_embed(
                title="📦 Что передать?",
                hint=(
                    "Выберите категорию и предметы кнопками.\n"
                    "Когда закончите — нажмите **Подтвердить**."
                ),
            )

            view = _DeliverRootView(sender, receiver, builder)
            await _safe_send(interaction, embed=embed, view=view)

        except Exception as e:
            logger.error(f"Ошибка в cmd_deliver: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    # ==================== /trade ====================

    @bot.tree.command(name="trade", description="Двусторонний обмен")
    @app_commands.describe(target="Партнёр для обмена")
    async def cmd_trade(interaction: discord.Interaction,
                        target: discord.Member):
        try:
            initiator = game_manager.get_player(interaction.user.id)
            receiver = game_manager.get_player(target.id)

            if not initiator or not receiver:
                await _safe_send(
                    interaction,
                    content="❌ Один из игроков не создан!",
                    ephemeral=True,
                )
                return
            if initiator.user_id == receiver.user_id:
                await _safe_send(
                    interaction,
                    content="❌ Нельзя обменять самого себя!",
                    ephemeral=True,
                )
                return
            if initiator.location != receiver.location:
                await _safe_send(
                    interaction,
                    content="❌ Вы должны быть на одной станции!",
                    ephemeral=True,
                )
                return

            t = transfer_manager.create_trade(
                initiator.user_id, receiver.user_id
            )
            view = TradeView(
                t.trade_id, initiator.user_id, receiver.user_id
            )
            embed = view.build_embed()

            await _safe_send(interaction, embed=embed, view=view)
        except Exception as e:
            logger.error(f"Ошибка в cmd_trade: {e}")
            await _safe_send(
                interaction, content=f"❌ Ошибка: {str(e)}", ephemeral=True
            )

    logger.info(
        "✅ Социальные команды (/brigada, /money, /deliver, /trade) "
        "зарегистрированы"
    )