# -*- coding: utf-8 -*-
# func/social/item_picker.py - UI-выбор предметов из инвентаря (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.7.2 — новый файл. Единый компонент выбора предметов кнопками
#             без знания ID.
#
# Используется в /deliver и /trade.
#
# Модель "описания предмета" (item descriptor) — словарь:
#   {"type": "weapon",  "id": "калаш_74"}
#   {"type": "melee",   "id": "сталкерский_нож"}
#   {"type": "armor",   "id": "броня_юг"}          # armor или helmet по slot
#   {"type": "module",  "id": "оптический_х2"}
#   {"type": "magazine","uid": "mag_5"}
#   {"type": "grenade", "id": "ргд_5",  "count": 1}
#   {"type": "knife",   "id": "кустарный_метательный_нож", "count": 1}
#   {"type": "food",    "id": "мясо_крысы", "count": 1}
#   {"type": "filter",  "id": "поношенный", "count": 1}
#   {"type": "inventory_key", "key": "аптечка_аи2", "count": 1}

import discord
import uuid

from ..game_manager import game_manager
from ..weapon_system import get_weapon, get_magazine
from ..melee_system import get_melee_weapon
from ..armor_system import get_armor_item
from ..food_system import get_food
from ..filter_system import get_filter
from config.map_config import MODULES, WEAPONS

from utils.logger import get_logger

logger = get_logger()


# ==================== КАТЕГОРИИ ====================

CATEGORIES = [
    {
        "id": "weapon",
        "name": "🔫 Оружие",
        "desc": "Огнестрельное оружие из инвентаря",
    },
    {
        "id": "melee",
        "name": "🗡️ Ближний бой",
        "desc": "Ножи, мачете, монтировки и т.д.",
    },
    {
        "id": "armor",
        "name": "🧥 Броня и шлемы",
        "desc": "Запасная экипировка",
    },
    {
        "id": "module",
        "name": "🔧 Модули",
        "desc": "Прицелы, рукояти, дуло",
    },
    {
        "id": "magazine",
        "name": "📀 Магазины",
        "desc": "Снаряжённые и пустые",
    },
    {
        "id": "throwable",
        "name": "💣 Гранаты и ножи",
        "desc": "Метательное оружие",
    },
    {
        "id": "consumable",
        "name": "💊 Расходники",
        "desc": "Аптечки, антирад, фильтры",
    },
    {
        "id": "food",
        "name": "🍖 Еда",
        "desc": "Продукты и грибы",
    },
]


def get_category_icon(cat_id: str) -> str:
    for c in CATEGORIES:
        if c["id"] == cat_id:
            return c["name"].split(" ", 1)[0]
    return "📦"


# ==================== СБОР ПРЕДМЕТОВ ПО КАТЕГОРИИ ====================

def get_items_in_category(player, category_id: str) -> list:
    """
    Возвращает список item-descriptor'ов в указанной категории.
    Фильтрует пустые / нулевые / надетые (их передавать нельзя).
    """
    result = []

    if category_id == "weapon":
        for wid in player.weapons_inventory:
            if wid == player.weapon:
                continue
            data = get_weapon(wid)
            if not data:
                continue
            result.append({
                "type": "weapon",
                "id": wid,
                "name": data.get("name", wid),
                "emoji": data.get("emoji", "🔫"),
            })

    elif category_id == "melee":
        for mid in player.melee_inventory:
            if mid == player.melee_weapon:
                continue
            data = get_melee_weapon(mid)
            if not data:
                continue
            result.append({
                "type": "melee",
                "id": mid,
                "name": data.get("name", mid),
                "emoji": data.get("emoji", "🗡️"),
            })

    elif category_id == "armor":
        for aid in player.armor_inventory:
            if aid == player.armor or aid == player.helmet:
                continue
            data = get_armor_item(aid)
            if not data:
                continue
            result.append({
                "type": "armor",
                "id": aid,
                "name": data.get("name", aid),
                "emoji": data.get("emoji", "🧥"),
                "slot": data.get("slot", "armor"),
            })

    elif category_id == "module":
        for mid in player.modules_inventory:
            data = MODULES.get('modules', {}).get(mid)
            if not isinstance(data, dict):
                continue
            result.append({
                "type": "module",
                "id": mid,
                "name": data.get("name", mid),
                "emoji": data.get("emoji", "🔧"),
            })

    elif category_id == "magazine":
        for mag in player.get_uninstalled_magazines():
            data = get_magazine(mag["type_id"])
            if not data:
                continue
            ammo_count = sum(mag.get("ammo", {}).values())
            result.append({
                "type": "magazine",
                "uid": mag["uid"],
                "name": f"{data.get('name', mag['type_id'])} ({ammo_count} патр.)",
                "emoji": data.get("emoji", "📀"),
            })

    elif category_id == "throwable":
        for gid, cnt in player.grenades_inventory.items():
            if cnt <= 0:
                continue
            data = WEAPONS.get(gid, {})
            if not isinstance(data, dict):
                continue
            result.append({
                "type": "grenade",
                "id": gid,
                "name": data.get("name", gid),
                "emoji": data.get("emoji", "💣"),
                "count": cnt,
                "max_count": cnt,
            })
        for kid, cnt in player.throwing_knives_inventory.items():
            if cnt <= 0:
                continue
            data = WEAPONS.get(kid, {})
            if not isinstance(data, dict):
                continue
            result.append({
                "type": "knife",
                "id": kid,
                "name": data.get("name", kid),
                "emoji": data.get("emoji", "🔪"),
                "count": cnt,
                "max_count": cnt,
            })

    elif category_id == "consumable":
        for key in ("аптечка_аи2", "аптечка_аи4", "кустарная_аптечка",
                    "тактическая_аптечка", "мед_подсумок", "антирад",
                    "аспирин", "розжиг"):
            cnt = player.inventory.get(key, 0)
            if cnt <= 0:
                continue
            name, emoji = _consumable_display(key)
            result.append({
                "type": "inventory_key",
                "key": key,
                "name": name,
                "emoji": emoji,
                "count": cnt,
                "max_count": cnt,
            })
        # Фильтры
        filter_counts = {}
        for fid in player.filters:
            filter_counts[fid] = filter_counts.get(fid, 0) + 1
        for fid, cnt in filter_counts.items():
            data = get_filter(fid)
            if not data:
                continue
            result.append({
                "type": "filter",
                "id": fid,
                "name": data.get("name", fid),
                "emoji": data.get("emoji", "🧪"),
                "count": cnt,
                "max_count": cnt,
            })

    elif category_id == "food":
        food_counts = {}
        for fid in player.food_inventory:
            food_counts[fid] = food_counts.get(fid, 0) + 1
        for fid, cnt in food_counts.items():
            data = get_food(fid)
            if not data:
                continue
            result.append({
                "type": "food",
                "id": fid,
                "name": data.get("name", fid),
                "emoji": data.get("emoji", "🍖"),
                "count": cnt,
                "max_count": cnt,
            })

    return result


def _consumable_display(key: str) -> tuple:
    """Возвращает (name, emoji) для inventory_key."""
    mapping = {
        "аптечка_аи2": ("Аптечка АИ-2", "💊"),
        "аптечка_аи4": ("Аптечка АИ-4", "💉"),
        "кустарная_аптечка": ("Кустарная аптечка", "🧪"),
        "тактическая_аптечка": ("Тактическая аптечка", "🩹"),
        "мед_подсумок": ("Мед. Подсумок", "🧰"),
        "антирад": ("Антирад", "💉"),
        "аспирин": ("Аспирин", "💊"),
        "розжиг": ("Розжиг", "🪵"),
    }
    return mapping.get(key, (key, "📦"))


# ==================== МЕНЮ ВЫБОРА КАТЕГОРИИ ====================

class CategoryPickerView(discord.ui.View):
    """
    Показывает категории предметов. При выборе категории вызывает
    callback(category_id, interaction).
    """

    def __init__(self, player, on_pick, back_label: str = "🔙 Отмена"):
        super().__init__(timeout=300)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self.on_pick = on_pick
        self._add_buttons(back_label)

    def _add_buttons(self, back_label: str):
        for idx, cat in enumerate(CATEGORIES):
            count = len(get_items_in_category(self.player, cat["id"]))
            label = f"{cat['name']} ({count})" if count > 0 else f"{cat['name']} — пусто"
            btn = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.primary if count > 0 else discord.ButtonStyle.secondary,
                custom_id=f"pickcat_{self.menu_id}_{idx}",
                row=idx // 2,
                disabled=(count == 0),
            )
            btn.callback = self.create_pick_callback(cat["id"])
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label=back_label,
            style=discord.ButtonStyle.danger,
            custom_id=f"pickcat_back_{self.menu_id}",
            row=4,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_pick_callback(self, category_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message(
                    "❌ Не ваш инвентарь!", ephemeral=True
                )
                return
            await self.on_pick(interaction, category_id)
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваш инвентарь!", ephemeral=True
            )
            return
        try:
            await interaction.response.edit_message(
                content="Выбор отменён.",
                embed=None,
                view=None,
            )
        except Exception:
            pass


def build_category_embed(player, title: str = "📦 Выбор категории") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description="Что вы хотите передать?",
        color=discord.Color.blue(),
    )

    for cat in CATEGORIES:
        items = get_items_in_category(player, cat["id"])
        if not items:
            embed.add_field(
                name=cat["name"],
                value=f"_{cat['desc']}_\n❌ Пусто",
                inline=True,
            )
        else:
            lines = []
            for it in items[:3]:
                lines.append(f"{it.get('emoji', '📦')} {it.get('name', '?')}")
            if len(items) > 3:
                lines.append(f"... и ещё {len(items) - 3}")
            embed.add_field(
                name=cat["name"],
                value=f"_{cat['desc']}_\n" + "\n".join(lines),
                inline=True,
            )

    return embed


# ==================== МЕНЮ ВЫБОРА ПРЕДМЕТА ====================

class ItemPickerView(discord.ui.View):
    """
    Список предметов в категории. При выборе предмета вызывает
    callback(item_descriptor, interaction).
    """

    def __init__(self, player, category_id: str, on_pick, back_callback=None):
        super().__init__(timeout=300)
        self.player = player
        self.category_id = category_id
        self.menu_id = uuid.uuid4().hex[:8]
        self.on_pick = on_pick
        self.back_callback_fn = back_callback

        self.items = get_items_in_category(player, category_id)

        for idx, item in enumerate(self.items[:20]):
            label = f"{item.get('emoji', '📦')} {item.get('name', '?')}"
            if item.get("count") is not None and item.get("count", 1) > 1:
                label += f" ×{item['count']}"
            btn = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"pickitem_{self.menu_id}_{idx}",
                row=idx // 3,
            )
            btn.callback = self.create_pick_callback(item)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"pickitem_back_{self.menu_id}",
            row=4,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_pick_callback(self, item: dict):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message(
                    "❌ Не ваш инвентарь!", ephemeral=True
                )
                return
            await self.on_pick(interaction, item)
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваш инвентарь!", ephemeral=True
            )
            return
        if self.back_callback_fn:
            await self.back_callback_fn(interaction)
        else:
            try:
                await interaction.response.edit_message(
                    content="Возврат.", embed=None, view=None
                )
            except Exception:
                pass


def build_items_embed(player, category_id: str, title: str = "📦 Выбор предмета") -> discord.Embed:
    cat = next((c for c in CATEGORIES if c["id"] == category_id), {})
    items = get_items_in_category(player, category_id)

    embed = discord.Embed(
        title=title,
        description=f"Раздел: **{cat.get('name', category_id)}**\n"
                    f"Найдено предметов: **{len(items)}**",
        color=discord.Color.blue(),
    )

    if not items:
        embed.add_field(name="❌ Пусто", value="В этой категории нет предметов.", inline=False)
        return embed

    for it in items[:10]:
        line = f"{it.get('emoji', '📦')} **{it.get('name', '?')}**"
        if it.get("count") is not None and it.get("count", 1) > 1:
            line += f" ×{it['count']}"
        embed.add_field(name=line, value="\u200b", inline=False)

    if len(items) > 10:
        embed.set_footer(text=f"Показано 10 из {len(items)}")

    return embed


# ==================== МЕНЮ ВЫБОРА КОЛИЧЕСТВА ====================

class CountPickerView(discord.ui.View):
    """
    Модалка/кнопки для выбора количества, если у предмета count > 1.
    Возвращает выбранное количество через callback(count, interaction).
    """

    def __init__(self, player, item: dict, on_pick, back_callback=None):
        super().__init__(timeout=120)
        self.player = player
        self.item = item
        self.on_pick = on_pick
        self.back_callback_fn = back_callback
        self.menu_id = uuid.uuid4().hex[:8]

        max_count = int(item.get("count", 1) or 1)
        presets = sorted(set([1, 2, 3, 5, 10, max_count]))
        presets = [p for p in presets if 1 <= p <= max_count]
        if max_count not in presets:
            presets.append(max_count)
        presets = presets[:6]

        for idx, n in enumerate(presets):
            btn = discord.ui.Button(
                label=f"×{n}" + (" (всё)" if n == max_count else ""),
                style=discord.ButtonStyle.primary,
                custom_id=f"pickcount_{self.menu_id}_{idx}",
                row=idx // 3,
            )
            btn.callback = self.create_count_callback(n)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"pickcount_back_{self.menu_id}",
            row=2,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_count_callback(self, n: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message(
                    "❌ Не ваш инвентарь!", ephemeral=True
                )
                return
            await self.on_pick(interaction, n)
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваш инвентарь!", ephemeral=True
            )
            return
        if self.back_callback_fn:
            await self.back_callback_fn(interaction)
        else:
            try:
                await interaction.response.edit_message(
                    content="Возврат.", embed=None, view=None
                )
            except Exception:
                pass


def build_count_embed(item: dict) -> discord.Embed:
    max_count = int(item.get("count", 1) or 1)
    embed = discord.Embed(
        title="📦 Сколько передать?",
        description=(
            f"{item.get('emoji', '📦')} **{item.get('name', '?')}**\n"
            f"В наличии: **{max_count}**"
        ),
        color=discord.Color.blue(),
    )
    return embed


# ==================== УТИЛИТЫ ====================

def apply_count_to_descriptor(item: dict, count: int) -> dict:
    """
    Возвращает новый descriptor с заданным count.
    Для одиночных предметов (weapon/melee/armor/module/magazine) count=1.
    """
    result = dict(item)
    if item.get("type") in ("grenade", "knife", "food", "filter", "inventory_key"):
        result["count"] = count
    else:
        result["count"] = 1
    return result


def describe_item(item: dict) -> str:
    """Человекочитаемое описание для эмбеда."""
    emoji = item.get("emoji", "📦")
    name = item.get("name", item.get("id") or item.get("key") or "?")
    cnt = item.get("count")
    if cnt and cnt > 1:
        return f"{emoji} {name} ×{cnt}"
    return f"{emoji} {name}"