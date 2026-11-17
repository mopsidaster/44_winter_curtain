# -*- coding: utf-8 -*-
# func/views/social/brigade_modal.py - Модалка создания группы (0.4.6)

import discord

from ...game_manager import game_manager
from ...social.brigade_manager import brigade_manager
from utils.logger import get_logger

logger = get_logger()


class BrigadeCreateModal(discord.ui.Modal, title="🤝 Создание бригады"):
    name = discord.ui.TextInput(
        label="Название группы",
        placeholder="Например: Стальные крысы",
        min_length=2,
        max_length=50,
        required=True,
    )
    description = discord.ui.TextInput(
        label="Описание (необязательно)",
        placeholder="Кратко о целях группы...",
        required=False,
        max_length=300,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message(
                    "❌ Создайте персонажа!", ephemeral=True
                )
                return
            if brigade_manager.is_user_in_brigade(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Вы уже в группе!", ephemeral=True
                )
                return

            brigade = await brigade_manager.create_brigade(
                leader_id=interaction.user.id,
                name=self.name.value.strip(),
                description=(self.description.value or "").strip(),
            )

            embed = discord.Embed(
                title="✅ Бригада создана",
                description=(
                    f"**{brigade.name}**\n"
                    f"📝 {brigade.description or '_без описания_'}\n\n"
                    f"👑 Лидер: **{player.name}**\n"
                    f"👥 Состав: 1/3\n\n"
                    f"💡 Пригласите игроков через `/brigada add @Игрок`"
                ),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"[Brigade] {player.name} создал группу {brigade.name}")

        except Exception as e:
            logger.error(f"Ошибка в BrigadeCreateModal: {e}")
            try:
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
            except Exception:
                pass