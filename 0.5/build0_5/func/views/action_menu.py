# -*- coding: utf-8 -*-
# func/views/action_menu.py - Меню действий (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.8.3 — Кнопка NPC перенесена в Главное меню.
#   0.4.8.6 — ФИКС: Аспирин — edit_original_response после defer.
#   0.4.8.7 — Кнопка «Активированный уголь» (-20 химии) в медикаментах.

import discord
import uuid
from .helpers import (
    game_manager, MAP_DATA, save_player, combat_manager,
    WEAPONS, get_current_filter_info
)
from .gas_mask import GasMaskMenu
from .equipment import EquipmentMenu
from .armor_manage import ArmorManageMenu
from ..weapon_system import (
    get_weapon, get_magazine, get_current_ammo, get_weapon_max_ammo
)
from ..melee_system import get_melee_weapon
from ..food_system import get_food
from ..social.sleep import can_sleep, start_sleep, is_safe_station
from ..social.brigade_manager import brigade_manager
from utils.logger import get_logger
from utils.autosave import autosaver

logger = get_logger()


class ActionMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    def _build_status_text(self, player) -> str:
        total_hp = player.get_total_health()
        max_hp = player.get_max_total_health()

        parts = []
        for part_id, part_data in player.body_parts.items():
            hp = part_data.get('hp', 0)
            max_part = part_data.get('max_hp', 0)
            name = part_data.get('name', part_id)
            if hp <= 0:
                parts.append(f"💀 {name}")
            elif hp <= max_part * 0.3:
                parts.append(f"🟡 {name}: {hp:.1f}/{max_part:.1f}")
            else:
                parts.append(f"🟢 {name}: {hp:.1f}/{max_part:.1f}")

        text = f"❤️ **Здоровье:** {total_hp:.1f}/{max_hp:.1f}\n"
        text += "\n".join(parts) + "\n"
        text += f"\n🏃 **Выносливость:** {player.stamina:.1f}/{player.max_stamina}"

        from ..disease_system import ensure_disease_fields
        from ..cold_system import ensure_cold_fields
        ensure_disease_fields(player)
        ensure_cold_fields(player)

        if player.radiation > 0 or player.chemical > 0:
            text += (
                f"\n☢️ Радиация: {player.radiation:.0f}/100 | "
                f"☣️ Химия: {player.chemical:.0f}/100"
            )

        if player.cold > 0:
            text += f"\n❄️ Замерзание: {player.cold:.0f}/100"

        if player.diseases:
            text += f"\n💀 Болезни: {len(player.diseases)}"

        return text

    @discord.ui.button(label="Аптечка", emoji="💊",
                       style=discord.ButtonStyle.success, row=0)
    async def heal_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player or not player.is_alive:
            return

        from ..pharmacy_system import get_available_medkits
        from ..disease_system import ensure_disease_fields
        available = get_available_medkits(player)
        ensure_disease_fields(player)

        has_antirad = (
                player.inventory.get('антирад', 0) > 0 and player.radiation > 0
        )
        has_aspirin = (
                player.inventory.get('аспирин', 0) > 0
                and 'простуда' in player.diseases
        )
        # 0.4.8.7: активированный уголь
        has_charcoal = (
                player.inventory.get('активированный_уголь', 0) > 0
                and player.chemical > 0
        )

        if not available and not has_antirad and not has_aspirin and not has_charcoal:
            await interaction.response.send_message(
                "❌ У вас нет медикаментов!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="💊 Медикаменты",
            description=(
                f"❤️ Здоровье: **{player.get_total_health():.1f}/"
                f"{player.get_max_total_health():.1f}**\n"
                f"☢️ Радиация: **{player.radiation:.0f}/100**\n"
                f"☣️ Химия: **{player.chemical:.0f}/100**\n\n"
                f"Выберите:"
            ),
            color=discord.Color.green()
        )
        for entry in available:
            embed.add_field(
                name=f"{entry['data'].get('emoji', '💊')} "
                     f"{entry['data'].get('name')} (x{entry['count']})",
                value=f"+{entry['data'].get('heal')} HP",
                inline=True
            )
        if has_antirad:
            embed.add_field(
                name=f"💉 Антирад (x{player.inventory['антирад']})",
                value="-50 радиации",
                inline=True
            )
        if has_aspirin:
            embed.add_field(
                name=f"💊 Аспирин (x{player.inventory['аспирин']})",
                value="Лечит простуду",
                inline=True
            )
        if has_charcoal:
            embed.add_field(
                name=f"⚫ Уголь (x{player.inventory['активированный_уголь']})",
                value="-20 химии",
                inline=True
            )

        from .action_menu import _MedkitSelectMenu
        await interaction.response.edit_message(
            embed=embed, view=_MedkitSelectMenu(player)
        )

    @discord.ui.button(label="Еда", emoji="🍖",
                       style=discord.ButtonStyle.success, row=0)
    async def food_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player or not player.is_alive:
            return

        embed = discord.Embed(
            title="🍖 Инвентарь еды", color=discord.Color.green()
        )
        if not player.food_inventory:
            embed.add_field(
                name="❌ Нет еды", value="Купите в торговой зоне.",
                inline=False
            )
            from .food import FoodEmptyMenu
            view = FoodEmptyMenu()
        else:
            food_counts = {}
            for food_id in player.food_inventory:
                food_counts[food_id] = food_counts.get(food_id, 0) + 1
            for food_id, count in food_counts.items():
                food = get_food(food_id)
                if food:
                    embed.add_field(
                        name=f"{food.get('emoji')} {food.get('name')}",
                        value=f"Количество: {count}",
                        inline=True
                    )
            from .food import FoodMenu
            view = FoodMenu(player)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Противогаз", emoji="🎒",
                       style=discord.ButtonStyle.primary, row=1)
    async def gas_mask_button(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player or not player.is_alive:
            return
        embed = discord.Embed(
            title="🎒 Управление противогазом", color=discord.Color.blue()
        )
        mask_status = {
            "целый": "🟢 Целый",
            "поношенный": "🟡 Поношенный",
            "разбитый": "🔴 Разбитый"
        }
        status = mask_status.get(
            player.gas_mask.get("состояние", "поношенный"), "❓"
        )
        worn = "✅ Надет" if player.gas_mask.get("надет", False) else "❌ Снят"
        current_filter = get_current_filter_info(player)
        filter_status = (
            "✅ Вставлен"
            if current_filter["has_filter"] and not current_filter["is_expired"]
            else "❌ Не вставлен"
        )
        if current_filter["has_filter"]:
            filter_status += (
                f" ({current_filter['filter_name']}, "
                f"{current_filter['current_durability']:.1f})"
            )
        embed.add_field(
            name="📊 Состояние",
            value=(
                f"Состояние: {status}\n"
                f"Прочность: {player.gas_mask.get('прочность', 0):.0f}/"
                f"{player.get_gas_mask_max_durability()}\n"
                f"Надет: {worn}\nФильтр: {filter_status}"
            ),
            inline=False
        )
        await interaction.response.edit_message(
            embed=embed, view=GasMaskMenu()
        )

    @discord.ui.button(label="Броня", emoji="🧥",
                       style=discord.ButtonStyle.primary, row=1)
    async def armor_button(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player or not player.is_alive:
            return
        from ..armor_system import format_armor_status, get_armor_item
        embed = discord.Embed(
            title="🧥 Снаряжение",
            description="Управление бронёй и шлемом",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📦 Надето", value=format_armor_status(player), inline=False
        )
        inv = player.armor_inventory
        if inv:
            lines = [
                f"{'🧥' if get_armor_item(i).get('slot')=='armor' else '⛑️'} "
                f"{get_armor_item(i).get('name', i)}"
                for i in inv[:10] if get_armor_item(i)
            ]
            embed.add_field(
                name=f"🎒 В рюкзаке ({len(inv)})",
                value="\n".join(lines),
                inline=False
            )
        else:
            embed.add_field(name="🎒 В рюкзаке", value="Пусто", inline=False)
        await interaction.response.edit_message(
            embed=embed, view=ArmorManageMenu(player)
        )

    @discord.ui.button(label="Снаряжение", emoji="🔧",
                       style=discord.ButtonStyle.primary, row=1)
    async def equipment_button(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player or not player.is_alive:
            return
        from config.map_config import MODULES
        embed = discord.Embed(
            title="🔧 Снаряжение", color=discord.Color.blue()
        )
        current_weapon = WEAPONS.get(player.weapon, {})
        embed.add_field(
            name="🔫 Текущее оружие",
            value=f"{current_weapon.get('emoji')} "
                  f"**{current_weapon.get('name', 'Нет')}**",
            inline=False
        )
        current_ammo = get_current_ammo(player.weapon, player)
        max_ammo = get_weapon_max_ammo(player.weapon, player)
        embed.add_field(
            name="🎯 Патроны", value=f"{current_ammo}/{max_ammo}",
            inline=False
        )
        modules_text = ""
        for slot_id, slot_data in MODULES.get('slots', {}).items():
            module_id = player.equipped_modules.get(slot_id)
            if module_id:
                module_data = MODULES['modules'].get(module_id, {})
                modules_text += (
                    f"{slot_data.get('emoji')} {slot_data.get('name')}: "
                    f"{module_data.get('emoji')} {module_data.get('name')}\n"
                )
            else:
                modules_text += (
                    f"{slot_data.get('emoji')} {slot_data.get('name')}: ❌\n"
                )
        embed.add_field(name="🔧 Модули", value=modules_text, inline=False)
        await interaction.response.edit_message(
            embed=embed, view=EquipmentMenu(player)
        )

    @discord.ui.button(label="Сон", emoji="😴",
                       style=discord.ButtonStyle.primary, row=1)
    async def sleep_button(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player or not player.is_alive:
            return
        ok, reason = can_sleep(player)
        if not ok:
            await interaction.response.send_message(reason, ephemeral=True)
            return
        await interaction.response.defer()
        result = await start_sleep(player)
        from .social.sleep_view import SleepingMenuView, build_sleeping_embed
        embed = build_sleeping_embed(player)
        embed.add_field(name="ℹ️", value=result, inline=False)
        await interaction.edit_original_response(
            embed=embed, view=SleepingMenuView(player.user_id)
        )

    @discord.ui.button(label="Мастерить", emoji="🔨",
                       style=discord.ButtonStyle.success, row=2)
    async def repair_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player or not player.is_alive:
            return
        from .repair_view import RepairMenu
        view = RepairMenu(player)
        await interaction.response.edit_message(
            embed=view._build_embed(), view=view
        )

    @discord.ui.button(label="Журнал", emoji="📓",
                       style=discord.ButtonStyle.primary, row=2)
    async def journal_button(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player or not player.is_alive:
            return
        from .faction_npc.journal_view import JournalView, build_journal_embed
        await interaction.response.edit_message(
            embed=build_journal_embed(player), view=JournalView(player)
        )

    @discord.ui.button(label="Назад", emoji="🔙",
                       style=discord.ButtonStyle.secondary, row=2)
    async def back_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        player = game_manager.get_player(interaction.user.id)
        if not player:
            return
        station_data = MAP_DATA["станции"][player.location]
        embed = discord.Embed(
            title="🎮 Меню 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
            description=f"Добро пожаловать, **{player.name}**!\n"
                        f"Уровень: **{player.level}**",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="❤️ Здоровье",
            value=f"{player.get_total_health():.1f}/"
                  f"{player.get_max_total_health():.1f}",
            inline=True
        )
        embed.add_field(
            name="🏃 Выносливость",
            value=f"{player.stamina:.1f}/{player.max_stamina}",
            inline=True
        )
        embed.add_field(
            name="📍 Локация", value=station_data["name"], inline=True
        )
        embed.add_field(
            name="💰 Никели", value=player.inventory.get('никели', 0),
            inline=True
        )
        from .main_menu import MainMenu
        await interaction.response.edit_message(
            embed=embed, view=MainMenu(player)
        )


# ==================== ПОДМЕНЮ МЕДИКАМЕНТОВ ====================

class _MedkitSelectMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        from ..pharmacy_system import get_available_medkits
        from ..disease_system import ensure_disease_fields
        ensure_disease_fields(self.player)
        available = get_available_medkits(self.player)

        for idx, entry in enumerate(available[:5]):
            item, item_id, count = entry['data'], entry['item_id'], entry['count']
            label = f"{item.get('name', item_id)} ({count})"
            btn = discord.ui.Button(
                label=label[:80], emoji=item.get('emoji', '💊'),
                style=discord.ButtonStyle.success,
                custom_id=f"mk_use_{self.menu_id}_{idx}"
            )
            btn.callback = self.create_use_callback(item_id)
            self.add_item(btn)

        if self.player.inventory.get('антирад', 0) > 0 and self.player.radiation > 0:
            btn = discord.ui.Button(
                label=f"Антирад ({self.player.inventory['антирад']})",
                emoji="💉", style=discord.ButtonStyle.primary,
                custom_id=f"mk_antirad_{self.menu_id}"
            )
            btn.callback = self.create_antirad_callback()
            self.add_item(btn)

        # 0.4.8.7: активированный уголь
        if self.player.inventory.get('активированный_уголь', 0) > 0 \
                and self.player.chemical > 0:
            btn = discord.ui.Button(
                label=f"Уголь ({self.player.inventory['активированный_уголь']})",
                emoji="⚫", style=discord.ButtonStyle.primary,
                custom_id=f"mk_charcoal_{self.menu_id}"
            )
            btn.callback = self.create_charcoal_callback()
            self.add_item(btn)

        if self.player.inventory.get('аспирин', 0) > 0 \
                and 'простуда' in getattr(self.player, 'diseases', []):
            btn = discord.ui.Button(
                label=f"Аспирин ({self.player.inventory['аспирин']})",
                emoji="💊", style=discord.ButtonStyle.danger,
                custom_id=f"mk_aspirin_{self.menu_id}"
            )
            btn.callback = self.create_aspirin_callback()
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="Назад", emoji="🔙", style=discord.ButtonStyle.danger,
            custom_id=f"mk_back_{self.menu_id}"
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_use_callback(self, item_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return
            if not interaction.response.is_done():
                await interaction.response.defer()
            from ..pharmacy_system import use_medkit
            result = use_medkit(self.player, item_id)
            autosaver.mark_dirty(self.player)
            embed = discord.Embed(
                title="✅ Использовано" if result.get('success') else "❌ Ошибка",
                description=result.get('message', ''),
                color=discord.Color.green() if result.get('success') else discord.Color.red()
            )
            embed.add_field(
                name="❤️ Здоровье",
                value=f"{self.player.get_total_health():.1f}/"
                      f"{self.player.get_max_total_health():.1f}",
                inline=True
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, view=_MedkitSelectMenu(self.player)
                )
            except Exception as e:
                logger.error(f"use_medkit edit: {e}")

        return callback

    def create_antirad_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return
            if not interaction.response.is_done():
                await interaction.response.defer()
            from ..pharmacy_system import use_antirad
            result = use_antirad(self.player)
            autosaver.mark_dirty(self.player)
            embed = discord.Embed(
                title="✅ Использовано",
                description=result.get('message', ''),
                color=discord.Color.green()
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, view=_MedkitSelectMenu(self.player)
                )
            except Exception as e:
                logger.error(f"antirad edit: {e}")

        return callback

    # 0.4.8.7: обработчик угля
    def create_charcoal_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return
            if not interaction.response.is_done():
                try:
                    await interaction.response.defer()
                except Exception:
                    pass

            from ..pharmacy_system import use_activated_charcoal
            result = use_activated_charcoal(self.player)
            autosaver.mark_dirty(self.player)

            embed = discord.Embed(
                title="✅ Использовано" if result.get('success') else "❌ Ошибка",
                description=result.get('message', ''),
                color=discord.Color.green() if result.get('success') else discord.Color.red()
            )
            embed.add_field(
                name="☣️ Химия",
                value=f"{self.player.chemical:.0f}/100",
                inline=True
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, view=_MedkitSelectMenu(self.player)
                )
            except Exception as e:
                logger.error(f"charcoal edit: {e}")

        return callback

    def create_aspirin_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return
            if not interaction.response.is_done():
                try:
                    await interaction.response.defer()
                except Exception:
                    pass

            from ..pharmacy_system import use_aspirin
            result = use_aspirin(self.player)
            autosaver.mark_dirty(self.player)

            embed = discord.Embed(
                title="✅ Вылечено" if result.get('success') else "❌ Ошибка",
                description=result.get('message', ''),
                color=discord.Color.green() if result.get('success') else discord.Color.red()
            )
            try:
                await interaction.edit_original_response(
                    embed=embed, view=ActionMenu()
                )
            except Exception as e:
                logger.error(f"aspirin edit: {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎯 Действия",
            description="Выберите действие:",
            color=discord.Color.blue()
        )
        try:
            await interaction.response.edit_message(
                embed=embed, view=ActionMenu()
            )
        except Exception as e:
            logger.error(f"back (medkit): {e}")