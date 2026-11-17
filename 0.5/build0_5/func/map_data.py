# -*- coding: utf-8 -*-
# func/map_data.py - Данные карты (Билд 0.4)
from config.map_config import STATIONS, STATIONS_DICT, LINES_DICT, TECHNICAL_TUNNELS_DICT

# Используем данные из конфига
MAP_DATA = STATIONS

# Для удобства доступа к станциям
STATIONS_DATA = STATIONS_DICT

# Извлекаем линии из правильной структуры
LINES = LINES_DICT

# Технические тоннели
TECHNICAL_TUNNELS = TECHNICAL_TUNNELS_DICT

# Добавляем технические тоннели в MAP_DATA для удобства
if "technical_tunnels" not in MAP_DATA:
    MAP_DATA["technical_tunnels"] = TECHNICAL_TUNNELS

# Иконки линий (собираем из LINES)
LINE_ICONS = {}
for line_id, line_data in LINES.items():
    LINE_ICONS[line_id] = line_data.get("icon", "⬛")

DANGER_LEVELS = {
    0: "🟢 Безопасно",
    1: "🟡 Небольшая опасность",
    2: "🟠 Опасно",
    3: "🔴 Очень опасно",
    4: "💀 Смертельно",
    5: "☠️ Экстремально"
}

RADIATION_STATIONS = [
    "аннино",
    "ул_янгеля",
    "южная",
    "пражская",
    "чертановская",
    "нахимовский_проспект"
]


# ==================== БАЗОВЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАНЦИЯМИ ====================

def get_station_name(station_id: str) -> str:
    """Получить название станции по ID"""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return station_id
    return station.get("name", station_id)


def get_station_emoji(station_id: str) -> str:
    """Получить эмодзи станции по ID"""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return "❓"
    return station.get("emoji", "⬤")


def get_station_danger_level(station_id: str) -> int:
    """Получить уровень опасности станции"""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return 0
    return station.get("danger", 0)


def is_ruined_station(station_id: str) -> bool:
    """Проверить, является ли станция разрушенной"""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return False
    return station.get("ruined", False)


def get_station_connections(station_id: str) -> list:
    """Получить список соединений станции"""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return []
    return station.get("connections", [])


def get_station_line(station_id: str) -> str:
    """Получить ID линии станции"""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return None
    return station.get("line")


def get_station_description(station_id: str) -> str:
    """Получить описание станции"""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return ""
    return station.get("description", "")


def get_all_station_ids() -> list:
    """Получить список всех ID станций"""
    return list(MAP_DATA["станции"].keys())


def format_station_info(station_id: str) -> str:
    """Форматированная информация о станции"""
    from .station_utils import get_station_types, format_station_types

    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return "❌ Станция не найдена"

    types_str = format_station_types(station_id)

    result = f"{station.get('emoji', '⬤')} **{station.get('name', station_id)}**\n"
    result += f"📋 Тип: {types_str}\n"

    danger = station.get("danger", 0)
    if danger > 0:
        result += f"⚠️ Опасность: {DANGER_LEVELS.get(danger, '❓ Неизвестно')}\n"
    else:
        result += "✅ Безопасная станция\n"

    if station.get("ruined", False):
        result += "☢️ Разрушенная станция\n"

    result += f"📝 {station.get('description', '')}\n"

    connections = station.get("connections", [])
    if connections:
        conn_names = [get_station_name(conn) for conn in connections]
        result += f"🚇 Переходы: {' → '.join(conn_names)}"
    else:
        result += "🚇 Конечная станция"

    return result