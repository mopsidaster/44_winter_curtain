# -*- coding: utf-8 -*-
# func/factions.py - Система фракций (0.4.8.8)
#
# ИСТОРИЯ:
#   0.4.8.3 — Вступительные квесты, журнал, доставка грузов.
#   0.4.8.8 — Награды за задания получает каждый участник активной
#             бригады (не только лидер). Бригада привязана к фракции лидера.

import random
import time
from config.map_config import (
    FACTIONS_DICT, NPCS_DICT, LOYALTY_THRESHOLDS, RELATION_TYPES,
    BALANCE, ITEMS, MUTANTS,
)
from .map_data import MAP_DATA
from utils.logger import get_logger

logger = get_logger()

MEDIATOR_STATIONS = ["новые_черемушки", "севастопольская", "каховская"]
_mediator_last_move_time = time.time()
_mediator_current_station_idx = 0


# ==================== ДОСТУП К ДАННЫМ ====================

def get_faction_data(faction_id: str) -> dict:
    return FACTIONS_DICT.get(faction_id, {}) if faction_id else {}


def get_faction_name(faction_id: str) -> str:
    return get_faction_data(faction_id).get("name", faction_id)


def get_faction_emoji(faction_id: str) -> str:
    data = get_faction_data(faction_id)
    return data.get("emoji") or data.get("emoji_fallback", "🚩")


def get_all_factions() -> dict:
    return FACTIONS_DICT


def get_npc_data(npc_id: str) -> dict:
    return NPCS_DICT.get(npc_id, {})


def get_npcs_on_station(station_id: str) -> list:
    global _mediator_last_move_time, _mediator_current_station_idx

    now = time.time()
    if now - _mediator_last_move_time > 3600:
        _mediator_current_station_idx = (
                (_mediator_current_station_idx + 1) % len(MEDIATOR_STATIONS)
        )
        _mediator_last_move_time = now

    dynamic_station = MEDIATOR_STATIONS[_mediator_current_station_idx]

    result = []
    for npc_id, npc in NPCS_DICT.items():
        npc_station = (
            dynamic_station if npc_id == "посредник_бандитов"
            else npc.get("station")
        )
        if npc_station == station_id:
            result.append({"id": npc_id, **npc, "station": npc_station})
    return result


def get_station_faction(station_id: str) -> str:
    return MAP_DATA["станции"].get(station_id, {}).get("faction") or ""


# ==================== ОТНОШЕНИЯ ====================

def get_relation_types() -> dict:
    return RELATION_TYPES


def get_relation_meta(relation_id: str) -> dict:
    return RELATION_TYPES.get(
        relation_id,
        {"name": relation_id, "emoji": "❓", "color": 0x808080},
    )


def get_player_relation_to(player, faction_id: str) -> str:
    if not faction_id:
        return "нейтральная"
    relations = getattr(player, 'faction_relations', {}) or {}
    if faction_id in relations:
        return relations[faction_id]

    player_faction = getattr(player, 'faction', 'loners')
    if player_faction == faction_id:
        return "дружественная"

    auto_relations = get_faction_data(player_faction).get(
        "relations_to_others", {}
    )
    if faction_id in auto_relations:
        return auto_relations[faction_id]
    return get_faction_data(faction_id).get("default_relation", "нейтральная")


def set_player_relation_to(player, faction_id: str, relation_id: str):
    if relation_id in RELATION_TYPES:
        if not hasattr(player, 'faction_relations') \
                or not isinstance(player.faction_relations, dict):
            player.faction_relations = {}
        player.faction_relations[faction_id] = relation_id


def shift_relation(player, faction_id: str, delta: int):
    order = ["враждебная", "нейтральная", "дружественная"]
    current = get_player_relation_to(player, faction_id)
    try:
        idx = order.index(current)
    except ValueError:
        idx = 1
    new_idx = max(0, min(len(order) - 1, idx + delta))
    if order[new_idx] != current:
        set_player_relation_to(player, faction_id, order[new_idx])


# ==================== ЛОЯЛЬНОСТЬ ====================

def get_player_loyalty(player, faction_id: str) -> int:
    try:
        return int(
            (getattr(player, 'faction_loyalty', {}) or {}).get(faction_id, 0)
            or 0
        )
    except (TypeError, ValueError):
        return 0


def set_player_loyalty(player, faction_id: str, value: int):
    if not hasattr(player, 'faction_loyalty') \
            or not isinstance(player.faction_loyalty, dict):
        player.faction_loyalty = {}
    player.faction_loyalty[faction_id] = max(0, min(int(value), 500))


def add_player_loyalty(player, faction_id: str, amount: int) -> int:
    current = get_player_loyalty(player, faction_id)
    new_value = current + int(amount)
    set_player_loyalty(player, faction_id, new_value)
    if amount != 0:
        logger.info(
            f"{getattr(player, 'name', '?')}: лояльность {faction_id} "
            f"{amount:+d} ({current} → {new_value})"
        )
    return get_loyalty_level(new_value)


def get_loyalty_level(points: int) -> int:
    if points <= 0:
        return 0
    level = 0
    for lvl in range(1, 6):
        if points >= LOYALTY_THRESHOLDS.get(str(lvl), 0):
            level = lvl
        else:
            break
    return level


def get_player_loyalty_level(player, faction_id: str) -> int:
    return get_loyalty_level(get_player_loyalty(player, faction_id))


def get_loyalty_progress(player, faction_id: str) -> dict:
    points = get_player_loyalty(player, faction_id)
    level = get_loyalty_level(points)
    if level >= 5:
        return {
            "points": points, "level": 5,
            "next_level": None, "next_threshold": None, "progress": 1.0,
        }
    next_level = level + 1
    next_threshold = LOYALTY_THRESHOLDS.get(str(next_level), 500)
    prev_threshold = LOYALTY_THRESHOLDS.get(str(level), 0)
    span = next_threshold - prev_threshold
    return {
        "points": points, "level": level,
        "next_level": next_level, "next_threshold": next_threshold,
        "progress": (
            max(0.0, min(1.0, (points - prev_threshold) / span))
            if span > 0 else 0.0
        ),
    }


# ==================== ВСТУПЛЕНИЕ ВО ФРАКЦИЮ ====================

def get_join_quest_requirements(faction_id: str) -> dict:
    quests = {
        "antiquars": {"kills": {}, "items": {"чешуя_червя": 3}, "nickels": 0},
        "bandits": {"kills": {}, "items": {}, "nickels": 3000},
        "yasenevo": {"kills": {}, "items": {"клык_носача": 3}, "nickels": 0},
        "gess": {"kills": {}, "items": {"жетон_рейдера": 1}, "nickels": 0},
        "gutagi": {"kills": {}, "items": {"шкура_мерзляка": 5}, "nickels": 500},
    }
    return quests.get(faction_id, {})


def check_join_quest(player, faction_id: str) -> tuple:
    req = get_join_quest_requirements(faction_id)
    if not req:
        return True, "OK"
    missing = []

    if req.get("nickels", 0) > 0 \
            and player.inventory.get("никели", 0) < req["nickels"]:
        missing.append(f"{req['nickels']} никелей")

    for item_id, count in req.get("items", {}).items():
        hlam = player.inventory.get("хлам", []) or []
        if hlam.count(item_id) < count:
            item_name = ITEMS.get('sell', {}).get(item_id, {}).get(
                'name', item_id
            )
            missing.append(f"{count} × {item_name}")

    if missing:
        return False, f"❌ Не хватает: {', '.join(missing)}"
    return True, "OK"


def can_join_faction(player, faction_id: str) -> tuple:
    if not faction_id:
        return False, "❌ Неверный ID фракции."
    current_faction = getattr(player, 'faction', 'loners')
    if current_faction == faction_id:
        return False, "❌ Вы уже состоите в этой фракции."
    if current_faction != 'loners':
        return False, (
            f"❌ Вы уже состоите во фракции "
            f"**{get_faction_name(current_faction)}**."
        )

    loyalty_level = get_player_loyalty_level(player, faction_id)
    can_join_level = 3
    for lvl, lvl_data in get_faction_data(faction_id).get(
            "loyalty_levels", {}).items():
        if isinstance(lvl_data, dict) and lvl_data.get("can_join"):
            can_join_level = int(lvl)
            break

    if loyalty_level < can_join_level:
        return False, (
            f"🔒 Для вступления во фракцию "
            f"**{get_faction_name(faction_id)}** нужен уровень лояльности "
            f"**{can_join_level}** (у вас {loyalty_level})."
        )

    ok, reason = check_join_quest(player, faction_id)
    if not ok:
        return False, f"📜 **Вступительный квест не выполнен:**\n{reason}"

    return True, "OK"


def join_faction(player, faction_id: str) -> tuple:
    ok, reason = can_join_faction(player, faction_id)
    if not ok:
        return False, reason

    req = get_join_quest_requirements(faction_id)
    if req.get("nickels", 0) > 0:
        player.inventory['никели'] -= req["nickels"]
    for item_id, count in req.get("items", {}).items():
        hlam = player.inventory.get("хлам", []) or []
        for _ in range(count):
            if item_id in hlam:
                hlam.remove(item_id)
        player.inventory['хлам'] = hlam

    player.faction = faction_id
    fname = get_faction_name(faction_id)
    set_player_relation_to(player, faction_id, "дружественная")

    player.remove_task(f"join_{faction_id}")

    msg = f"✅ Вы успешно вступили во фракцию **{fname}**!"

    if faction_id == "gutagi":
        if "ганза_броня" not in player.armor_inventory:
            player.armor_inventory.append("ганза_броня")
            msg += (
                "\n🎁 Получена **Лёгкая Броня Охранника "
                "Гутагского Периметра**."
            )
        if "ганза_зш1" not in player.armor_inventory:
            player.armor_inventory.append("ганза_зш1")
            msg += "\n🎁 Получен **ЗШ-1 Охранника Гутагского Периметра**."

    # 0.4.8.8: обновляем фракцию бригады, если игрок — лидер
    try:
        from .social.brigade_manager import brigade_manager
        from database.db import get_db
        brigade = brigade_manager.get_user_brigade(player.user_id)
        if brigade and brigade.is_leader(player.user_id):
            brigade.faction_id = faction_id
            logger.info(
                f"[Brigade] Фракция бригады {brigade.brigade_id} → {faction_id}"
            )
    except Exception as e:
        logger.error(f"[FACTIONS] join_faction brigade: {e}")

    logger.info(f"{player.name} вступил во фракцию {faction_id}")
    return True, msg


# ==================== ДОСТУП НА СТАНЦИИ ====================

def can_enter_station_with_faction_full(player, station_id: str) -> tuple:
    st = MAP_DATA["станции"].get(station_id, {})
    name, faction_id = st.get("name", station_id), st.get("faction", "")
    is_member = (getattr(player, 'faction', 'loners') == faction_id)
    loyalty_level = get_player_loyalty_level(player, faction_id)

    if st.get("surface_lock"):
        if getattr(player, 'surface_unlocked', False):
            pass
        elif loyalty_level >= 3:
            pass
        else:
            return False, (
                f"🚫 **{name}** закрыта. Нужна лояльность 3+ у "
                f"{get_faction_name(faction_id)} или открытый проход "
                f"на поверхность."
            ), ""
    elif st.get("faction_lock") and not is_member and loyalty_level < 3:
        return False, (
            f"🚫 Территория **{get_faction_name(faction_id)}**. "
            f"Нужно членство или лояльность 3+ (у вас {loyalty_level})."
        ), ""

    warning = ""
    if faction_id and not is_member \
            and get_player_relation_to(player, faction_id) == "враждебная":
        warning = (
            f"⚠️ **{name}** — территория {get_faction_name(faction_id)}. "
            f"Они враждебны. Готовьтесь к бою."
        )
    return True, "OK", warning


def get_trade_discount_for_faction(player, faction_id: str) -> float:
    if not faction_id:
        return 1.0
    loyalty_level = get_player_loyalty_level(player, faction_id)
    levels = get_faction_data(faction_id).get("loyalty_levels", {})
    discount = 0
    for lvl in range(1, loyalty_level + 1):
        for bonus in levels.get(str(lvl), {}).get("bonuses", []):
            if bonus.get("type") == "trade_discount":
                discount = max(discount, int(bonus.get("value", 0)))
    return 1.0 - (discount / 100.0)


def get_station_discount(player, station_id: str) -> float:
    return get_trade_discount_for_faction(
        player, get_station_faction(station_id)
    )


def get_station_discount_percent(player, station_id: str) -> int:
    return int(round((1.0 - get_station_discount(player, station_id)) * 100))


def has_workshop_on_station(player, station_id: str) -> bool:
    faction_id = get_station_faction(station_id)
    return (
        True if not faction_id or faction_id == "loners"
        else get_player_loyalty_level(player, faction_id) >= 1
    )


def get_faction_enemy_type(player, station_id: str) -> str:
    faction_id = get_station_faction(station_id)
    if not faction_id or faction_id == "gutagi":
        return ""
    if getattr(player, 'faction', 'loners') == faction_id:
        return ""
    if get_player_relation_to(player, faction_id) == "враждебная":
        return faction_id
    return ""


def get_faction_human_mutant_id(faction_id: str) -> str:
    return {
        "bandits": "бандит",
        "antiquars": "бандит",
        "yasenevo": "бандит",
        "gess": "бандит",
    }.get(faction_id, "")


def get_faction_human_display_name(faction_id: str) -> str:
    return {
        "bandits": "Бандит",
        "antiquars": "Охранник Антикваров",
        "yasenevo": "Ополченец Общины",
        "gess": "Работяга ГЭС",
    }.get(faction_id, "NPC")


def on_kill_member(player, faction_id: str):
    add_player_loyalty(
        player, faction_id,
        BALANCE.get('factions', {}).get('relation_shift', {}).get(
            'kill_member', -50
        ),
    )
    shift_relation(player, faction_id, -1)


def on_spare_member(player, faction_id: str):
    add_player_loyalty(
        player, faction_id,
        BALANCE.get('factions', {}).get('relation_shift', {}).get(
            'spare_member', 10
        ),
    )


def on_help_member(player, faction_id: str):
    add_player_loyalty(
        player, faction_id,
        BALANCE.get('factions', {}).get('relation_shift', {}).get(
            'help_member', 5
        ),
    )


def format_faction_status(player, faction_id: str) -> str:
    if not faction_id:
        return "—"
    data = get_faction_data(faction_id)
    relation = get_relation_meta(get_player_relation_to(player, faction_id))
    loyalty = get_loyalty_progress(player, faction_id)
    return (
        f"{get_faction_emoji(faction_id)} **{data.get('name', faction_id)}**\n"
        f"   Отношение: {relation['emoji']} {relation['name']}\n"
        f"   Лояльность: {loyalty['points']}/"
        f"{loyalty.get('next_threshold', 500)} (ур. {loyalty['level']})"
    )


def format_all_factions(player) -> str:
    return "\n\n".join(
        [format_faction_status(player, fid) for fid in FACTIONS_DICT.keys()]
    )


# ==================== ДОСКА ЗАДАНИЙ ====================

TASK_TYPE_KILL = "kill"
TASK_TYPE_GATHER = "gather"
TASK_TYPE_PAY = "pay"
TASK_TYPE_DELIVERY = "delivery"


def _get_tasks_config() -> dict:
    return BALANCE.get('factions', {}).get('tasks', {}) or {}


def generate_tasks_for_faction(faction_id: str,
                               player_location: str = None) -> list:
    cfg = _get_tasks_config()
    count = int(cfg.get("count_per_board", 3))
    tasks = []

    for _ in range(count):
        available_types = [TASK_TYPE_KILL, TASK_TYPE_GATHER, TASK_TYPE_PAY]
        if faction_id != "bandits":
            available_types.append(TASK_TYPE_DELIVERY)

        task_type = random.choice(available_types)
        task = {
            "type": task_type, "faction_id": faction_id,
            "completed": False, "progress": 0, "ready_to_claim": False,
        }

        if task_type == TASK_TYPE_KILL:
            target = random.choice(cfg.get("kill_targets", ["упырь"]))
            mutant_name = MUTANTS.get("mutants", {}).get(target, {}).get(
                "name", target
            )
            task.update({
                "target": target, "target_name": mutant_name,
                "count": random.randint(
                    cfg.get("kill_count_min", 2),
                    cfg.get("kill_count_max", 5),
                ),
            })
        elif task_type == TASK_TYPE_GATHER:
            item_id = random.choice(cfg.get("gather_items", ["хвост_упыря"]))
            item_name = ITEMS.get("sell", {}).get(item_id, {}).get(
                "name", item_id
            )
            task.update({
                "item_id": item_id, "item_name": item_name,
                "count": random.randint(
                    cfg.get("gather_count_min", 2),
                    cfg.get("gather_count_max", 4),
                ),
            })
        elif task_type == TASK_TYPE_PAY:
            task.update({
                "amount": random.randint(
                    cfg.get("pay_money_min", 100),
                    cfg.get("pay_money_max", 500),
                ),
                "progress": 0,
            })
        elif task_type == TASK_TYPE_DELIVERY:
            cargo_id = f"груз_{random.randint(1000, 9999)}"

            trade_stations = [
                sid for sid, st in MAP_DATA["станции"].items()
                if "торговая" in st.get("types", [])
                   or st.get("type") == "торговая"
            ]
            if player_location and player_location in trade_stations \
                    and len(trade_stations) > 1:
                trade_stations.remove(player_location)

            target_st = random.choice(trade_stations)
            target_faction = MAP_DATA["станции"][target_st].get("faction", "")

            reward = random.randint(200, 800)
            task.update({
                "cargo_id": cargo_id, "target_station": target_st,
                "target_faction": target_faction,
                "reward": reward, "amount": reward,
            })

        task["loyalty_reward"] = random.randint(
            cfg.get("loyalty_base_min", 10),
            cfg.get("loyalty_base_max", 25),
        )
        task["nickels_reward"] = (
            random.randint(
                cfg.get("nickels_base_min", 30),
                cfg.get("nickels_base_max", 80),
            )
            if task_type != TASK_TYPE_PAY else 0
        )
        task["task_id"] = f"{faction_id}_{random.randint(100000, 999999)}"
        tasks.append(task)

    return tasks


def get_npc_faction_for_tasks(npc_id: str) -> str:
    npc = get_npc_data(npc_id)
    return (
            npc.get("mediates_for") or npc.get("faction")
    ) if npc else ""


def format_task(task: dict) -> str:
    t = task.get("type")
    if t == TASK_TYPE_KILL:
        return (
            f"🗡️ **Убить {task['target_name']}**\n"
            f"   Прогресс: {task.get('progress', 0)}/{task['count']}\n"
            f"   Награда: +{task['loyalty_reward']} лояльности, "
            f"+{task['nickels_reward']} никелей"
        )
    elif t == TASK_TYPE_GATHER:
        return (
            f"📦 **Принести {task['item_name']} ×{task['count']}**\n"
            f"   Награда: +{task['loyalty_reward']} лояльности, "
            f"+{task['nickels_reward']} никелей"
        )
    elif t == TASK_TYPE_PAY:
        return (
            f"💰 **Заплатить {task['amount']} никелей**\n"
            f"   Награда: +{task['loyalty_reward']} лояльности"
        )
    elif t == TASK_TYPE_DELIVERY:
        target_name = MAP_DATA["станции"].get(
            task['target_station'], {}
        ).get("name", "Неизвестно")
        reward = task.get('amount', task.get('reward', 0))
        return (
            f"🚚 **Доставить груз**\n"
            f"   Пункт назначения: **{target_name}**\n"
            f"   Награда: +{task['loyalty_reward']} лояльности, "
            f"+{reward} никелей"
        )
    return "❓ Неизвестное задание"


def register_kill_for_tasks(player, mutant_id: str):
    for task in (getattr(player, 'active_tasks', []) or []):
        if task.get("completed") \
                or task.get("type") != TASK_TYPE_KILL \
                or task.get("target") != mutant_id:
            continue
        task["progress"] = task.get("progress", 0) + 1
        if task["progress"] >= task["count"]:
            task["ready_to_claim"] = True


# ==================== 0.4.8.8: ГРУППОВЫЕ НАГРАДЫ ====================

def _get_active_group_members(player) -> list:
    """
    Возвращает список участников активной бригады, включая лидера,
    которые находятся с ним на одной станции.
    Если игрок не лидер или бригада не активна — возвращает [player].
    """
    try:
        from .social.brigade_manager import brigade_manager
        from .game_manager import game_manager
    except Exception:
        return [player]

    brigade = brigade_manager.get_user_brigade(player.user_id)
    if not brigade or not brigade.is_active() \
            or not brigade.is_leader(player.user_id):
        return [player]

    result = []
    for uid in brigade.get_member_ids():
        if uid == player.user_id:
            result.append(player)
            continue
        mate = game_manager.get_player(uid)
        if mate and mate.is_alive and mate.location == player.location:
            result.append(mate)
    return result or [player]


def _apply_rewards_to_group(leader, faction_id: str,
                            loyalty_reward: int, nickels_reward: int):
    """Начисляет лояльность и никели каждому в активной группе."""
    members = _get_active_group_members(leader)
    for p in members:
        if faction_id and loyalty_reward > 0:
            add_player_loyalty(p, faction_id, loyalty_reward)
        if nickels_reward > 0:
            p.inventory['никели'] = (
                    p.inventory.get('никели', 0) + nickels_reward
            )


def claim_task(player, task_id: str) -> tuple:
    tasks = getattr(player, 'active_tasks', []) or []
    target_task = next(
        (t for t in tasks if t.get("task_id") == task_id), None
    )

    if not target_task:
        return False, "❌ Задание не найдено."
    if target_task.get("completed"):
        return False, "❌ Задание уже выполнено."

    ttype = target_task.get("type")

    if ttype == TASK_TYPE_KILL:
        if target_task.get("progress", 0) < target_task.get("count", 0):
            return False, (
                f"❌ Не убито достаточно: "
                f"{target_task.get('progress', 0)}/"
                f"{target_task.get('count', 0)}."
            )

    elif ttype == TASK_TYPE_GATHER:
        needed, item_id = (
            target_task.get("count", 0), target_task.get("item_id")
        )
        hlam = player.inventory.get('хлам', []) or []
        if hlam.count(item_id) < needed:
            return False, (
                f"❌ Нужно **{needed}** × {target_task.get('item_name')}, "
                f"у вас **{hlam.count(item_id)}**."
            )
        for _ in range(needed):
            if item_id in hlam:
                hlam.remove(item_id)
        player.inventory['хлам'] = hlam

    elif ttype == TASK_TYPE_PAY:
        amount = target_task.get("amount", 0)
        if player.inventory.get('никели', 0) < amount:
            return False, (
                f"❌ Нужно **{amount}** никелей, "
                f"у вас **{player.inventory.get('никели', 0)}**."
            )
        player.inventory['никели'] -= amount

    elif ttype == TASK_TYPE_DELIVERY:
        return False, "❌ Груз нужно сдавать через NPC, а не через доску!"

    faction_id = target_task.get("faction_id")
    loyalty_reward = target_task.get("loyalty_reward", 0)
    nickels_reward = target_task.get("nickels_reward", 0)

    # 0.4.8.8: награда каждому участнику активной группы
    _apply_rewards_to_group(
        player, faction_id, loyalty_reward, nickels_reward
    )

    target_task["completed"] = True
    target_task["ready_to_claim"] = False

    group_size = len(_get_active_group_members(player))
    group_note = ""
    if group_size > 1:
        group_note = f"\n👥 Награда выдана **{group_size}** участникам бригады."

    return True, (
        f"✅ Задание сдано!\n"
        f"💠 +{loyalty_reward} лояльности к {get_faction_name(faction_id)}\n"
        f"💰 +{nickels_reward} никелей{group_note}"
    )