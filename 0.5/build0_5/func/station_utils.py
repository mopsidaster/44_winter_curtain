# -*- coding: utf-8 -*-
# func/station_utils.py - Утилиты для работы с типами станций (0.4.7.5)
#
# ИСТОРИЯ:
#   0.4.0   — базовые хелперы
#   0.4.7.5 — добавлены is_blocked_station, is_hostile_station,
#             can_enter_station

from .map_data import MAP_DATA
from utils.logger import get_logger

logger = get_logger()


def has_station_type(station_id: str, type_name: str) -> bool:
    """Проверить, есть ли у станции указанный тип."""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        logger.debug(f"has_station_type: станция {station_id} не найдена")
        return False

    if "types" in station:
        result = type_name in station["types"]
        logger.debug(f"has_station_type: {station_id} types={station['types']}, {type_name}={result}")
        return result

    if "type" in station:
        result = station["type"] == type_name
        logger.debug(f"has_station_type: {station_id} type={station['type']}, {type_name}={result}")
        return result

    logger.debug(f"has_station_type: {station_id} тип не найден")
    return False


def is_trade_station(station_id: str) -> bool:
    return has_station_type(station_id, "торговая")


def is_start_station(station_id: str) -> bool:
    return has_station_type(station_id, "стартовая")


def is_danger_station(station_id: str) -> bool:
    return has_station_type(station_id, "опасная")


# ==================== 0.4.7.5 ====================

def is_blocked_station(station_id: str) -> bool:
    """
    0.4.7.5: заблокированная станция.
    Игрок НЕ может совершить переход на такую станцию.
    """
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return False
    return bool(station.get("blocked", False))


def is_hostile_station(station_id: str) -> bool:
    """0.4.7.5: враждебная станция (лагерь Бандитов и т.п.)."""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return False
    return bool(station.get("hostile", False))


def can_enter_station(station_id: str) -> tuple:
    """
    0.4.7.5: может ли игрок войти на станцию.
    Возвращает (ok: bool, reason: str).
    """
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return False, "❌ Станция не найдена"

    if station.get("blocked", False):
        return False, f"🚫 Станция **{station.get('name', station_id)}** заблокирована. Проход закрыт."

    return True, "OK"


# ==================== ОСТАЛЬНОЕ ====================

def get_station_type(station_id: str) -> str:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return None

    if "types" in station and station["types"]:
        return station["types"][0]

    if "type" in station:
        return station["type"]

    return None


def get_station_types(station_id: str) -> list:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return []

    if "types" in station:
        return station["types"]

    if "type" in station:
        return [station["type"]]

    return []


def get_station_name(station_id: str) -> str:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return station_id
    return station.get("name", station_id)


def get_station_emoji(station_id: str) -> str:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return "❓"
    return station.get("emoji", "⬤")


def get_station_danger_level(station_id: str) -> int:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return 0
    return station.get("danger", 0)


def is_ruined_station(station_id: str) -> bool:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return False
    return station.get("ruined", False)


def get_station_connections(station_id: str) -> list:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return []
    return station.get("connections", [])


def get_station_line(station_id: str) -> str:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return None
    return station.get("line")


def get_station_description(station_id: str) -> str:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return ""
    return station.get("description", "")


def get_all_station_ids() -> list:
    return list(MAP_DATA["станции"].keys())


def get_stations_by_type(type_name: str) -> list:
    result = []
    for station_id in MAP_DATA["станции"]:
        if has_station_type(station_id, type_name):
            result.append(station_id)
    return result


def get_trade_stations() -> list:
    return get_stations_by_type("торговая")


def get_start_stations() -> list:
    return get_stations_by_type("стартовая")


def get_danger_stations_full() -> list:
    return get_stations_by_type("опасная")


def format_station_types(station_id: str) -> str:
    types = get_station_types(station_id)
    if not types:
        return "обычная"

    type_icons = {
        "стартовая": "★",
        "торговая": "🏪",
        "опасная": "☢️",
        "обычная": "⬤",
        "жилая": "🏘️",
        "разрушенная": "☢️",
        "на_поверхности": "❄️",
    }

    result = []
    for t in types:
        icon = type_icons.get(t, "⬤")
        result.append(f"{icon} {t}")

    if is_blocked_station(station_id):
        result.append("🚫 заблокирована")
    if is_hostile_station(station_id):
        result.append("🔫 враждебная")

    return ", ".join(result)


def format_station_info(station_id: str) -> str:
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return "❌ Станция не найдена"

    types_str = format_station_types(station_id)

    result = f"{get_station_emoji(station_id)} **{get_station_name(station_id)}**\n"
    result += f"📋 Тип: {types_str}\n"

    danger = get_station_danger_level(station_id)
    danger_levels = {
        0: "🟢 Безопасно",
        1: "🟡 Небольшая опасность",
        2: "🟠 Опасно",
        3: "🔴 Очень опасно",
        4: "💀 Смертельно",
        5: "☠️ Экстремально"
    }

    if danger > 0:
        result += f"⚠️ Опасность: {danger_levels.get(danger, '❓ Неизвестно')}\n"
    else:
        result += "✅ Безопасная станция\n"

    if is_ruined_station(station_id):
        result += "☢️ Разрушенная станция\n"

    desc = get_station_description(station_id)
    if desc:
        result += f"📝 {desc}\n"

    connections = get_station_connections(station_id)
    if connections:
        conn_names = [get_station_name(conn) for conn in connections]
        result += f"🚇 Переходы: {' → '.join(conn_names)}"
    else:
        result += "🚇 Конечная станция"

    return result