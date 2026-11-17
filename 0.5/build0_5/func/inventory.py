# -*- coding: utf-8 -*-
# func/inventory.py - Система инвентаря (0.4.8.3)
#
# ИСТОРИЯ:
#   0.4.8.3 — Рюкзак разбит на вкладки.
#             ФИКС: кнопка "Закрыть" возвращает в Главное меню.

import discord
import uuid
from config.map_config import WEAPONS, ITEMS, AMMO, ARMOR
from .weapon_system import (
    get_magazine, get_current_ammo, get_weapon_max_ammo,
    is_shell_loaded_weapon, get_weapon
)
from .weapon_system.ammo import make_ammo_key
from .filter_system import get_filter, get_current_filter_info
from .melee_system import get_melee_weapon
from .food_system import get_food
from .armor_system import get_armor_item, get_item_durability
from .disease_system import ensure_disease_fields
from .cold_system import ensure_cold_fields
from utils.calculations import calculate_xp_to_level
from utils.logger import get_logger

logger = get_logger()


class InventoryView(discord.ui.View):
    """Интерактивный рюкзак с вкладками."""
    def __init__(self, player, page: str = "main"):
        super().__init__(timeout=180)
        self.player = player
        self.page = page
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        self.clear_items()

        if self.page == "main":
            # Ряд 0: Основное
            btn1 = discord.ui.Button(label="Оружие", emoji="🔫", style=discord.ButtonStyle.primary, row=0)
            btn1.callback = self.create_nav_callback("weapon")
            self.add_item(btn1)

            btn2 = discord.ui.Button(label="Броня", emoji="🧥", style=discord.ButtonStyle.primary, row=0)
            btn2.callback = self.create_nav_callback("armor")
            self.add_item(btn2)

            btn3 = discord.ui.Button(label="Медикаменты", emoji="💊", style=discord.ButtonStyle.success, row=0)
            btn3.callback = self.create_nav_callback("meds")
            self.add_item(btn3)

            # Ряд 1: Расходники
            btn4 = discord.ui.Button(label="Еда", emoji="🍖", style=discord.ButtonStyle.success, row=1)
            btn4.callback = self.create_nav_callback("food")
            self.add_item(btn4)

            btn5 = discord.ui.Button(label="Маска/Фильтры", emoji="🎒", style=discord.ButtonStyle.secondary, row=1)
            btn5.callback = self.create_nav_callback("mask")
            self.add_item(btn5)

            btn6 = discord.ui.Button(label="Патроны", emoji="🎯", style=discord.ButtonStyle.secondary, row=1)
            btn6.callback = self.create_nav_callback("ammo")
            self.add_item(btn6)

            # Ряд 2: Разное
            btn7 = discord.ui.Button(label="Хлам/Лут", emoji="📦", style=discord.ButtonStyle.secondary, row=2)
            btn7.callback = self.create_nav_callback("loot")
            self.add_item(btn7)

            btn8 = discord.ui.Button(label="Статус/Инфо", emoji="📊", style=discord.ButtonStyle.secondary, row=2)
            btn8.callback = self.create_nav_callback("info")
            self.add_item(btn8)

            btn_close = discord.ui.Button(label="Закрыть", emoji="🔙", style=discord.ButtonStyle.danger, row=3)
            btn_close.callback = self.close_callback
            self.add_item(btn_close)

        else:
            # Кнопка Назад
            btn_back = discord.ui.Button(label="Назад в рюкзак", emoji="🔙", style=discord.ButtonStyle.danger, row=3)
            btn_back.callback = self.create_nav_callback("main")
            self.add_item(btn_back)

    def create_nav_callback(self, target_page: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            new_view = InventoryView(self.player, page=target_page)
            embed = new_view.build_embed()
            await interaction.response.edit_message(embed=embed, view=new_view)
        return callback

    async def close_callback(self, interaction: discord.Interaction):
        """Возврат в главное меню."""
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        from .views.main_menu import MainMenu, build_main_embed
        from .map_data import MAP_DATA

        station_data = MAP_DATA["станции"].get(self.player.location, {})
        embed = build_main_embed(self.player, station_data)

        await interaction.response.edit_message(embed=embed, view=MainMenu(self.player))

    def build_embed(self) -> discord.Embed:
        if self.page == "main":
            return self._build_main_embed()
        elif self.page == "weapon":
            return self._build_weapon_embed()
        elif self.page == "armor":
            return self._build_armor_embed()
        elif self.page == "meds":
            return self._build_meds_embed()
        elif self.page == "food":
            return self._build_food_embed()
        elif self.page == "mask":
            return self._build_mask_embed()
        elif self.page == "ammo":
            return self._build_ammo_embed()
        elif self.page == "loot":
            return self._build_loot_embed()
        elif self.page == "info":
            return self._build_info_embed()

        return discord.Embed(title="Ошибка", description="Страница не найдена", color=discord.Color.red())

    # ==================== СТРАНИЦЫ ====================

    def _build_main_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(
            title=f"🎒 Рюкзак: {p.name}",
            description=f"💰 **Никели:** {p.inventory.get('никели', 0)}\nВыберите категорию для просмотра:",
            color=discord.Color.blue()
        )

        # Оружие
        w = WEAPONS.get(p.weapon, {})
        ammo = get_current_ammo(p.weapon, p)
        max_ammo = get_weapon_max_ammo(p.weapon, p)
        embed.add_field(
            name="🔫 Текущее оружие",
            value=f"{w.get('emoji', '')} {w.get('name', 'Нет')} ({ammo}/{max_ammo})",
            inline=True
        )

        # Броня
        a_id = getattr(p, 'armor', None)
        a_name = get_armor_item(a_id).get('name', 'Нет') if a_id else "❌"
        embed.add_field(name="🧥 Броня", value=a_name, inline=True)

        # Противогаз
        mask_state = p.gas_mask.get("состояние", "поношенный")
        mask_dur = p.gas_mask.get("прочность", 0)
        embed.add_field(name="🎒 Противогаз", value=f"{mask_state.capitalize()} ({mask_dur:.0f})", inline=True)

        return embed

    def _build_weapon_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(title="🔫 Оружие и Ближний бой", color=discord.Color.blue())

        # Огнестрел
        w = WEAPONS.get(p.weapon, {})
        if is_shell_loaded_weapon(p.weapon):
            ammo = p.get_shell_ammo_count()
            max_ammo = p.get_weapon_shell_capacity()
            ammo_text = f"{ammo}/{max_ammo} (в стволе)"
        else:
            ammo = get_current_ammo(p.weapon, p)
            max_ammo = get_weapon_max_ammo(p.weapon, p)
            mag = p.get_equipped_magazine_obj()
            mag_name = get_magazine(mag['type_id']).get('name', '?') if mag else 'Нет'
            ammo_text = f"{ammo}/{max_ammo} ({mag_name})"

        embed.add_field(
            name="Текущее оружие",
            value=f"{w.get('emoji', '')} **{w.get('name', 'Нет')}**\nУрон: {w.get('damage', 0)} | {ammo_text}",
            inline=False
        )

        # Ближний бой
        m = get_melee_weapon(p.melee_weapon)
        embed.add_field(
            name="Ближний бой",
            value=f"{m.get('emoji', '')} **{m.get('name', 'Кулаки')}**\nУрон: {m.get('damage', 1.0)} | Прочность: {p.get_melee_weapon_durability_percent()}%",
            inline=False
        )

        # Резерв
        if p.weapons_inventory:
            res = [f"• {WEAPONS.get(wid, {}).get('name', wid)}" for wid in p.weapons_inventory]
            embed.add_field(name=f"В рюкзаке ({len(res)})", value="\n".join(res), inline=False)
        if p.melee_inventory:
            res = [f"• {get_melee_weapon(mid).get('name', mid)}" for mid in p.melee_inventory]
            embed.add_field(name=f"Ближний бой в рюкзаке ({len(res)})", value="\n".join(res), inline=False)

        return embed

    def _build_armor_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(title="🧥 Броня и Шлемы", color=discord.Color.blue())

        # Надето
        a_id = getattr(p, 'armor', None)
        h_id = getattr(p, 'helmet', None)

        if a_id:
            a = get_armor_item(a_id)
            dur = get_item_durability(p, a_id)
            embed.add_field(name="Надетая броня", value=f"{a.get('emoji', '')} **{a.get('name', '')}**\n❤️ {dur:.0f}/{a.get('max_durability', 100)}", inline=True)
        else:
            embed.add_field(name="Надетая броня", value="❌ Нет", inline=True)

        if h_id:
            h = get_armor_item(h_id)
            dur = get_item_durability(p, h_id)
            embed.add_field(name="Надетый шлем", value=f"{h.get('emoji', '')} **{h.get('name', '')}**\n❤️ {dur:.0f}/{h.get('max_durability', 100)}", inline=True)
        else:
            embed.add_field(name="Надетый шлем", value="❌ Нет", inline=True)

        # В рюкзаке
        if p.armor_inventory:
            lines = []
            for item_id in p.armor_inventory:
                item = get_armor_item(item_id)
                slot = "🧥" if item.get('slot') == 'armor' else "⛑️"
                lines.append(f"{slot} {item.get('name', item_id)}")
            embed.add_field(name=f"В рюкзаке ({len(lines)})", value="\n".join(lines[:10]), inline=False)

        return embed

    def _build_meds_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(title="💊 Медикаменты", color=discord.Color.green())

        items = []
        if p.inventory.get('мед_подсумок', 0) > 0: items.append(f"🧰 Мед. Подсумок: {p.inventory['мед_подсумок']}")
        if p.inventory.get('тактическая_аптечка', 0) > 0: items.append(f"🩹 Тактическая аптечка: {p.inventory['тактическая_аптечка']}")
        if p.inventory.get('аптечка_аи2', 0) > 0: items.append(f"💊 Аптечка АИ-2: {p.inventory['аптечка_аи2']}")
        if p.inventory.get('аптечка_аи4', 0) > 0: items.append(f"💉 Аптечка АИ-4: {p.inventory['аптечка_аи4']}")
        if p.inventory.get('антирад', 0) > 0: items.append(f"💉 Антирад: {p.inventory['антирад']}")
        if p.inventory.get('аспирин', 0) > 0: items.append(f"💊 Аспирин: {p.inventory['аспирин']}")

        if not items:
            embed.description = "У вас нет медикаментов."
        else:
            embed.description = "\n".join(items)

        return embed

    def _build_food_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(title="🍖 Еда", color=discord.Color.green())

        if not p.food_inventory:
            embed.description = "У вас нет еды."
        else:
            food_counts = {}
            for fid in p.food_inventory:
                food_counts[fid] = food_counts.get(fid, 0) + 1

            lines = []
            for fid, count in food_counts.items():
                f = get_food(fid)
                if f:
                    lines.append(f"{f.get('emoji', '🍖')} {f.get('name', fid)} ×{count} (+{f.get('stamina', 0)} вын.)")
            embed.description = "\n".join(lines)

        return embed

    def _build_mask_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(title="🎒 Противогаз и Фильтры", color=discord.Color.blue())

        m_status = {"целый": "🟢 Целый", "поношенный": "🟡 Поношенный", "разбитый": "🔴 Разбитый"}
        status = m_status.get(p.gas_mask.get("состояние", "поношенный"), "❓")
        worn = "✅ Надет" if p.gas_mask.get("надет", False) else "❌ Снят"

        embed.add_field(
            name="Состояние маски",
            value=f"{status}\nНадет: {worn}\nПрочность: {p.gas_mask.get('прочность', 0):.0f}/{p.get_gas_mask_max_durability():.0f}",
            inline=False
        )

        cur_filter = get_current_filter_info(p)
        if cur_filter['has_filter']:
            f_text = f"{cur_filter['filter_emoji']} {cur_filter['filter_name']} ({cur_filter['current_durability']:.1f})"
        else:
            f_text = "❌ Не установлен"
        embed.add_field(name="Текущий фильтр", value=f_text, inline=False)

        if p.filters:
            filter_counts = {}
            for fid in p.filters:
                filter_counts[fid] = filter_counts.get(fid, 0) + 1
            lines = [f"{get_filter(fid).get('emoji', '')} {get_filter(fid).get('name', fid)} ×{c}" for fid, c in filter_counts.items()]
            embed.add_field(name=f"Запасные фильтры ({len(p.filters)})", value="\n".join(lines), inline=False)

        return embed

    def _build_ammo_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(title="🎯 Патроны по калибрам", color=discord.Color.blue())

        lines = []
        for cal_id, cal_data in AMMO.get('calibers', {}).items():
            owned = []
            for t in cal_data.get('types', []):
                key = make_ammo_key(cal_id, t)
                count = p.inventory.get(key, 0)
                if count > 0:
                    ammo_data = AMMO.get('ammo_types', {}).get(t, {})
                    owned.append(f"{ammo_data.get('emoji', '🔘')} {ammo_data.get('name', t)}: {count}")

            if owned:
                lines.append(f"**{cal_data.get('name', cal_id)}**")
                lines.extend([f"   {o}" for o in owned])

        if not lines:
            embed.description = "У вас нет патронов."
        else:
            text = "\n".join(lines)
            if len(text) > 1024:
                text = text[:1020] + "..."
            embed.description = text

        # Гранаты и ножи
        throwables = []
        for gid, cnt in p.grenades_inventory.items():
            if cnt > 0:
                throwables.append(f"💣 {WEAPONS.get(gid, {}).get('name', gid)} ×{cnt}")
        for kid, cnt in p.throwing_knives_inventory.items():
            if cnt > 0:
                throwables.append(f"🔪 {WEAPONS.get(kid, {}).get('name', kid)} ×{cnt}")

        if throwables:
            embed.add_field(name="Метательное", value="\n".join(throwables), inline=False)

        return embed

    def _build_loot_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(title="📦 Хлам и Лут", color=discord.Color.dark_gray())

        hlam = p.inventory.get("хлам", [])
        if not hlam:
            embed.description = "У вас нет хлама."
        else:
            sell_items = ITEMS.get('sell', {})
            item_counts = {}
            for item in hlam:
                item_counts[item] = item_counts.get(item, 0) + 1

            lines = []
            for item_id, count in item_counts.items():
                data = sell_items.get(item_id, {})
                name = data.get('name', item_id)
                price = data.get('price', 0)
                lines.append(f"• {name} ×{count} ({price} ник.)")

            embed.description = "\n".join(lines)

        return embed

    def _build_info_embed(self) -> discord.Embed:
        p = self.player
        embed = discord.Embed(title="📊 Информация", color=discord.Color.gold())

        total_health = p.get_total_health()
        max_health = p.get_max_total_health()

        embed.add_field(name="❤️ Здоровье", value=f"{total_health:.1f}/{max_health:.1f}", inline=True)
        embed.add_field(name="🏃 Выносливость", value=f"{p.stamina:.1f}/{p.max_stamina}", inline=True)
        embed.add_field(name="⭐ Уровень", value=str(p.level), inline=True)

        ensure_disease_fields(p)
        ensure_cold_fields(p)

        status = []
        if p.radiation > 0: status.append(f"☢️ Радиация: {p.radiation:.0f}")
        if p.chemical > 0: status.append(f"☣️ Химия: {p.chemical:.0f}")
        if p.cold > 0: status.append(f"❄️ Холод: {p.cold:.0f}")
        if p.diseases: status.append(f"💀 Болезни: {len(p.diseases)}")

        embed.add_field(name="Состояние", value="\n".join(status) if status else "✅ Отлично", inline=False)

        return embed


def get_inventory_embed(player):
    """
    0.4.8.3: Возвращает (embed, view) для поддержки кнопок.
    """
    view = InventoryView(player, page="main")
    return view.build_embed(), view