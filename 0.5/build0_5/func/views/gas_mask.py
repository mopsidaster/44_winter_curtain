# -*- coding: utf-8 -*-
# func/views/gas_mask.py - Меню противогаза и фильтров (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.2.10 — custom_id через uuid
#   0.4.7.2  — после установки фильтра показываем кнопку «Назад»
#              и текущее состояние фильтра

import discord
import uuid
from .helpers import (
    game_manager, MAP_DATA, save_player, get_current_filter_info,
    get_filter, format_filters_inventory, equip_filter, unequip_filter
)


class GasMaskMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="🎒 Надеть противогаз", style=discord.ButtonStyle.success)
    async def put_on_mask(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа!", ephemeral=True)
                return
            if not player.is_alive:
                await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)
                return
            if not player.has_gas_mask:
                await interaction.response.send_message("❌ У вас нет противогаза!", ephemeral=True)
                return
            if player.gas_mask["состояние"] == "разбитый":
                await interaction.response.send_message("❌ Противогаз разбит!", ephemeral=True)
                return
            if player.gas_mask.get("надет", False):
                await interaction.response.send_message("❌ Противогаз уже надет!", ephemeral=True)
                return

            player.gas_mask["надет"] = True
            await save_player(player)
            await interaction.response.send_message(f"🎒 **{player.name}** надел противогаз!", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🎒 Снять противогаз", style=discord.ButtonStyle.danger)
    async def take_off_mask(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа!", ephemeral=True)
                return
            if not player.is_alive:
                await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)
                return
            if not player.gas_mask.get("надет", False):
                await interaction.response.send_message("❌ Противогаз и так снят!", ephemeral=True)
                return
            if MAP_DATA["станции"][player.location].get("ruined", False):
                await interaction.response.send_message(
                    "❌ Нельзя снимать противогаз на опасной станции!",
                    ephemeral=True
                )
                return

            player.gas_mask["надет"] = False
            await save_player(player)
            await interaction.response.send_message(f"🎒 **{player.name}** снял противогаз!", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🧪 Управление фильтрами", style=discord.ButtonStyle.primary)
    async def filter_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player or not player.is_alive:
                await interaction.response.send_message("❌ Ошибка!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🧪 Управление фильтрами",
                description="Управление фильтрами для противогаза",
                color=discord.Color.blue()
            )

            if not player.gas_mask.get("надет", False):
                embed.add_field(
                    name="⚠️ Противогаз не надет",
                    value="Установить фильтр можно, но он не будет работать, пока вы не наденете противогаз.",
                    inline=False
                )

            current = get_current_filter_info(player)
            if current["has_filter"]:
                status = "✅ Активен" if not current["is_expired"] else "❌ Израсходован"
                embed.add_field(
                    name="📊 Текущий фильтр",
                    value=f"{current['filter_emoji']} **{current['filter_name']}**\n"
                          f"Состояние: {status}\n"
                          f"Прочность: {current['current_durability']:.1f}/{current['max_durability']}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📊 Текущий фильтр",
                    value="❌ Фильтр не установлен",
                    inline=False
                )

            embed.add_field(
                name="📦 Ваши фильтры",
                value=format_filters_inventory(player),
                inline=False
            )

            view = FilterManagementMenu(player)
            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            from .action_menu import ActionMenu
            embed = discord.Embed(
                title="🎯 Действия",
                description="Выберите действие:",
                color=discord.Color.blue()
            )
            view = ActionMenu()
            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)


class FilterManagementMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="🧪 Установить фильтр", style=discord.ButtonStyle.success)
    async def equip_filter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа!", ephemeral=True)
                return

            if not player.gas_mask.get("надет", False):
                await interaction.response.send_message(
                    "❌ Сначала наденьте противогаз!\n💡 Используйте «Надеть противогаз» в меню противогаза.",
                    ephemeral=True
                )
                return

            if not player.filters:
                await interaction.response.send_message(
                    "❌ У вас нет фильтров! Купите их в торговой зоне.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🧪 Установка фильтра",
                description="Выберите фильтр для установки:",
                color=discord.Color.green()
            )

            for filter_id in set(player.filters):
                filter_data = get_filter(filter_id)
                if filter_data:
                    count = player.filters.count(filter_id)
                    embed.add_field(
                        name=f"{filter_data.get('emoji', '🧪')} {filter_data.get('name', filter_id)} (x{count})",
                        value=f"Прочность: {filter_data.get('durability', 0)} единиц",
                        inline=True
                    )

            view = FilterEquipMenu(player)
            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🧪 Снять фильтр", style=discord.ButtonStyle.danger)
    async def unequip_filter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа!", ephemeral=True)
                return

            result = await unequip_filter(player)
            await save_player(player)
            await interaction.response.send_message(result, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Создайте персонажа!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🎒 Управление противогазом",
                description="Выберите действие:",
                color=discord.Color.blue()
            )

            mask_status = {
                "целый": "🟢 Целый",
                "поношенный": "🟡 Поношенный",
                "разбитый": "🔴 Разбитый"
            }
            status = mask_status.get(player.gas_mask["состояние"], "❓ Неизвестно")
            worn = "✅ Надет" if player.gas_mask.get("надет", False) else "❌ Снят"

            current_filter = get_current_filter_info(player)
            filter_status = "✅ Вставлен" if current_filter["has_filter"] and not current_filter["is_expired"] else "❌ Не вставлен"
            if current_filter["has_filter"]:
                filter_status += f" ({current_filter['filter_name']}, {current_filter['current_durability']:.1f})"

            embed.add_field(
                name="📊 Состояние",
                value=f"Состояние: {status}\nНадет: {worn}\nФильтр: {filter_status}",
                inline=False
            )

            view = GasMaskMenu()
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except discord.errors.InteractionResponded:
                await interaction.followup.send(embed=embed, view=view, ephemeral=False)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)


class FilterEquipMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        unique_filters = list(set(self.player.filters))

        for idx, filter_id in enumerate(unique_filters):
            filter_data = get_filter(filter_id)
            if filter_data:
                count = self.player.filters.count(filter_id)
                button = discord.ui.Button(
                    label=f"{filter_data.get('emoji', '🧪')} {filter_data.get('name', filter_id)} (x{count})",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"equip_filter_{self.menu_id}_{idx}"
                )
                button.callback = self.create_callback(filter_id)
                self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"equip_filter_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, filter_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            result = await equip_filter(self.player, filter_id)
            await save_player(self.player)

            # 0.4.7.2: после установки фильтра показываем embed с состоянием
            # + кнопка «Назад» (возврат в меню управления фильтрами)
            embed = discord.Embed(
                title="🧪 Результат",
                description=result,
                color=discord.Color.green() if "✅" in result else discord.Color.red()
            )

            current = get_current_filter_info(self.player)
            if current["has_filter"]:
                embed.add_field(
                    name="📊 Текущий фильтр",
                    value=(
                        f"{current['filter_emoji']} **{current['filter_name']}**\n"
                        f"Прочность: {current['current_durability']:.1f}/{current['max_durability']}"
                    ),
                    inline=False
                )

            view = _FilterAfterEquipMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception:
                pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            player = game_manager.get_player(interaction.user.id)
            if not player:
                await interaction.response.send_message("❌ Ошибка!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🧪 Управление фильтрами",
                description="Управление фильтрами для противогаза",
                color=discord.Color.blue()
            )

            current = get_current_filter_info(player)
            if current["has_filter"]:
                status = "✅ Активен" if not current["is_expired"] else "❌ Израсходован"
                embed.add_field(
                    name="📊 Текущий фильтр",
                    value=f"{current['filter_emoji']} **{current['filter_name']}**\n"
                          f"Состояние: {status}\n"
                          f"Прочность: {current['current_durability']:.1f}/{current['max_durability']}",
                    inline=False
                )
            else:
                embed.add_field(name="📊 Текущий фильтр", value="❌ Фильтр не установлен", inline=False)

            embed.add_field(name="📦 Ваши фильтры", value=format_filters_inventory(player), inline=False)

            view = FilterManagementMenu(player)
            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except discord.errors.InteractionResponded:
                await interaction.followup.send(embed=embed, view=view, ephemeral=False)

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)


class _FilterAfterEquipMenu(discord.ui.View):
    """0.4.7.2: кнопка «Назад» после установки фильтра."""

    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        try:
            embed = discord.Embed(
                title="🧪 Управление фильтрами",
                description="Управление фильтрами для противогаза",
                color=discord.Color.blue()
            )

            current = get_current_filter_info(self.player)
            if current["has_filter"]:
                status = "✅ Активен" if not current["is_expired"] else "❌ Израсходован"
                embed.add_field(
                    name="📊 Текущий фильтр",
                    value=f"{current['filter_emoji']} **{current['filter_name']}**\n"
                          f"Состояние: {status}\n"
                          f"Прочность: {current['current_durability']:.1f}/{current['max_durability']}",
                    inline=False
                )
            else:
                embed.add_field(name="📊 Текущий фильтр",
                                value="❌ Фильтр не установлен", inline=False)

            embed.add_field(
                name="📦 Ваши фильтры",
                value=format_filters_inventory(self.player),
                inline=False
            )

            view = FilterManagementMenu(self.player)
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
            except Exception:
                pass