# -*- coding: utf-8 -*-
# func/global_events.py - Глобальные ивенты (Билд 0.4.5)
#
# ИСТОРИЯ:
#   0.4.3.3 — убран hunter_spirit, earthquake; groundwater → frost (заглушка)
#   0.4.4   — frost теперь РАБОТАЕТ: сохраняет зону поражения
#   0.4.5   — удалены power_outage, station_fire;
#             добавлены raider_raid, chemical_cloud, heating_failure;
#             хелперы is_chemical_zone, is_heating_zone, is_raider_raid_zone

import random
import asyncio
import discord
from discord.ext import commands
from utils.logger import get_logger
from config.map_config import BALANCE, STATIONS_DICT
from .map_data import MAP_DATA
from .station_utils import has_station_type, is_trade_station

logger = get_logger()

GLOBAL_EVENTS_ENABLED = True
MIN_EVENT_INTERVAL = 45
MAX_EVENT_INTERVAL = 90
EVENT_CHANNEL_ID = 1522572454122360912

logger.info(f"🌍 Конфигурация: ENABLED={GLOBAL_EVENTS_ENABLED}, INTERVAL={MIN_EVENT_INTERVAL}-{MAX_EVENT_INTERVAL} мин")


# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================

def get_trade_zones() -> list:
    trade_zones = []
    for station_id in MAP_DATA["станции"]:
        if has_station_type(station_id, "торговая"):
            trade_zones.append(station_id)
    return trade_zones


def get_danger_stations() -> list:
    danger_zones = []
    for station_id, station_data in MAP_DATA["станции"].items():
        if station_data.get("ruined", False) or station_data.get("danger", 0) >= 3:
            danger_zones.append(station_id)
    return danger_zones


def get_safe_stations() -> list:
    safe_zones = []
    for station_id, station_data in MAP_DATA["станции"].items():
        if not station_data.get("ruined", False) and station_data.get("danger", 0) < 3:
            safe_zones.append(station_id)
    return safe_zones


def get_random_stations(count: int, station_list: list) -> list:
    if not station_list:
        return []
    if len(station_list) <= count:
        return station_list
    return random.sample(station_list, count)


def get_nearby_stations(station_id: str, count: int = 2) -> list:
    if station_id not in MAP_DATA["станции"]:
        return []
    connections = MAP_DATA["станции"][station_id].get("connections", [])
    if len(connections) <= count:
        return connections
    return random.sample(connections, count)


def get_all_neighbors(station_id: str) -> list:
    """Все соседи станции по connections."""
    if station_id not in MAP_DATA["станции"]:
        return []
    return list(MAP_DATA["станции"][station_id].get("connections", []))


def get_random_trade_zone() -> str:
    trade_zones = get_trade_zones()
    if not trade_zones:
        return None
    return random.choice(trade_zones)


def get_station_defense(station_id: str) -> int:
    if station_id not in MAP_DATA["станции"]:
        return 0
    danger = MAP_DATA["станции"][station_id].get("danger", 0)
    return max(0, 10 - danger * 2)


def apply_damage_to_players_on_station(gm, station_id: str, damage: float, message: str) -> str:
    affected = []
    for player in gm.players.values():
        # 0.4.6: спящих не трогаем
        if getattr(player, 'is_sleeping', False):
            continue
        if player.is_alive and player.location == station_id:
            player.lives -= damage
            if player.lives <= 0:
                player.is_alive = False
                affected.append(f"💀 {player.name} погиб!")
            else:
                affected.append(f"{player.name} ({player.lives:.1f})")

    if affected:
        return f"{message}\nПострадавшие: {', '.join(affected)}"
    return message


def get_stations_with_defense_below(threshold: int) -> list:
    result = []
    for station_id in MAP_DATA["станции"]:
        defense = get_station_defense(station_id)
        if defense < threshold:
            result.append(station_id)
    return result


# ==================== FROST ZONE (0.4.4) ====================

def is_frost_zone(station_id: str, game_manager) -> bool:
    """Находится ли станция в зоне ивента Заморозки."""
    if not is_event_active('frost', game_manager):
        return False

    zone_station = getattr(game_manager, 'frost_station', None)
    zone_connections = getattr(game_manager, 'frost_connections', []) or []

    if station_id == zone_station:
        return True

    if station_id in zone_connections:
        return True

    return False


def get_frost_zone(game_manager) -> dict:
    """Информация о текущей зоне заморозки."""
    if not is_event_active('frost', game_manager):
        return {"active": False}

    return {
        "active": True,
        "station": getattr(game_manager, 'frost_station', None),
        "connections": getattr(game_manager, 'frost_connections', []) or [],
    }


# ==================== ХИМИЧЕСКАЯ ЗОНА (0.4.5) ====================

def is_chemical_zone(station_id: str, game_manager) -> bool:
    """
    Находится ли станция в зоне Химического выброса.
    Зона = chemical_cloud_station + все её соседи (connections).
    """
    if not is_event_active('chemical_cloud', game_manager):
        return False

    zone_station = getattr(game_manager, 'chemical_cloud_station', None)
    zone_connections = getattr(game_manager, 'chemical_cloud_connections', []) or []

    if station_id == zone_station:
        return True

    if station_id in zone_connections:
        return True

    return False


def get_chemical_zone(game_manager) -> dict:
    """Информация о текущей зоне Химического выброса."""
    if not is_event_active('chemical_cloud', game_manager):
        return {"active": False}

    return {
        "active": True,
        "station": getattr(game_manager, 'chemical_cloud_station', None),
        "connections": getattr(game_manager, 'chemical_cloud_connections', []) or [],
    }


# ==================== ЗОНА ОТОПЛЕНИЯ (0.4.5) ====================

def is_heating_zone(station_id: str, game_manager) -> bool:
    """
    Находится ли станция в зоне Отопления (только одна конкретная станция,
    без соседей).
    """
    if not is_event_active('heating_failure', game_manager):
        return False

    zone_station = getattr(game_manager, 'heating_station', None)
    return station_id == zone_station


def get_heating_zone(game_manager) -> dict:
    """Информация о текущей зоне Отопления."""
    if not is_event_active('heating_failure', game_manager):
        return {"active": False}

    return {
        "active": True,
        "station": getattr(game_manager, 'heating_station', None),
    }


# ==================== ЗОНА РЕЙДЕРСКОГО ЗАХВАТА (0.4.5) ====================

def is_raider_raid_zone(station_id: str, game_manager) -> bool:
    """
    Активен ли Рейдерский захват и находится ли станция в списке атакуемых.
    """
    if not is_event_active('raider_raid', game_manager):
        return False

    raid_stations = getattr(game_manager, 'raider_raid_stations', []) or []
    return station_id in raid_stations


def get_raider_raid_stations(game_manager) -> list:
    """Список станций, где активен Рейдерский захват."""
    if not is_event_active('raider_raid', game_manager):
        return []
    return list(getattr(game_manager, 'raider_raid_stations', []) or [])


# ==================== СПИСОК ИВЕНТОВ ====================

def get_events():
    return [
        {
            "id": "trade_caravan",
            "text": "🛒 **Торговый караван!** Скидка 20% на все товары в одной из торговых зон на 15 минут!",
            "type": "buff",
            "duration": 15,
            "effect": "trade_discount",
            "apply": lambda gm: setattr(gm, 'trade_discount_active', True),
            "remove": lambda gm: setattr(gm, 'trade_discount_active', False),
            "description": "🛒 Скидка 20% на все товары в случайной торговой зоне"
        },
        {
            "id": "mutant_activity",
            "text": "⚠️ **Повышенная активность мутантов!** На 5 случайных опасных станциях мутанты активизировались на 15 минут!",
            "type": "debuff",
            "duration": 15,
            "effect": "mutant_wave",
            "apply": lambda gm: setattr(gm, 'mutant_wave_active', True),
            "remove": lambda gm: setattr(gm, 'mutant_wave_active', False),
            "description": "💀 Мутанты опаснее на 5 случайных станциях"
        },
        {
            "id": "frost",
            "text": "❄️ **Заморозки!** На одной из станций вентиляция вышла из строя. Одна станция и 2 ближайших перехода страдают от адского холода.",
            "type": "debuff",
            "duration": 20,
            "effect": "frost",
            "apply": lambda gm: setattr(gm, 'frost_active', True),
            "remove": lambda gm: [
                setattr(gm, 'frost_active', False),
                setattr(gm, 'frost_station', None),
                setattr(gm, 'frost_connections', []),
            ],
            "description": "❄️ Игроки получают холод в зоне поражения. Согревайтесь у костра!"
        },
        {
            "id": "station_celebration",
            "text": "🎉 **Праздник на станции!** Случайная торговая зона празднует! Зайдите и получите +3 еды!",
            "type": "buff",
            "duration": 15,
            "effect": "station_celebration",
            "apply": lambda gm: [
                setattr(gm, 'station_celebration_active', True),
                setattr(gm, 'celebration_station', get_random_trade_zone()),
            ],
            "remove": lambda gm: [
                setattr(gm, 'station_celebration_active', False),
                setattr(gm, 'celebration_station', None),
            ],
            "description": "🍖 Зайдите в указанную торговую зону и получите +3 еды"
        },
        {
            "id": "radiation_spike",
            "text": "☢️ **Радиационный выброс!** Урон от радиации удвоен на опасных станциях на 15 минут!",
            "type": "debuff",
            "duration": 15,
            "effect": "radiation_spike",
            "apply": lambda gm: setattr(gm, 'radiation_spike_active', True),
            "remove": lambda gm: setattr(gm, 'radiation_spike_active', False),
            "description": "☢️ Радиационное заражение накапливается вдвое быстрее"
        },
        {
            "id": "grand_sale",
            "text": "🏪 **Грандиозная распродажа!** В случайной торговой зоне скидка 30% на 15 минут!",
            "type": "buff",
            "duration": 15,
            "effect": "shop_sale",
            "apply": lambda gm: setattr(gm, 'shop_sale_active', True),
            "remove": lambda gm: setattr(gm, 'shop_sale_active', False),
            "description": "🏪 Скидка 30% в случайной торговой зоне"
        },
        {
            "id": "gas_leak",
            "text": "☠️ **Утечка газа!** Для защиты необходим полный РХБЗ комплект. Урон 5 единиц за переход!",
            "type": "debuff",
            "duration": 10,
            "effect": "gas_leak",
            "apply": lambda gm: setattr(gm, 'gas_leak_active', True),
            "remove": lambda gm: setattr(gm, 'gas_leak_active', False),
            "description": "☠️ Урон 5 за переход. Защищает только полный РХБЗ комплект"
        },
        {
            "id": "stalker_workshop",
            "text": "🔧 **Мастерская сталкеров!** В случайной торговой зоне появилась мастерская!",
            "type": "buff",
            "duration": 10,
            "effect": "stalker_workshop",
            "apply": lambda gm: [
                setattr(gm, 'stalker_workshop_active', True),
                setattr(gm, 'workshop_station', get_random_trade_zone()),
            ],
            "remove": lambda gm: [
                setattr(gm, 'stalker_workshop_active', False),
                setattr(gm, 'workshop_station', None),
            ],
            "description": "🔧 Противогаз в подарок и скидка 50% на фильтры"
        },
        {
            "id": "mutant_breach",
            "text": "🧟 **Мутанты прорвали оборону!** Атака на случайную станцию с защитой ниже 6!",
            "type": "debuff",
            "duration": 5,
            "effect": "mutant_breach",
            "apply": lambda gm: [
                setattr(gm, 'mutant_breach_active', True),
                setattr(gm, 'breach_station',
                        random.choice(get_stations_with_defense_below(6))
                        if get_stations_with_defense_below(6) else None),
            ],
            "remove": lambda gm: [
                setattr(gm, 'mutant_breach_active', False),
                setattr(gm, 'breach_station', None),
            ],
            "description": "🧟 Атака на станцию с защитой ниже 6"
        },
        # 0.4.5: Рейдерский захват
        {
            "id": "raider_raid",
            "text": "☠️ **Рейдерский захват!** Рейдер со своими носачами решил запугать народ на Севастопольской ГЭС!",
            "type": "debuff",
            "duration": 15,
            "effect": "raider_raid",
            "apply": lambda gm: [
                setattr(gm, 'raider_raid_active', True),
                setattr(gm, 'raider_raid_stations',
                        list(BALANCE.get('raider_raid', {}).get('stations', []))),
                setattr(gm, 'raider_raid_killed', False),
            ],
            "remove": lambda gm: [
                setattr(gm, 'raider_raid_active', False),
                setattr(gm, 'raider_raid_stations', []),
                setattr(gm, 'raider_raid_killed', False),
            ],
            "description": "☠️ Рейдер появляется со 100% шансом на 6 станциях. Убейте его, чтобы закончить ивент досрочно."
        },
        # 0.4.5: Химический выброс
        {
            "id": "chemical_cloud",
            "text": "☣️ **Химический выброс!** Неизвестное вещество распространяется на опасных станциях.",
            "type": "debuff",
            "duration": 25,
            "effect": "chemical_cloud",
            "apply": lambda gm: _apply_chemical_cloud(gm),
            "remove": lambda gm: [
                setattr(gm, 'chemical_cloud_active', False),
                setattr(gm, 'chemical_cloud_station', None),
                setattr(gm, 'chemical_cloud_connections', []),
            ],
            "description": "☣️ Станция опасности 4-5 и все соседние заражены. 25 хим. заражения за переход без защиты."
        },
        # 0.4.5: Отопление вышло из строя
        {
            "id": "heating_failure",
            "text": "🥶 **Отопление вышло из строя!** На одной безопасной станции отключили отопление.",
            "type": "debuff",
            "duration": 25,
            "effect": "heating_failure",
            "apply": lambda gm: _apply_heating_failure(gm),
            "remove": lambda gm: [
                setattr(gm, 'heating_failure_active', False),
                setattr(gm, 'heating_station', None),
            ],
            "description": "🥶 Переход на станцию и с неё наносит 25 холода без защиты."
        }
    ]


# ==================== ПРИМЕНЕНИЕ НОВЫХ ИВЕНТОВ ====================

def _apply_chemical_cloud(gm):
    """Выбирает случайную станцию опасности 4-5, заражает её и соседей."""
    cfg = BALANCE.get('chemical_cloud', {})
    danger_min = cfg.get('target_danger_min', 4)
    danger_max = cfg.get('target_danger_max', 5)

    candidates = []
    for station_id, station_data in MAP_DATA["станции"].items():
        danger = station_data.get("danger", 0)
        if danger_min <= danger <= danger_max:
            candidates.append(station_id)

    if not candidates:
        logger.warning("🌍 chemical_cloud: не найдено станций опасности 4-5")
        gm.chemical_cloud_station = None
        gm.chemical_cloud_connections = []
        gm.chemical_cloud_active = True
        return

    station = random.choice(candidates)
    connections = get_all_neighbors(station)

    gm.chemical_cloud_station = station
    gm.chemical_cloud_connections = list(connections)
    gm.chemical_cloud_active = True

    station_name = MAP_DATA["станции"][station]["name"]
    nearby_names = [MAP_DATA["станции"][s]["name"] for s in connections]
    logger.info(
        f"🌍 chemical_cloud: центр={station_name}, "
        f"соседи={nearby_names}"
    )


def _apply_heating_failure(gm):
    """Выбирает случайную безопасную станцию."""
    safe = get_safe_stations()
    if not safe:
        logger.warning("🌍 heating_failure: не найдено безопасных станций")
        gm.heating_station = None
        gm.heating_failure_active = True
        return

    station = random.choice(safe)
    gm.heating_station = station
    gm.heating_failure_active = True

    station_name = MAP_DATA["станции"][station]["name"]
    logger.info(f"🌍 heating_failure: станция={station_name}")


# ==================== СТАТУСЫ ====================

class EventStatus:
    def __init__(self):
        self.active = False
        self.event = None
        self.time_remaining = 0
        self.task = None
        self.start_time = 0


current_event = EventStatus()


def get_active_effects(gm) -> dict:
    effects = {}
    attrs = [
        'trade_discount_active', 'mutant_wave_active',
        'frost_active', 'radiation_spike_active',
        'shop_sale_active',
        'x2_exp_active',
        'station_celebration_active', 'gas_leak_active',
        'stalker_workshop_active',
        'mutant_breach_active',
        # 0.4.5
        'raider_raid_active', 'chemical_cloud_active', 'heating_failure_active',
    ]
    for attr in attrs:
        if hasattr(gm, attr) and getattr(gm, attr):
            effects[attr.replace('_active', '')] = True
    return effects


def get_event_color(event_type: str) -> int:
    colors = {"buff": 0x00FF00, "debuff": 0xFF0000, "neutral": 0xFFFF00}
    return colors.get(event_type, 0x00A2FF)


def get_event_icon(event_type: str) -> str:
    icons = {"buff": "✨", "debuff": "⚠️", "neutral": "ℹ️"}
    return icons.get(event_type, "📢")


# ==================== ПРОВЕРКИ ЭФФЕКТОВ ====================

def is_event_active(effect_id: str, game_manager) -> bool:
    attr_name = f"{effect_id}_active"
    if hasattr(game_manager, attr_name):
        return getattr(game_manager, attr_name)
    return False


def get_trade_discount(game_manager) -> float:
    discount = 1.0
    if is_event_active('shop_sale', game_manager):
        discount = 0.7
    elif is_event_active('trade_discount', game_manager):
        discount = 0.8
    return discount


def get_stamina_multiplier(game_manager) -> float:
    return 1.0


def get_xp_multiplier(game_manager) -> float:
    if is_event_active('x2_exp', game_manager):
        return 2.0
    return 1.0


def get_radiation_multiplier(game_manager) -> float:
    if is_event_active('radiation_spike', game_manager):
        return 2.0
    return 1.0


def can_move(game_manager) -> bool:
    return True


def get_mutant_difficulty(game_manager) -> float:
    if is_event_active('mutant_wave', game_manager):
        return 1.5
    return 1.0


def get_loot_multiplier(game_manager) -> float:
    return 1.0


def get_gas_damage(game_manager) -> float:
    if is_event_active('gas_leak', game_manager):
        return 5.0
    return 0.0


def is_celebration_station(station_id: str, game_manager) -> bool:
    if not is_event_active('station_celebration', game_manager):
        return False
    return getattr(game_manager, 'celebration_station', None) == station_id


def is_workshop_station(station_id: str, game_manager) -> bool:
    if not is_event_active('stalker_workshop', game_manager):
        return False
    return getattr(game_manager, 'workshop_station', None) == station_id


def get_breach_station(game_manager) -> str:
    if not is_event_active('mutant_breach', game_manager):
        return None
    return getattr(game_manager, 'breach_station', None)


def get_filter_discount(game_manager) -> float:
    if is_event_active('stalker_workshop', game_manager):
        return 0.5
    return 1.0


# ==================== ЗАПУСК ====================

async def run_global_events(bot: commands.Bot, game_manager):
    if not GLOBAL_EVENTS_ENABLED:
        logger.info("🌍 Глобальные ивенты ОТКЛЮЧЕНЫ в конфиге")
        return

    await bot.wait_until_ready()
    _init_event_attributes(game_manager)

    logger.info("🌍 Глобальные ивенты ЗАПУЩЕНЫ (Билд 0.4.5)")

    next_event_time = random.randint(MIN_EVENT_INTERVAL, MAX_EVENT_INTERVAL)
    logger.info(f"⏱️ Первый глобальный ивент через {next_event_time} минут")

    while not bot.is_closed():
        await asyncio.sleep(next_event_time * 60)

        if not game_manager.players:
            next_event_time = random.randint(MIN_EVENT_INTERVAL, MAX_EVENT_INTERVAL)
            continue

        await trigger_event(bot, game_manager)
        next_event_time = random.randint(MIN_EVENT_INTERVAL, MAX_EVENT_INTERVAL)
        logger.info(f"⏱️ Следующий глобальный ивент через {next_event_time} минут")


def _init_event_attributes(gm):
    attrs = [
        'trade_discount_active', 'mutant_wave_active',
        'frost_active', 'radiation_spike_active',
        'shop_sale_active',
        'x2_exp_active',
        'station_celebration_active', 'gas_leak_active',
        'stalker_workshop_active',
        'mutant_breach_active',
        # 0.4.5
        'raider_raid_active', 'chemical_cloud_active', 'heating_failure_active',
    ]
    for attr in attrs:
        if not hasattr(gm, attr):
            setattr(gm, attr, False)

    extra_attrs = [
        'celebration_station', 'workshop_station',
        'breach_station', 'frost_station',
        # 0.4.5
        'chemical_cloud_station', 'heating_station',
    ]
    for attr in extra_attrs:
        if not hasattr(gm, attr):
            setattr(gm, attr, None)

    list_attrs = ['frost_connections', 'chemical_cloud_connections', 'raider_raid_stations']
    for attr in list_attrs:
        if not hasattr(gm, attr):
            setattr(gm, attr, [])

    if not hasattr(gm, 'raider_raid_killed'):
        gm.raider_raid_killed = False


async def trigger_event(bot: commands.Bot, game_manager):
    global current_event

    if current_event.active:
        logger.warning("🌍 Попытка запустить ивент, когда уже есть активный")
        return

    events = get_events()

    available_events = []
    for event in events:
        if event["id"] in ["trade_caravan", "grand_sale", "station_celebration", "stalker_workshop"]:
            if not get_trade_zones():
                continue
        if event["id"] in ["mutant_activity"]:
            if len(get_danger_stations()) < 3:
                continue
        if event["id"] in ["mutant_breach"]:
            if not get_stations_with_defense_below(6):
                continue
        # 0.4.5
        if event["id"] == "chemical_cloud":
            candidates = [
                sid for sid, sdata in MAP_DATA["станции"].items()
                if sdata.get("danger", 0) in (4, 5)
            ]
            if not candidates:
                continue
        if event["id"] == "heating_failure":
            if not get_safe_stations():
                continue
        if event["id"] == "raider_raid":
            if not BALANCE.get('raider_raid', {}).get('stations'):
                continue
        available_events.append(event)

    if not available_events:
        logger.warning("🌍 Нет доступных ивентов для запуска")
        return

    event = random.choice(available_events)

    # Подставляем конкретику
    if event["id"] == "trade_caravan":
        station = get_random_trade_zone()
        if station:
            station_name = MAP_DATA["станции"][station]["name"]
            event["text"] = f"🛒 **Торговый караван на {station_name}!** Скидка 20% на все товары на 15 минут!"
    elif event["id"] == "grand_sale":
        station = get_random_trade_zone()
        if station:
            station_name = MAP_DATA["станции"][station]["name"]
            event["text"] = f"🏪 **Грандиозная распродажа на {station_name}!** Скидка 30% на 15 минут!"
    elif event["id"] == "station_celebration":
        station = get_random_trade_zone()
        if station:
            station_name = MAP_DATA["станции"][station]["name"]
            event["text"] = f"🎉 **Праздник на {station_name}!** Зайдите и получите +3 еды!"
    elif event["id"] == "stalker_workshop":
        station = get_random_trade_zone()
        if station:
            station_name = MAP_DATA["станции"][station]["name"]
            event["text"] = f"🔧 **Мастерская сталкеров на {station_name}!**"
    elif event["id"] == "mutant_activity":
        stations = get_random_stations(5, get_danger_stations())
        if stations:
            station_names = [MAP_DATA["станции"][s]["name"] for s in stations]
            event["text"] = f"⚠️ **Повышенная активность мутантов на {', '.join(station_names)}!**"
    elif event["id"] == "frost":
        # === 0.4.4: выбираем станцию и её соседей ===
        station = random.choice(list(MAP_DATA["станции"].keys()))
        station_name = MAP_DATA["станции"][station]["name"]
        nearby = get_nearby_stations(station, 2)
        nearby_names = [MAP_DATA["станции"][s]["name"] for s in nearby]

        game_manager.frost_station = station
        game_manager.frost_connections = list(nearby)

        event["text"] = (
            f"❄️ **Заморозки у {station_name}!** Вентиляция вышла из строя.\n"
            f"🌬️ Переходы {', '.join(nearby_names)} страдают от адского холода.\n"
            f"🔥 Согревайтесь у костра!"
        )
    elif event["id"] == "mutant_breach":
        stations = get_stations_with_defense_below(6)
        station = random.choice(stations) if stations else None
        if station:
            station_name = MAP_DATA["станции"][station]["name"]
            defense = get_station_defense(station)
            event["text"] = f"🧟 **Мутанты прорвали оборону на {station_name}!** (Защита: {defense}/10)"
            result = apply_damage_to_players_on_station(
                game_manager, station, 1.0,
                f"💀 **{station_name}** атакована мутантами!"
            )
            if result:
                event["text"] += f"\n{result}"
    # 0.4.5
    elif event["id"] == "raider_raid":
        stations = BALANCE.get('raider_raid', {}).get('stations', [])
        station_names = [MAP_DATA["станции"][s]["name"] for s in stations if s in MAP_DATA["станции"]]
        event["text"] = (
            f"☠️ **Рейдерский захват!** Рейдер со своими носачами "
            f"решил запугать народ на Севастопольской ГЭС!\n"
            f"📍 Атакованы: {', '.join(station_names)}\n"
            f"⚔️ Рейдер появляется со 100% шансом на этих станциях.\n"
            f"💀 Убейте его, чтобы закончить ивент досрочно!"
        )
    elif event["id"] == "chemical_cloud":
        # Значения уже установлены в _apply_chemical_cloud, но текст формируем тут
        # (само apply вызовется ниже). Сначала вычислим станцию и соседей для текста.
        cfg = BALANCE.get('chemical_cloud', {})
        danger_min = cfg.get('target_danger_min', 4)
        danger_max = cfg.get('target_danger_max', 5)

        candidates = [
            sid for sid, sdata in MAP_DATA["станции"].items()
            if danger_min <= sdata.get("danger", 0) <= danger_max
        ]
        if candidates:
            station = random.choice(candidates)
            connections = get_all_neighbors(station)
            station_name = MAP_DATA["станции"][station]["name"]
            nearby_names = [MAP_DATA["станции"][s]["name"] for s in connections]
            event["text"] = (
                f"☣️ **Химический выброс!** Неизвестное вещество "
                f"распространяется с **{station_name}**.\n"
                f"📍 Заражены также: {', '.join(nearby_names) if nearby_names else '—'}\n"
                f"☣️ Без защиты — 25 хим. заражения за переход.\n"
                f"💡 Используйте РХБЗ-комплект или полный противогаз."
            )
    elif event["id"] == "heating_failure":
        safe = get_safe_stations()
        if safe:
            station = random.choice(safe)
            station_name = MAP_DATA["станции"][station]["name"]
            event["text"] = (
                f"🥶 **Отопление вышло из строя на {station_name}!**\n"
                f"❄️ Переход на неё и с неё наносит 25 холода без защиты.\n"
                f"🔥 Согревайтесь у костра!"
            )

    logger.info(f"🌍 ЗАПУСК ИВЕНТА: {event['id']} (тип: {event['type']}, длительность: {event['duration']} мин)")

    try:
        event["apply"](game_manager)
        logger.info(f"🌍 Эффект {event['id']} применен")
    except Exception as e:
        logger.error(f"🌍 Ошибка применения эффекта ивента {event['id']}: {e}")
        return

    current_event.active = True
    current_event.event = event
    current_event.time_remaining = event["duration"]
    current_event.start_time = asyncio.get_event_loop().time()

    if event["id"] == "frost":
        await _apply_frost_to_zone_players(bot, game_manager)

    await send_event_notification(bot, game_manager, event)

    async def remove_event():
        await asyncio.sleep(event["duration"] * 60)
        await end_event(bot, game_manager, event)

    current_event.task = asyncio.create_task(remove_event())


async def _apply_frost_to_zone_players(bot, game_manager):
    """Когда ивент Заморозки стартует, все игроки в зоне мгновенно получают 25 холода."""
    from .cold_system import process_cold_on_event_start, ensure_cold_fields
    from database.db import save_player

    frost_station = getattr(game_manager, 'frost_station', None)
    frost_connections = getattr(game_manager, 'frost_connections', []) or []
    zone = [frost_station] + frost_connections

    affected = []
    for player in game_manager.players.values():
        if not player.is_alive:
            continue
        # 0.4.6: спящих не трогаем
        if getattr(player, 'is_sleeping', False):
            continue
        if player.location not in zone:
            continue

        ensure_cold_fields(player)
        result = process_cold_on_event_start(player, in_frost_zone=True)

        if result.get('cold_message'):
            affected.append(f"🥶 {player.name}: {result['cold_message']}")

        asyncio.create_task(save_player(player))

    if affected:
        try:
            channel = await get_event_channel(bot, game_manager)
            if channel:
                text = "❄️ **Заморозки накрыли игроков в зоне:**\n" + "\n".join(affected)
                await channel.send(text)
        except Exception as e:
            logger.error(f"Ошибка оповещения о заморозках: {e}")


async def end_event(bot: commands.Bot, game_manager, event):
    global current_event

    logger.info(f"🌍 ЗАВЕРШЕНИЕ ИВЕНТА: {event['id']}")

    try:
        if event["remove"]:
            event["remove"](game_manager)
            logger.info(f"🌍 Эффект {event['id']} снят")
    except Exception as e:
        logger.error(f"🌍 Ошибка снятия эффекта ивента {event['id']}: {e}")

    current_event.active = False
    current_event.event = None
    current_event.time_remaining = 0
    current_event.task = None

    embed = discord.Embed(
        title="⏰ Ивент завершен",
        description=f"**{event['text'].split('!')[0] + '!'}** завершил своё действие.",
        color=discord.Color.dark_gray()
    )
    embed.set_footer(text="Следующий ивент скоро начнётся")

    channel = await get_event_channel(bot, game_manager)
    if channel:
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"🌍 Ошибка отправки уведомления о завершении ивента: {e}")


async def send_event_notification(bot: commands.Bot, game_manager, event):
    color = get_event_color(event["type"])
    icon = get_event_icon(event["type"])

    description = f"{event['text']}\n\n"
    description += f"⏱️ **Длительность:** {event['duration']} минут\n"
    description += f"📊 **Тип:** {'✅ Бафф' if event['type'] == 'buff' else '❌ Дебафф' if event['type'] == 'debuff' else 'ℹ️ Нейтральный'}\n"
    description += f"\n💡 **Эффект:** {event.get('description', 'Нет описания')}"

    embed = discord.Embed(
        title=f"{icon} ГЛОБАЛЬНЫЙ ИВЕНТ",
        description=description,
        color=color
    )
    embed.set_footer(text="Следите за новыми событиями в Метро! Используйте /event для информации")

    channel = await get_event_channel(bot, game_manager)
    if channel:
        try:
            await channel.send(embed=embed)
            if game_manager.game_channel and game_manager.game_channel != channel.id:
                game_channel = bot.get_channel(game_manager.game_channel)
                if game_channel:
                    await game_channel.send(f"🌍 **Глобальный ивент запущен!** Используйте `/event` для информации.")
        except Exception as e:
            logger.error(f"🌍 Ошибка отправки уведомления об ивенте: {e}")


async def get_event_channel(bot: commands.Bot, game_manager):
    if EVENT_CHANNEL_ID:
        channel = bot.get_channel(EVENT_CHANNEL_ID)
        if channel:
            return channel

    if game_manager.game_channel:
        channel = bot.get_channel(game_manager.game_channel)
        if channel:
            return channel

    return None