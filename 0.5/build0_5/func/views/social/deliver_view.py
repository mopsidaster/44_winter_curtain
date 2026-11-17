# -*- coding: utf-8 -*-
# func/views/social/deliver_view.py - UI передачи вещей (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.6   — кнопки «Принять/Отказаться»
#   0.4.7.2 — новый многошаговый UI выбора предметов:
#             категория → предмет → количество → подтверждение.
#             Получатель видит понятное описание и жмёт «Принять/Отказаться».

import discord

from ...game_manager import game_manager
from ...social.transfer import transfer_manager
from ...social.trade import apply_deliver
from ...social.item_picker import (
    CategoryPickerView, ItemPickerView, CountPickerView,
    build_category_embed, build_items_embed, build_count_embed,
    apply_count_to_descriptor, describe_item, get_items_in_category,
)
from database.db import save_player
from utils.logger import get_logger

logger = get_logger()


# ==================== ПРИЁМ У ПОЛУЧАТЕЛЯ ====================

class DeliverView(discord.ui.View):
    """Кнопки «Принять/Отказаться» для получателя."""

    def __init__(self, transfer_id: str, sender_id: int, receiver_id: int):
        super().__init__(timeout=600)
        self.transfer_id = transfer_id
        self.sender_id = sender_id
        self.receiver_id = receiver_id

    async def _not_receiver(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "❌ Это предложение не для вас!", ephemeral=True
        )

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receiver_id:
            await self._not_receiver(interaction)
            return

        t = transfer_manager.get_deliver(self.transfer_id)
        if not t or t.resolved:
            await interaction.response.send_message(
                "⏳ Предложение недействительно.", ephemeral=True
            )
            return

        sender = game_manager.get_player(t.sender_id)
        receiver = game_manager.get_player(t.receiver_id)
        if not sender or not receiver:
            await interaction.response.send_message(
                "❌ Один из игроков не найден.", ephemeral=True
            )
            transfer_manager.resolve_deliver(self.transfer_id)
            return

        ok, reason = apply_deliver(sender, receiver, t.items)
        if not ok:
            await interaction.response.send_message(
                f"❌ Не удалось передать: {reason}", ephemeral=True
            )
            transfer_manager.resolve_deliver(self.transfer_id)
            return

        transfer_manager.resolve_deliver(self.transfer_id)
        await save_player(sender)
        await save_player(receiver)

        items_text = "\n".join(describe_item(it) for it in t.items) or "_пусто_"

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="📦 Передача выполнена",
                description=(
                    f"**{sender.name}** → **{receiver.name}**\n\n"
                    f"{items_text}"
                ),
                color=discord.Color.green(),
            ),
            view=None,
        )

    @discord.ui.button(label="❌ Отказаться", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receiver_id:
            await self._not_receiver(interaction)
            return

        transfer_manager.resolve_deliver(self.transfer_id)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🚪 Передача отклонена",
                description=f"**{interaction.user.display_name}** отказался принимать предметы.",
                color=discord.Color.dark_gray(),
            ),
            view=None,
        )


# ==================== МНОГОШАГОВЫЙ ПИКЕР ДЛЯ ОТПРАВИТЕЛЯ ====================

class DeliverBuilder:
    """
    Управляет сессией выбора предметов для /deliver.
    Хранит список выбранных item-descriptor'ов.
    """

    def __init__(self, sender, receiver):
        self.sender = sender
        self.receiver = receiver
        self.selected: list[dict] = []

    async def start(self, interaction: discord.Interaction):
        """Первый шаг — выбор категории."""
        await self._show_categories(interaction, first=True)

    async def _show_categories(self, interaction: discord.Interaction, first: bool = False):
        embed = self._build_builder_embed(
            title="📦 Что передать?",
            hint="Выберите категорию предметов.",
        )

        view = CategoryPickerView(
            player=self.sender,
            on_pick=self._on_category_picked,
            back_label="🔙 Отмена",
        )

        # Заменяем callback отмены на закрытие сессии
        for child in view.children:
            if child.custom_id.endswith("_back_" + view.menu_id):
                child.callback = self._cancel_callback

        if first:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except Exception:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _on_category_picked(self, interaction: discord.Interaction, category_id: str):
        embed = build_items_embed(
            self.sender, category_id,
            title=f"📦 {self._category_title(category_id)}"
        )
        embed = self._append_selected(embed)

        view = ItemPickerView(
            player=self.sender,
            category_id=category_id,
            on_pick=self._on_item_picked,
            back_callback=self._back_to_categories,
        )
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _on_item_picked(self, interaction: discord.Interaction, item: dict):
        # Если у предмета есть count > 1 — спрашиваем количество
        if item.get("count") and int(item.get("count", 1)) > 1:
            embed = build_count_embed(item)
            embed = self._append_selected(embed)
            view = CountPickerView(
                player=self.sender,
                item=item,
                on_pick=lambda i, n: self._on_count_picked(i, item, n),
                back_callback=self._back_to_categories,
            )
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except Exception:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

        # Одиночный предмет — добавляем сразу
        desc = apply_count_to_descriptor(item, 1)
        self.selected.append(desc)
        await self._show_categories(interaction)

    async def _on_count_picked(self, interaction: discord.Interaction, item: dict, count: int):
        desc = apply_count_to_descriptor(item, count)
        self.selected.append(desc)
        await self._show_categories(interaction)

    async def _back_to_categories(self, interaction: discord.Interaction):
        await self._show_categories(interaction)

    async def _cancel_callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="🚪 Передача отменена",
                    description="Вы отменили передачу предметов.",
                    color=discord.Color.dark_gray(),
                ),
                view=None,
            )
        except Exception:
            pass

    def _category_title(self, category_id: str) -> str:
        mapping = {
            "weapon": "Оружие",
            "melee": "Ближний бой",
            "armor": "Броня и шлемы",
            "module": "Модули",
            "magazine": "Магазины",
            "throwable": "Гранаты и ножи",
            "consumable": "Расходники",
            "food": "Еда",
        }
        return mapping.get(category_id, category_id)

    def _append_selected(self, embed: discord.Embed) -> discord.Embed:
        if self.selected:
            text = "\n".join(f"• {describe_item(it)}" for it in self.selected[:10])
            if len(self.selected) > 10:
                text += f"\n... и ещё {len(self.selected) - 10}"
            embed.add_field(
                name=f"✅ Выбрано ({len(self.selected)})",
                value=text,
                inline=False,
            )
        return embed

    def _build_builder_embed(self, title: str, hint: str) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=(
                f"**Отправитель:** {self.sender.name}\n"
                f"**Получатель:** {self.receiver.name}\n\n"
                f"{hint}"
            ),
            color=discord.Color.blue(),
        )
        return self._append_selected(embed)


# ==================== ВХОД В СЕССИЮ ====================

async def open_deliver_builder(interaction: discord.Interaction, sender, receiver):
    """Открывает UI выбора предметов для /deliver."""
    builder = DeliverBuilder(sender, receiver)

    embed = builder._build_builder_embed(
        title="📦 Что передать?",
        hint="Выберите категорию предметов.",
    )

    view = _DeliverRootView(sender, receiver, builder)
    await interaction.response.edit_message(embed=embed, view=view)


class _DeliverRootView(discord.ui.View):
    """
    Корневое меню /deliver. Кнопки:
      • «Выбрать предмет» — открывает категории
      • «Подтвердить» — создаёт transfer и отправляет получателю
      • «Отмена» — закрывает
    """

    def __init__(self, sender, receiver, builder: DeliverBuilder):
        super().__init__(timeout=300)
        self.sender = sender
        self.receiver = receiver
        self.builder = builder

    @discord.ui.button(label="📦 Выбрать предмет", style=discord.ButtonStyle.primary)
    async def pick(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.sender.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return
        await self.builder._show_categories(interaction)

    @discord.ui.button(label="✅ Подтвердить", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.sender.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        if not self.builder.selected:
            await interaction.response.send_message(
                "❌ Вы не выбрали ни одного предмета!", ephemeral=True
            )
            return

        from ...social.trade import validate_offer_items
        ok, reason = validate_offer_items(self.sender, self.builder.selected)
        if not ok:
            await interaction.response.send_message(
                f"❌ {reason}", ephemeral=True
            )
            return

        t = transfer_manager.create_deliver(
            self.sender.user_id, self.receiver.user_id,
            list(self.builder.selected)
        )

        items_text = "\n".join(
            describe_item(it) for it in self.builder.selected
        ) or "_пусто_"

        embed = discord.Embed(
            title="📦 Передача предметов",
            description=(
                f"**{self.sender.name}** → **{self.receiver.name}**\n\n"
                f"{items_text}\n\n"
                f"🎯 **{self.receiver.name}**, принять?"
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="⏱️ У вас 10 минут")

        view = DeliverView(t.transfer_id, self.sender.user_id, self.receiver.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.sender.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="🚪 Передача отменена",
                    description="Вы отменили передачу предметов.",
                    color=discord.Color.dark_gray(),
                ),
                view=None,
            )
        except Exception:
            pass