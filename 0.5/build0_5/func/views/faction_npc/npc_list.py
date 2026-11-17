# -*- coding: utf-8 -*-
# func/views/faction_npc/npc_list.py - Список NPC на станции (0.4.8.6)
#
# ИСТОРИЯ:
#   0.4.8   — новый файл.
#   0.4.8.5 — БЕЗ defer: отвечаем сразу через response/followup.
#   0.4.8.6 — Гарантия: fallback-кнопка «Назад», если кнопок 0.
#             Детальное логирование количества кнопок.

import discord
import uuid

from .dialog_view import DialogView
from .dialog_trees import DIALOG_TREES
from ...factions import (
    get_npcs_on_station, get_npc_data,
    get_faction_name, get_faction_emoji,
    get_player_loyalty_level,
)
from utils.logger import get_logger

logger = get_logger()


def build_npc_list_embed(player) -> discord.Embed:
    station_id = getattr(player, 'location', None)
    npcs = get_npcs_on_station(station_id) if station_id else []

    embed = discord.Embed(
        title="👥 NPC рядом",
        color=discord.Color.dark_gold(),
    )

    if not npcs:
        embed.description = (
            "Здесь никого нет.\n\n"
            "NPC появляются на станциях фракций: Бульвар Дмитрия Донского "
            "(Антиквары), Ясенево (Община), Новые Черемушки (Посредник)."
        )
        return embed

    for npc in npcs:
        faction_id = npc.get("faction") or npc.get("mediates_for")
        faction_name = get_faction_name(faction_id) if faction_id else "—"
        emoji = get_faction_emoji(faction_id) if faction_id else "👤"
        role = npc.get("role", "")

        loyalty_line = ""
        if faction_id:
            lvl = get_player_loyalty_level(player, faction_id)
            loyalty_line = f"\n   Ваша лояльность: ур. {lvl}"

        embed.add_field(
            name=f"{npc.get('emoji', '👤')} {npc.get('name', '?')}",
            value=(
                f"{emoji} {faction_name}\n"
                f"   _{npc.get('greeting', '')}_{loyalty_line}"
            ),
            inline=False,
        )

    return embed


class NPCPickerView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=180)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]

        npcs = get_npcs_on_station(player.location)
        for idx, npc in enumerate(npcs[:5]):
            btn = discord.ui.Button(
                label=f"{npc.get('emoji', '👤')} {npc.get('name', '?')}"[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"npclist_{idx}_{self.menu_id}",
                row=idx // 2,
            )
            btn.callback = self.create_npc_callback(npc["id"])
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"npclist_back_{self.menu_id}",
            row=4,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_npc_callback(self, npc_id: str):
        async def callback(interaction: discord.Interaction):
            # 1. Проверка владельца
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message(
                        "❌ Не ваше меню!", ephemeral=True
                    )
                    return
            except discord.errors.NotFound:
                return
            except Exception:
                return

            # 2. Собираем данные
            try:
                npc = get_npc_data(npc_id)
                if not npc:
                    await interaction.response.send_message(
                        "❌ NPC не найден.", ephemeral=True
                    )
                    return

                tree_id = npc.get("dialog_tree")
                tree = DIALOG_TREES.get(tree_id, {})
                root = tree.get("root", "greeting")

                logger.info(
                    f"[NPC] open: npc={npc_id}, tree={tree_id}, root={root}"
                )

                new_view = DialogView(self.player.user_id, npc_id, root)
                embed = new_view.build_embed()

                logger.info(
                    f"[NPC] view ready: buttons={len(new_view.children)}"
                )

                # 3. Отвечаем
                try:
                    if not interaction.response.is_done():
                        await interaction.response.edit_message(
                            embed=embed, view=new_view
                        )
                    else:
                        await interaction.followup.send(
                            embed=embed, view=new_view
                        )
                except discord.errors.NotFound:
                    logger.warning("[NPC] interaction истёк")
                except Exception as e:
                    logger.error(f"[NPC] send error: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"[NPC] build error: {e}", exc_info=True)
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            f"❌ Ошибка диалога: {e}", ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            f"❌ Ошибка диалога: {e}", ephemeral=True
                        )
                except Exception:
                    pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваше меню!", ephemeral=True
            )
            return
        try:
            from ..action_menu import ActionMenu
            embed = discord.Embed(
                title="🎯 Действия",
                description="Выберите действие:",
                color=discord.Color.blue(),
            )
            await interaction.response.edit_message(
                embed=embed, view=ActionMenu()
            )
        except Exception as e:
            logger.error(f"[NPC] back: {e}")