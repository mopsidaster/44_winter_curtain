# -*- coding: utf-8 -*-
# func/independent_traders.py - Независимые торговцы (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.8.7 — новый модуль. Ганс и Радеон, их лояльность и задания.

import json
import os
import random
import time
from typing import Optional

from config.map_config import BALANCE, WEAPONS, ITEMS, MODULES, ARMOR
from config.map_config import CONFIG_DIR

from utils.logger import get_logger

logger = get_logger()


# ==================== ЗАГРУЗКА ====================

TRADERS_FILE = os.path.join(CONFIG_DIR, "independent_traders.json")

_traders_data = {}
_traders_loaded = False


def _load_traders():
    global _traders_data, _traders_loaded
    if _traders_loaded:
        return

    try:
        with open(TRADERS_FILE, 'r', encoding='utf-8') as f:
            _traders_data = json.load(f).get("traders", {})
        _traders_loaded = True
        logger.info(
            f"[TRADERS] Загружено независимых торговцев: {len(_traders_data)}"
        )
    except FileNotFoundError:
        logger.error(f"[TRADERS] Файл {TRADERS_FILE} не найден")
        _traders_data = {}
        _traders_loaded = True
    except Exception as e:
        logger.error(f"[TRADERS] Ошибка загрузки: {e}", exc_info=True)
        _traders_data = {}
        _traders_loaded = True


_load_traders()


# ==================== ДОСТУП ====================

def get_all_traders() -> dict:
    return dict(_traders_data)


def get_trader(trader_id: str) -> dict:
    return _traders_data.get(trader_id, {}) or {}


def get_trader_name(trader_id: str) -> str:
    return get_trader(trader_id).get("name", trader_id)


def get_trader_emoji(trader_id: str) -> str:
    return get_trader(trader_id).get("emoji", "🧔")


def get_trader_station(trader_id: str) -> str:
    return get_trader(trader_id).get("station", "")


def get_trader_faction(trader_id: str) -> str:
    return get_trader(trader_id).get("faction", "loners")


# ==================== ЛОЯЛЬНОСТЬ ====================

def get_loyalty_thresholds() -> dict:
    cfg = BALANCE.get("independent_traders", {}) or {}
    return cfg.get("loyalty_thresholds", {"0": 0, "1": 100, "2": 200})


def get_player_trader_loyalty(player, trader_id: str) -> int:
    """0..200 очков."""
    if not hasattr(player, 'trader_loyalty') \
            or not isinstance(player.trader_loyalty, dict):
        player.trader_loyalty = {}
    try:
        return int(player.trader_loyalty.get(trader_id, 0) or 0)
    except (TypeError, ValueError):
        return 0


def set_player_trader_loyalty(player, trader_id: str, value: int):
    if not hasattr(player, 'trader_loyalty') \
            or not isinstance(player.trader_loyalty, dict):
        player.trader_loyalty = {}
    player.trader_loyalty[trader_id] = max(0, min(int(value), 200))


def add_player_trader_loyalty(player, trader_id: str, amount: int) -> int:
    current = get_player_trader_loyalty(player, trader_id)
    new_value = current + int(amount)
    set_player_trader_loyalty(player, trader_id, new_value)
    if amount != 0:
        logger.info(
            f"[TRADERS] {getattr(player, 'name', '?')}: лояльность "
            f"{trader_id} {amount:+d} ({current} → {new_value})"
        )
    return get_player_trader_loyalty_level(player, trader_id)


def get_player_trader_loyalty_level(player, trader_id: str) -> int:
    """0, 1 или 2."""
    points = get_player_trader_loyalty(player, trader_id)
    thresholds = get_loyalty_thresholds()
    level = 0
    for lvl in (1, 2):
        if points >= thresholds.get(str(lvl), 0):
            level = lvl
        else:
            break
    return level


def get_trader_loyalty_progress(player, trader_id: str) -> dict:
    points = get_player_trader_loyalty(player, trader_id)
    level = get_player_trader_loyalty_level(player, trader_id)
    thresholds = get_loyalty_thresholds()

    if level >= 2:
        return {
            "points": points, "level": 2,
            "next_level": None, "next_threshold": None, "progress": 1.0,
        }

    next_level = level + 1
    next_threshold = thresholds.get(str(next_level), 200)
    prev_threshold = thresholds.get(str(level), 0)
    span = next_threshold - prev_threshold

    return {
        "points": points, "level": level,
        "next_level": next_level, "next_threshold": next_threshold,
        "progress": (
            max(0.0, min(1.0, (points - prev_threshold) / span))
            if span > 0 else 0.0
        ),
    }


# ==================== АССОРТИМЕНТ ====================

def get_assortment_for_player(player, trader_id: str) -> dict:
    """
    Возвращает {"level_0": [...], "level_1": [...], "level_2": [...]}
    с учётом лояльности игрока.
    """
    trader = get_trader(trader_id)
    assortment = trader.get("assortment", {})

    level = get_player_trader_loyalty_level(player, trader_id)

    result = {
        "level_0": list(assortment.get("level_0", [])),
        "level_1": [],
        "level_2": [],
    }

    if level >= 1:
        result["level_1"] = list(assortment.get("level_1", []))
    if level >= 2:
        result["level_2"] = list(assortment.get("level_2", []))

    return result


def get_visible_items(player, trader_id: str) -> list:
    """
    Все видимые игроку предметы с учётом уровня лояльности.
    Возвращает список (item_id, kind, data) где kind:
      'weapon', 'module', 'ammo_caliber', 'armor'
    """
    trader = get_trader(trader_id)
    level = get_player_trader_loyalty_level(player, trader_id)
    items = []

    assortment = trader.get("assortment", {})
    levels_to_show = ["level_0"]
    if level >= 1:
        levels_to_show.append("level_1")
    if level >= 2:
        levels_to_show.append("level_2")

    for lvl in levels_to_show:
        for item_id in assortment.get(lvl, []):
            kind = _resolve_item_kind(item_id)
            if kind:
                items.append((item_id, kind))

    return items


def _resolve_item_kind(item_id: str) -> Optional[str]:
    if item_id in WEAPONS:
        wtype = WEAPONS[item_id].get("type")
        if wtype == "grenade":
            return "grenade"
        if wtype == "throwing_knife":
            return "knife"
        return "weapon"
    if item_id in MODULES.get("modules", {}):
        return "module"
    if item_id in ARMOR.get("armor_sets", {}):
        return "armor"
    if item_id.startswith("патроны_"):
        return "ammo_caliber"
    return None


def get_ammo_caliber_from_item(item_id: str) -> str:
    """'патроны_5.56x45' -> '5.56x45'."""
    return item_id.replace("патроны_", "")


# ==================== ЦЕНЫ И СКИДКИ ====================

def get_trader_price(base_price: int, player, trader_id: str) -> int:
    """Скидка зависит от уровня лояльности: 0% / 5% / 10%."""
    level = get_player_trader_loyalty_level(player, trader_id)
    discount = {0: 0.0, 1: 0.05, 2: 0.10}.get(level, 0.0)
    return max(1, int(base_price * (1.0 - discount)))


def get_hans_loot_sell_multiplier(player) -> float:
    """Ганс 0 ур: продажа лута с мутантов ×2."""
    if get_player_trader_loyalty_level(player, "ганс") >= 0:
        cfg = BALANCE.get("independent_traders", {}) or {}
        return float(cfg.get("hans_loot_sell_multiplier", 2.0))
    return 1.0


def get_radeon_junk_sell_bonus(player) -> float:
    """Радеон 0 ур: +20% к продаже хлама."""
    if get_player_trader_loyalty_level(player, "радеон") >= 0:
        cfg = BALANCE.get("independent_traders", {}) or {}
        bonus = float(cfg.get("radeon_junk_sell_bonus_percent", 20))
        return 1.0 + bonus / 100.0
    return 1.0


# ==================== ЗАДАНИЯ ====================

_trader_boards: dict[str, list] = {}
_trader_board_last_refresh: dict[str, float] = {}


def _get_task_cfg() -> dict:
    cfg = BALANCE.get("independent_traders", {}) or {}
    return cfg.get("tasks", {}) or {}


def _get_refresh_interval() -> int:
    cfg = BALANCE.get("independent_traders", {}) or {}
    hours = int(cfg.get("task_board_refresh_hours", 3))
    return hours * 3600


def get_trader_board(trader_id: str) -> list:
    """Доска заданий торговца (обновляется раз в N часов)."""
    now = time.time()
    interval = _get_refresh_interval()

    if (trader_id not in _trader_boards
            or (now - _trader_board_last_refresh.get(trader_id, 0) > interval)):
        _trader_boards[trader_id] = generate_trader_tasks(trader_id)
        _trader_board_last_refresh[trader_id] = now
        logger.info(f"[TRADERS] Доска {trader_id} обновлена")
    return _trader_boards[trader_id]


def refresh_trader_board_force(trader_id: str):
    _trader_boards[trader_id] = generate_trader_tasks(trader_id)
    _trader_board_last_refresh[trader_id] = time.time()
    logger.info(f"[TRADERS] Доска {trader_id} принудительно обновлена")


def refresh_all_boards():
    for tid in get_all_traders():
        refresh_trader_board_force(tid)


def generate_trader_tasks(trader_id: str) -> list:
    """
    Только gather и delivery. Без kill и pay.
    """
    cfg = _get_task_cfg()
    count = int(cfg.get("count_per_board", 3))
    tasks = []

    from .map_data import MAP_DATA

    for _ in range(count):
        task_type = random.choice(["gather", "delivery"])
        task = {
            "type": task_type,
            "faction_id": trader_id,
            "trader_id": trader_id,
            "completed": False,
            "progress": 0,
            "ready_to_claim": False,
        }

        if task_type == "gather":
            item_id = random.choice(cfg.get("gather_items", ["хвост_упыря"]))
            item_name = ITEMS.get("sell", {}).get(item_id, {}).get("name", item_id)
            task.update({
                "item_id": item_id,
                "item_name": item_name,
                "count": random.randint(
                    cfg.get("gather_count_min", 1),
                    cfg.get("gather_count_max", 3),
                ),
            })
        else:
            cargo_id = f"груз_т{random.randint(1000, 9999)}"
            trade_stations = [
                sid for sid, st in MAP_DATA["станции"].items()
                if ("торговая" in st.get("types", [])
                    or st.get("type") == "торговая")
            ]
            target_st = random.choice(trade_stations) if trade_stations else "ясенево"
            target_faction = MAP_DATA["станции"][target_st].get("faction", "")
            reward = random.randint(
                cfg.get("delivery_reward_min", 100),
                cfg.get("delivery_reward_max", 300),
            )
            task.update({
                "cargo_id": cargo_id,
                "target_station": target_st,
                "target_faction": target_faction,
                "reward": reward,
                "amount": reward,
            })

        task["loyalty_reward"] = random.randint(
            cfg.get("loyalty_base_min", 5),
            cfg.get("loyalty_base_max", 15),
        )
        task["nickels_reward"] = (
            random.randint(
                cfg.get("nickels_base_min", 20),
                cfg.get("nickels_base_max", 60),
            )
            if task_type == "gather" else 0
        )
        task["task_id"] = (
            f"{trader_id}_{random.randint(100000, 999999)}"
        )
        tasks.append(task)

    return tasks


def get_task_by_id(trader_id: str, task_id: str) -> dict:
    for t in get_trader_board(trader_id):
        if t.get("task_id") == task_id:
            return t
    return {}


def format_trader_task(task: dict) -> str:
    t = task.get("type")
    if t == "gather":
        return (
            f"📦 **Принести {task['item_name']} ×{task['count']}**\n"
            f"   Награда: +{task['loyalty_reward']} лояльности, "
            f"+{task['nickels_reward']} никелей"
        )
    if t == "delivery":
        from .map_data import MAP_DATA
        target_name = MAP_DATA["станции"].get(
            task.get("target_station"), {}
        ).get("name", "Неизвестно")
        reward = task.get("amount", task.get("reward", 0))
        return (
            f"🚚 **Доставить груз**\n"
            f"   Пункт назначения: **{target_name}**\n"
            f"   Награда: +{task['loyalty_reward']} лояльности, "
            f"+{reward} никелей"
        )
    return "❓ Неизвестное задание"


def claim_trader_task(player, trader_id: str, task_id: str) -> tuple:
    """0.4.8.7.3: разрешаем сдачу gather и delivery."""
    tasks = getattr(player, 'active_tasks', []) or []
    target_task = next(
        (t for t in tasks if t.get("task_id") == task_id), None
    )

    if not target_task:
        return False, "❌ Задание не найдено."
    if target_task.get("completed"):
        return False, "❌ Задание уже выполнено."

    ttype = target_task.get("type")

    if ttype == "gather":
        needed = target_task.get("count", 0)
        item_id = target_task.get("item_id")
        hlam = player.inventory.get("хлам", []) or []
        if hlam.count(item_id) < needed:
            return False, (
                f"❌ Нужно **{needed}** × {target_task.get('item_name')}, "
                f"у вас **{hlam.count(item_id)}**."
            )
        for _ in range(needed):
            if item_id in hlam:
                hlam.remove(item_id)
        player.inventory["хлам"] = hlam

    elif ttype == "delivery":
        # 0.4.8.7.3: проверяем, что игрок на станции назначения
        current = player.location
        target_station = target_task.get("target_station")
        if current != target_station:
            from .map_data import MAP_DATA
            target_name = MAP_DATA["станции"].get(
                target_station, {}
            ).get("name", "?")
            return False, (
                f"❌ Доставьте груз на **{target_name}** и вернитесь."
            )
        # Снимаем груз
        cargo_id = target_task.get("cargo_id")
        hlam = player.inventory.get("хлам", []) or []
        if cargo_id and cargo_id in hlam:
            hlam.remove(cargo_id)
        if "временный_пропуск" in hlam:
            hlam.remove("временный_пропуск")
        player.inventory["хлам"] = hlam

    loyalty_reward = target_task.get("loyalty_reward", 0)
    nickels_reward = target_task.get("nickels_reward", 0)
    reward_amount = target_task.get("amount", target_task.get("reward", 0))

    add_player_trader_loyalty(player, trader_id, loyalty_reward)
    if nickels_reward > 0:
        player.inventory["никели"] = (
                player.inventory.get("никели", 0) + nickels_reward
        )
    if reward_amount > 0 and ttype == "delivery":
        player.inventory["никели"] = (
                player.inventory.get("никели", 0) + reward_amount
        )

    target_task["completed"] = True
    target_task["ready_to_claim"] = False
    target_task["rewarded"] = True

    return True, (
        f"✅ Задание сдано!\n"
        f"💠 +{loyalty_reward} лояльности торговцу "
        f"**{get_trader_name(trader_id)}**\n"
        f"💰 +{nickels_reward + reward_amount} никелей"
    )