# -*- coding: utf-8 -*-
# func/views/food.py - Меню еды (Билд 0.4.5)
#
# ИСТОРИЯ:
#   0.4.2.10 — custom_id через uuid
#   0.4.5    — чайный гриб в FoodBuyMenu

import discord
import uuid
import logging
from .helpers import save_player, get_food, format_food_inventory, get_trade_discount, game_manager
from ..food_system import eat_food
from ..map_data import MAP_DATA

logger = logging.getLogger('metro_bot.food')


# ==================== МЕНЮ ЕДЫ (ПОЕДАНИЕ) ====================

class FoodMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        unique_foods = list(set(self.player.food_inventory))

        for idx, food_id in enumerate(unique_foods):
            food = get_food(food_id)
            if food:
                count = self.player.food_inventory.count(food_id)
                button = discord.ui.Button(
                    label=f"{food.get('emoji', '🍖')} {food.get('name', food_id)} ({count} шт.)",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"eat_{self.menu_id}_{idx}"
                )
                button.callback = self.create_callback(food_id)
                self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"food_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, food_id: str):
        async def callback(interaction: discord.Interaction):
            logger.info(f"🍽️ Еда: нажата кнопка {food_id} от {interaction.user.id}")

            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            result = await eat_food(self.player, food_id)
            await save_player(self.player)

            if self.player.food_inventory:
                embed = discord.Embed(
                    title="🍖 Инвентарь еды",
                    description="Выберите, что хотите съесть:",
                    color=discord.Color.green()
                )

                embed.add_field(name="🍽️ Результат", value=result, inline=False)

                food_counts = {}
                for fid in self.player.food_inventory:
                    food_counts[fid] = food_counts.get(fid, 0) + 1

                food_list = []
                for fid, count in food_counts.items():
                    food = get_food(fid)
                    if food:
                        food_list.append(
                            f"{food.get('emoji', '🍖')} **{food.get('name', fid)}** — "
                            f"{count} шт. (+{food.get('stamina', 0)} вын.)"
                        )

                embed.add_field(
                    name=f"📦 В инвентаре ({len(self.player.food_inventory)} шт.)",
                    value="\n".join(food_list),
                    inline=False
                )

                embed.add_field(
                    name="🏃 Выносливость",
                    value=f"{self.player.stamina:.1f}/{self.player.max_stamina}",
                    inline=False
                )

                new_view = FoodMenu(self.player)
                await interaction.edit_original_response(embed=embed, view=new_view)
            else:
                embed = discord.Embed(
                    title="🍖 Инвентарь еды",
                    description="У вас больше нет еды.",
                    color=discord.Color.red()
                )
                embed.add_field(name="🍽️ Результат", value=result, inline=False)
                embed.add_field(
                    name="🏃 Выносливость",
                    value=f"{self.player.stamina:.1f}/{self.player.max_stamina}",
                    inline=False
                )
                view = FoodEmptyMenu()
                await interaction.edit_original_response(embed=embed, view=view)

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        logger.info(f"🔙 Назад нажата от {interaction.user.id}")

        try:
            from .main_menu import MainMenu

            player = game_manager.get_player(interaction.user.id)

            if player:
                station_data = MAP_DATA["станции"][player.location]
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

                view = MainMenu(player)
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message("❌ Игрок не найден", ephemeral=True)

        except discord.errors.InteractionResponded:
            try:
                await interaction.followup.send("✅ Возврат в меню", ephemeral=True)
                await interaction.message.delete()
            except Exception as e2:
                logger.error(f"❌ Ошибка followup: {e2}")
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
            except:
                try:
                    await interaction.followup.send(f"❌ Ошибка: {str(e)}", ephemeral=True)
                except:
                    pass


class FoodEmptyMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🔙 Назад (пустое меню) нажата от {interaction.user.id}")

        try:
            from .main_menu import MainMenu

            player = game_manager.get_player(interaction.user.id)

            if player:
                station_data = MAP_DATA["станции"][player.location]
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

                view = MainMenu(player)
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message("❌ Игрок не найден", ephemeral=True)

        except discord.errors.InteractionResponded:
            try:
                await interaction.followup.send("✅ Возврат в меню", ephemeral=True)
                await interaction.message.delete()
            except Exception as e2:
                logger.error(f"❌ Ошибка followup: {e2}")
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
            except:
                try:
                    await interaction.followup.send(f"❌ Ошибка: {str(e)}", ephemeral=True)
                except:
                    pass


# ==================== МЕНЮ ПОКУПКИ ЕДЫ ====================

class FoodBuyMenu(discord.ui.View):
    """
    0.4.5: добавлен чайный гриб.
    Кнопки раскладываются по 2 в ряд (row 0 — первые 2, row 1 — следующие 2).
    """
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        discount = get_trade_discount(game_manager)
        # 0.4.5: добавлен чайный_гриб
        food_shop_items = ["мясо_крысы", "съедобные_грибы", "кусок_свинины", "чайный_гриб"]

        for idx, food_id in enumerate(food_shop_items):
            food = get_food(food_id)
            if food:
                price = int(food.get('price', 0) * discount)
                button = discord.ui.Button(
                    label=f"{food.get('emoji', '🍖')} {food.get('name', food_id)} ({price} никелей)",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"buy_food_{self.menu_id}_{idx}",
                    row=idx // 2
                )
                button.callback = self.create_callback(food_id, price)
                self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"buy_food_back_{self.menu_id}",
            row=3
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, food_id: str, price: int):
        async def callback(interaction: discord.Interaction):
            logger.info(f"🛒 Покупка еды: {food_id} от {interaction.user.id}")

            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            if self.player.inventory['никели'] < price:
                await interaction.edit_original_response(
                    embed=discord.Embed(
                        title="❌ Недостаточно никелей",
                        description=f"Нужно {price} никелей. У вас: {self.player.inventory['никели']}",
                        color=discord.Color.red()
                    )
                )
                return

            self.player.inventory['никели'] -= price
            self.player.food_inventory.append(food_id)
            await save_player(self.player)

            food = get_food(food_id)

            embed = discord.Embed(
                title="✅ Покупка завершена!",
                description=f"Куплено {food.get('emoji', '🍖')} **{food.get('name', food_id)}** за {price} никелей!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="💰 Никели",
                value=f"Остаток: **{self.player.inventory['никели']}**",
                inline=False
            )

            view = FoodBuyMenu(self.player)
            await interaction.edit_original_response(embed=embed, view=view)

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        logger.info(f"🔙 Назад (покупка) нажата от {interaction.user.id}")

        try:
            from .trade import TradeMenu

            embed = discord.Embed(
                title="🏪 Торговая зона",
                description="Нажмите на кнопку для покупки или продажи.",
                color=discord.Color.gold()
            )
            view = TradeMenu(self.player)

            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except discord.errors.InteractionResponded:
                await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())