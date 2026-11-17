# -*- coding: utf-8 -*-
# func/views/ammo.py - Меню покупки патронов (0.4.6.2)
#
# ИСТОРИЯ:
#   0.4.4   — ГП-25, дробовики
#   0.4.4.5 — бронебойно-экспансивные
#   0.4.4.6 — Группировка по калибрам
#   0.4.4.7 — defer() в on_submit
#   0.4.6.2 — Категории калибров (пистолетные, промежуточные, винтовочные,
#             крупнокалиберные, дробовые, спец)

import discord
import uuid

from .helpers import (
    game_manager, save_player, get_trade_discount,
    get_weapon, get_ammo_type, get_caliber_ammo_types
)
from ..weapon_system import get_ammo_price, is_spec_weapon
from config.map_config import BALANCE, AMMO
from utils.logger import get_logger

logger = get_logger()

MAX_AMMO_PURCHASE = BALANCE.get('items', {}).get('ammo_max_purchase', 300)


# ==================== КАТЕГОРИИ КАЛИБРОВ ====================

CALIBER_CATEGORIES = {
    "pistol": {
        "name": "🔫 Пистолетные",
        "description": "9x18, 9x19, .44 Магнум",
        "calibers": ["9x18", "9x19", ".44 Магнум"],
    },
    "intermediate": {
        "name": "💥 Промежуточные",
        "description": "5.45x39, 9x39",
        "calibers": ["5.45x39", "9x39"],
    },
    "rifle": {
        "name": "🎯 Винтовочные",
        "description": "7.62x39, 7.62x54R",
        "calibers": ["7.62x39", "7.62x54R"],
    },
    "heavy": {
        "name": "💀 Крупнокалиберные",
        "description": "12.7x108",
        "calibers": ["12.7x108"],
    },
    "shotgun": {
        "name": "🔫 Дробовые",
        "description": "12x70, 23x75",
        "calibers": ["12x70", "23x75"],
    },
    "special": {
        "name": "💣 Специальные",
        "description": "40 мм",
        "calibers": ["40 мм"],
    },
}


# ==================== МОДАЛКА ПОКУПКИ ====================

class AmmoPurchaseModal(discord.ui.Modal):
    quantity = discord.ui.TextInput(
        label=f"Количество (макс. {MAX_AMMO_PURCHASE})",
        placeholder=f"Введите число от 1 до {MAX_AMMO_PURCHASE}...",
        min_length=1,
        max_length=3,
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, player, ammo_type: str, price_per_unit: int, caliber: str, caliber_name: str):
        super().__init__(title=f"🎯 Покупка: {ammo_type} {caliber_name}"[:45])
        self.player = player
        self.ammo_type = ammo_type
        self.price_per_unit = price_per_unit
        self.caliber = caliber
        self.caliber_name = caliber_name

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.errors.NotFound:
            logger.warning("⚠️ AmmoPurchaseModal: interaction истёк")
            return
        except discord.errors.InteractionResponded:
            pass
        except Exception as e:
            logger.error(f"❌ AmmoPurchaseModal.defer: {e}")
            return

        try:
            if interaction.user.id != self.player.user_id:
                await interaction.followup.send("❌ Не ваш инвентарь!", ephemeral=True)
                return

            try:
                count = int(self.quantity.value.strip())
            except ValueError:
                await interaction.followup.send("❌ Введите целое число!", ephemeral=True)
                return

            if count <= 0:
                await interaction.followup.send("❌ Число должно быть больше 0!", ephemeral=True)
                return

            if count > MAX_AMMO_PURCHASE:
                await interaction.followup.send(
                    f"❌ Максимум {MAX_AMMO_PURCHASE} патронов за раз!",
                    ephemeral=True
                )
                return

            # 0.4.8: скидка фракции
            from ..factions import get_station_discount
            faction_discount = get_station_discount(self.player, self.player.location)
            total_price = int(self.price_per_unit * faction_discount) * count

            if self.player.inventory['никели'] < total_price:
                await interaction.followup.send(
                    f"❌ Нужно **{total_price}** никелей (у вас: {self.player.inventory['никели']})!",
                    ephemeral=True
                )
                return

            # 0.4.6.3: сохраняем по ключу '<caliber>|<ammo_type>'
            from ..weapon_system.ammo import make_ammo_key
            ammo_key = make_ammo_key(self.caliber, self.ammo_type)

            self.player.inventory['никели'] -= total_price
            self.player.inventory[ammo_key] = self.player.inventory.get(ammo_key, 0) + count
            await save_player(self.player)

            ammo = get_ammo_type(self.ammo_type)
            ammo_name = ammo.get('name', self.ammo_type) if ammo else self.ammo_type
            ammo_emoji = ammo.get('emoji', '🔘') if ammo else '🔘'

            embed = discord.Embed(
                title="✅ Покупка завершена",
                description=f"Куплено **{count}** {ammo_emoji} **{ammo_name}** ({self.caliber_name})",
                color=discord.Color.green()
            )
            embed.add_field(
                name="💰 Стоимость",
                value=f"{self.price_per_unit} × {count} = **{total_price}** никелей",
                inline=False
            )
            embed.add_field(
                name="💳 Остаток никелей",
                value=f"**{self.player.inventory['никели']}**",
                inline=False
            )
            from ..weapon_system.ammo import make_ammo_key
            ammo_key = make_ammo_key(self.caliber, self.ammo_type)
            embed.add_field(
                name="📦 Теперь патронов этого типа",
                value=f"**{self.player.inventory.get(ammo_key, 0)}** шт.",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ Ошибка в AmmoPurchaseModal.on_submit: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                await interaction.followup.send(f"❌ Ошибка: {str(e)}", ephemeral=True)
            except:
                pass


# ==================== МЕНЮ КАТЕГОРИЙ ====================

class AmmoCategoriesMenu(discord.ui.View):
    """0.4.6.2: главное меню — категории калибров."""

    def __init__(self, player):
        super().__init__(timeout=180)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    @staticmethod
    def build_embed(player) -> discord.Embed:
        embed = discord.Embed(
            title="🎯 Патроны — категории",
            description=(
                "**Все патроны имеют калибр.** Заряжать можно только патроны того калибра, "
                "который подходит магазину.\n\nВыберите категорию:"
            ),
            color=discord.Color.blue()
        )

        for cat_id, cat in CALIBER_CATEGORIES.items():
            lines = []
            for cal_id in cat["calibers"]:
                cal_data = AMMO.get('calibers', {}).get(cal_id, {})
                if not cal_data:
                    continue
                types_count = len(cal_data.get('types', []))
                lines.append(f"• {cal_data.get('name', cal_id)} — {types_count} тип(ов)")
            if lines:
                embed.add_field(
                    name=cat["name"],
                    value=f"_{cat['description']}_\n" + "\n".join(lines),
                    inline=False
                )

        embed.set_footer(text=f"💰 Ваши никели: {player.inventory.get('никели', 0)}")
        return embed

    def _add_buttons(self):
        for idx, (cat_id, cat) in enumerate(CALIBER_CATEGORIES.items()):
            # Проверяем, есть ли хоть один калибр с типами
            has_any = False
            for cal_id in cat["calibers"]:
                cal_data = AMMO.get('calibers', {}).get(cal_id, {})
                if cal_data and cal_data.get('types'):
                    has_any = True
                    break
            if not has_any:
                continue

            btn = discord.ui.Button(
                label=f"{cat['name']}"[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"ammo_cat_{self.menu_id}_{idx}",
                row=idx // 3
            )
            btn.callback = self.create_category_callback(cat_id)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"ammo_cat_back_{self.menu_id}",
            row=4
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_category_callback(self, category_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                    return

                if not interaction.response.is_done():
                    await interaction.response.defer()

                embed = AmmoCalibersMenu.build_embed(self.player, category_id)
                view = AmmoCalibersMenu(self.player, category_id)

                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка edit (category {category_id}): {e}")

            except discord.errors.NotFound:
                logger.warning("⚠️ Interaction истёк (category callback)")
            except Exception as e:
                logger.error(f"❌ Ошибка в category callback ({category_id}): {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.errors.NotFound:
            return

        embed = discord.Embed(title="🔫 Оружейный магазин", description="Выберите раздел:", color=discord.Color.blue())
        embed.add_field(
            name="📋 Доступные разделы",
            value="• 🔫 **Оружие**\n• 📀 **Магазины**\n• 🎯 **Патроны**\n• 🔧 **Модификации**\n• 🗡️ **Ближний бой**\n• 💣 **Расходники**",
            inline=False
        )
        from .weapon_shop import WeaponShopMainMenu
        view = WeaponShopMainMenu(self.player)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            pass


# ==================== МЕНЮ КАЛИБРОВ В КАТЕГОРИИ ====================

class AmmoCalibersMenu(discord.ui.View):
    """Список калибров внутри выбранной категории."""

    def __init__(self, player, category_id: str):
        super().__init__(timeout=180)
        self.player = player
        self.category_id = category_id
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    @staticmethod
    def build_embed(player, category_id: str) -> discord.Embed:
        cat = CALIBER_CATEGORIES.get(category_id, {})
        embed = discord.Embed(
            title=f"🎯 Патроны — {cat.get('name', category_id)}",
            description=f"_{cat.get('description', '')}_\n\nВыберите калибр:",
            color=discord.Color.blue()
        )

        for cal_id in cat.get('calibers', []):
            cal_data = AMMO.get('calibers', {}).get(cal_id, {})
            if not cal_data or not cal_data.get('types'):
                continue

            lines = []
            from ..weapon_system.ammo import make_ammo_key
            for t in cal_data['types']:
                ammo_data = get_ammo_type(t)
                if not ammo_data:
                    continue
                price = get_ammo_price(t, cal_id)
                have = player.inventory.get(make_ammo_key(cal_id, t), 0)
                lines.append(
                    f"{ammo_data.get('emoji', '🔘')} {ammo_data.get('name', t)} — "
                    f"{price} ник./шт | у вас: {have}"
                )

            embed.add_field(
                name=f"📦 {cal_data.get('name', cal_id)} (`{cal_id}`)",
                value="\n".join(lines),
                inline=False
            )

        embed.set_footer(text=f"💰 Ваши никели: {player.inventory.get('никели', 0)}")
        return embed

    def _add_buttons(self):
        cat = CALIBER_CATEGORIES.get(self.category_id, {})
        idx = 0
        for cal_id in cat.get('calibers', []):
            cal_data = AMMO.get('calibers', {}).get(cal_id, {})
            if not cal_data or not cal_data.get('types'):
                continue
            btn = discord.ui.Button(
                label=f"📦 {cal_data.get('name', cal_id)}"[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"ammo_cal_{self.menu_id}_{idx}",
                row=idx // 3
            )
            btn.callback = self.create_caliber_callback(cal_id)
            self.add_item(btn)
            idx += 1

        back_btn = discord.ui.Button(
            label="🔙 К категориям",
            style=discord.ButtonStyle.secondary,
            custom_id=f"ammo_cal_back_{self.menu_id}",
            row=4
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_caliber_callback(self, caliber: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                    return

                if not interaction.response.is_done():
                    await interaction.response.defer()

                embed = AmmoTypesMenu.build_embed(self.player, caliber)
                view = AmmoTypesMenu(self.player, caliber)

                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"Ошибка edit (caliber {caliber}): {e}")

            except discord.errors.NotFound:
                logger.warning("⚠️ Interaction истёк (caliber callback)")
            except Exception as e:
                logger.error(f"❌ Ошибка в caliber callback ({caliber}): {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.errors.NotFound:
            return

        embed = AmmoCategoriesMenu.build_embed(self.player)
        view = AmmoCategoriesMenu(self.player)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            pass


# ==================== МЕНЮ ТИПОВ ПАТРОНОВ ====================

class AmmoTypesMenu(discord.ui.View):
    """Список типов патронов для выбранного калибра."""

    def __init__(self, player, caliber: str):
        super().__init__(timeout=120)
        self.player = player
        self.caliber = caliber
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    @staticmethod
    def build_embed(player, caliber: str) -> discord.Embed:
        cal_data = AMMO.get('calibers', {}).get(caliber, {})
        cal_name = cal_data.get('name', caliber)
        types = cal_data.get('types', [])

        discount = get_trade_discount(game_manager)
        # 0.4.8: скидка фракции
        try:
            from ..factions import get_station_discount
            from ...game_manager import game_manager as _gm
            _player = _gm.get_player(player.user_id) if hasattr(player, 'user_id') else None
            if _player:
                discount = discount * get_station_discount(_player, _player.location)
        except Exception:
            pass

        embed = discord.Embed(
            title=f"🎯 Патроны — {cal_name}"[:256],
            description=f"Выберите тип патронов калибра **{cal_name}**:",
            color=discord.Color.blue()
        )

        from ..weapon_system.ammo import make_ammo_key
        for t in types:
            ammo = get_ammo_type(t)
            if not ammo:
                continue
            base_price = get_ammo_price(t, caliber)
            price = int(base_price * discount)
            have = player.inventory.get(make_ammo_key(caliber, t), 0)

            embed.add_field(
                name=f"{ammo.get('emoji', '🔘')} {ammo.get('name', t)}",
                value=(
                    f"{ammo.get('description', '')}\n"
                    f"📊 Множитель: ×{ammo.get('multiplier', 1)}\n"
                    f"💰 Цена: **{price}** никелей/шт | 📦 У вас: **{have}**"
                ),
                inline=False
            )

        embed.set_footer(text=f"💰 Ваши никели: {player.inventory.get('никели', 0)}")
        return embed

    def _add_buttons(self):
        cal_data = AMMO.get('calibers', {}).get(self.caliber, {})
        types = cal_data.get('types', [])

        for idx, t in enumerate(types):
            ammo = get_ammo_type(t)
            if not ammo:
                continue
            btn = discord.ui.Button(
                label=f"{ammo.get('emoji', '🔘')} {ammo.get('name', t)}"[:80],
                style=discord.ButtonStyle.success,
                custom_id=f"ammo_type_{self.menu_id}_{idx}",
                row=idx // 2
            )
            btn.callback = self.create_buy_callback(t)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 К калибрам",
            style=discord.ButtonStyle.secondary,
            custom_id=f"ammo_type_back_{self.menu_id}",
            row=3
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_buy_callback(self, ammo_type: str):
        async def callback(interaction: discord.Interaction):
            logger.info(f"🎯 AmmoTypesMenu: покупка ammo_type={ammo_type}, caliber={self.caliber}")
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                    return

                if interaction.response.is_done():
                    logger.warning("⚠️ Interaction уже отвечен, пропускаем открытие модалки")
                    return

                discount = get_trade_discount(game_manager)
                base_price = get_ammo_price(ammo_type, self.caliber)
                price = int(base_price * discount)

                cal_data = AMMO.get('calibers', {}).get(self.caliber, {})
                cal_name = cal_data.get('name', self.caliber)

                modal = AmmoPurchaseModal(self.player, ammo_type, price, self.caliber, cal_name)
                await interaction.response.send_modal(modal)
                logger.info(f"✅ Модалка открыта: {ammo_type} {cal_name} по {price}/шт")

            except discord.errors.NotFound:
                logger.warning(f"⚠️ Interaction истёк (buy_callback, {ammo_type})")
            except Exception as e:
                logger.error(f"❌ Ошибка в buy_callback ({ammo_type}): {e}")
                import traceback
                logger.error(traceback.format_exc())
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(f"❌ Ошибка: {str(e)}", ephemeral=True)
                    else:
                        await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
                except:
                    pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.errors.NotFound:
            return

        # Возврат к списку калибров той же категории
        cal_data = AMMO.get('calibers', {}).get(self.caliber, {})
        # Ищем категорию
        category_id = None
        for cat_id, cat in CALIBER_CATEGORIES.items():
            if self.caliber in cat.get('calibers', []):
                category_id = cat_id
                break

        if category_id:
            embed = AmmoCalibersMenu.build_embed(self.player, category_id)
            view = AmmoCalibersMenu(self.player, category_id)
        else:
            embed = AmmoCategoriesMenu.build_embed(self.player)
            view = AmmoCategoriesMenu(self.player)

        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            pass


# ==================== СОВМЕСТИМОСТЬ ====================

class AmmoBuyMenu(discord.ui.View):
    """Совместимость: старое имя AmmoBuyMenu = AmmoCategoriesMenu."""
    def __new__(cls, player):
        return AmmoCategoriesMenu(player)