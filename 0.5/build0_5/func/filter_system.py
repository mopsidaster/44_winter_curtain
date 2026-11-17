# -*- coding: utf-8 -*-
# func/filter_system.py - Система фильтров (0.4.8.7.3)
#
# ИСТОРИЯ:
#   0.4   — базовая система
#   0.4.8.7.3 — ФИКС дупа: filters_durability

from config.map_config import FILTERS, BALANCE
from utils.logger import get_logger

logger = get_logger()


def _ensure_filters_durability(player):
    """0.4.8.7.3: dict filter_id → list[durability]"""
    if not hasattr(player, 'filters_durability') \
            or not isinstance(player.filters_durability, dict):
        player.filters_durability = {}


def get_filter(filter_id: str) -> dict:
    return FILTERS["фильтры"].get(filter_id)


def get_filter_name(filter_id: str) -> str:
    filter_data = get_filter(filter_id)
    if not filter_data:
        return filter_id
    return filter_data.get("name", filter_id)


def get_filter_durability(filter_id: str) -> float:
    filter_data = get_filter(filter_id)
    if not filter_data:
        return 0.0
    return filter_data.get("durability", 0.0)


def get_filter_price(filter_id: str) -> int:
    return BALANCE.get('prices', {}).get('filter', {}).get(filter_id, 0)


def get_filter_emoji(filter_id: str) -> str:
    filter_data = get_filter(filter_id)
    if not filter_data:
        return "🧪"
    return filter_data.get("emoji", "🧪")


def get_all_filters() -> list:
    return list(FILTERS["фильтры"].keys())


def get_available_filters() -> list:
    return list(FILTERS["фильтры"].keys())


def format_filter_info(filter_id: str) -> str:
    filter_data = get_filter(filter_id)
    if not filter_data:
        return "❌ Фильтр не найден"

    result = f"{filter_data.get('emoji', '🧪')} **{filter_data.get('name', filter_id)}**\n"
    result += f"📊 Прочность: {filter_data.get('durability', 0)} единиц\n"
    result += f"💰 Цена: {get_filter_price(filter_id)} никелей\n"

    durability = filter_data.get('durability', 0)
    if durability >= 8:
        result += "💪 Максимальная защита. Выдерживает длительное нахождение в заражённой зоне."
    elif durability >= 5:
        result += "🟢 Хорошая защита. Надёжный фильтр для опасных зон."
    elif durability >= 2.5:
        result += "🟡 Средняя защита. Подходит для кратковременных вылазок."
    else:
        result += "🔴 Минимальная защита. Используйте только в крайнем случае."

    return result


def format_filters_inventory(player) -> str:
    _ensure_filters_durability(player)

    if not player.filters:
        return "🧪 У вас нет фильтров"

    filter_counts = {}
    for filter_id in player.filters:
        filter_counts[filter_id] = filter_counts.get(filter_id, 0) + 1

    result = ""
    for filter_id, count in filter_counts.items():
        filter_data = get_filter(filter_id)
        if filter_data:
            result += f"{filter_data.get('emoji', '🧪')} **{filter_data.get('name', filter_id)}** x{count}\n"
        else:
            result += f"❓ {filter_id} x{count}\n"

    return result


async def equip_filter(player, filter_id: str) -> str:
    """0.4.8.7.3: при замене сохраняем прочность старого фильтра."""
    _ensure_filters_durability(player)

    filter_data = get_filter(filter_id)
    if not filter_data:
        return "❌ Такого фильтра не существует!"

    if filter_id not in player.filters:
        return f"❌ У вас нет {filter_data.get('name', filter_id)}!"

    if not player.gas_mask.get("надет", False):
        return "❌ Сначала наденьте противогаз!"

    # Если фильтр уже стоит
    if player.equipped_filter:
        old_filter = player.equipped_filter
        old_dur = player.gas_mask.get("фильтр_прочность", 0)

        # 0.4.8.7.3: вернуть старый фильтр только если прочность > 0
        if old_dur > 0:
            player.filters.append(old_filter)
            # Сохраняем прочность по индексу
            if old_filter not in player.filters_durability:
                player.filters_durability[old_filter] = []
            player.filters_durability[old_filter].append(float(old_dur))

        player.equipped_filter = None
        player.gas_mask["фильтр_вставлен"] = False
        player.gas_mask["фильтр_прочность"] = 0.0

    # Извлекаем новый фильтр
    player.filters.remove(filter_id)

    # 0.4.8.7.3: берём прочность из filters_durability, если есть
    if filter_id in player.filters_durability \
            and player.filters_durability[filter_id]:
        dur = player.filters_durability[filter_id].pop(0)
    else:
        dur = filter_data.get("durability", 0)

    player.equipped_filter = filter_id
    player.gas_mask["фильтр_вставлен"] = True
    player.gas_mask["фильтр_прочность"] = dur

    return (
        f"✅ Установлен **{filter_data.get('name', filter_id)}**! "
        f"Прочность: {dur:.1f}"
    )


async def unequip_filter(player) -> str:
    """0.4.8.7.3: сохраняем прочность при снятии."""
    _ensure_filters_durability(player)

    if not player.equipped_filter:
        return "❌ У вас нет установленного фильтра!"

    filter_data = get_filter(player.equipped_filter)
    filter_id = player.equipped_filter
    remaining_durability = player.gas_mask.get("фильтр_прочность", 0)

    if remaining_durability > 0:
        player.filters.append(filter_id)
        if filter_id not in player.filters_durability:
            player.filters_durability[filter_id] = []
        player.filters_durability[filter_id].append(float(remaining_durability))

    player.equipped_filter = None
    player.gas_mask["фильтр_вставлен"] = False
    player.gas_mask["фильтр_прочность"] = 0.0

    return (
        f"✅ Снят **{filter_data.get('name', filter_id)}** "
        f"(остаток прочности: {remaining_durability:.1f})"
    )


def use_filter(player, amount: float = 0.5) -> dict:
    """Использовать фильтр."""
    if not player.equipped_filter:
        return {"success": False, "message": "❌ Нет установленного фильтра!"}

    current_durability = player.gas_mask.get("фильтр_прочность", 0)

    if current_durability <= 0:
        filter_data = get_filter(player.equipped_filter)
        player.gas_mask["фильтр_вставлен"] = False
        player.gas_mask["фильтр_прочность"] = 0.0
        return {
            "success": False,
            "message": f"❌ Фильтр **{filter_data.get('name', player.equipped_filter)}** полностью израсходован!",
            "expired": True,
        }

    new_durability = max(0, current_durability - amount)
    player.gas_mask["фильтр_прочность"] = new_durability

    if new_durability <= 0:
        filter_data = get_filter(player.equipped_filter)
        player.gas_mask["фильтр_вставлен"] = False
        return {
            "success": True,
            "message": f"🧪 Фильтр **{filter_data.get('name', player.equipped_filter)}** полностью израсходован!",
            "expired": True,
            "remaining": 0.0,
        }

    return {
        "success": True,
        "message": f"🧪 Фильтр использован. Осталось прочности: {new_durability:.1f}",
        "expired": False,
        "remaining": new_durability,
    }


def get_current_filter_info(player) -> dict:
    if not player.equipped_filter:
        return {"has_filter": False, "message": "❌ Фильтр не установлен"}

    filter_data = get_filter(player.equipped_filter)
    current_durability = player.gas_mask.get("фильтр_прочность", 0)

    return {
        "has_filter": True,
        "filter_id": player.equipped_filter,
        "filter_name": filter_data.get("name", player.equipped_filter),
        "filter_emoji": filter_data.get("emoji", "🧪"),
        "max_durability": filter_data.get("durability", 0),
        "current_durability": current_durability,
        "is_expired": current_durability <= 0,
    }