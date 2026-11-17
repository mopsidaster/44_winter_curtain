# -*- coding: utf-8 -*-
# func/repair_system.py - Система ремонта (0.4.7.7)
#
# ИСТОРИЯ:
#   0.4.7.6 — изолента, шанс ремонта, навык Инженерия
#   0.4.7.7 — добавлен набор для ремонта (25 прочности)
#
# Механики:
#   • Расходники: изолента (5), набор для ремонта (25).
#   • Шанс ремонта = base_success_chance (45%) + 5% за уровень Инженерии.
#   • Максимум 10 уровней Инженерии → максимум 95%.
#   • Мастерская: ремонт брони за никели (100% успех).
#
# Ремонтировать можно:
#   • Противогаз (gas_mask["прочность"])
#   • Оружие ближнего боя (melee_weapon_durability)
#   • Броня (armor_durability["armor"])
#   • Шлем (armor_durability["helmet"])

import random

from config.map_config import BALANCE, ARMOR, MELEE
from utils.logger import get_logger

logger = get_logger()


# ==================== 0.4.7.7: РАСХОДНИКИ ====================

# Внутренний реестр доступных расходников для ремонта.
# Ключ — inventory_key (как в player.inventory), значение — конфиг.
REPAIR_TOOLS = {
    "изолента": {
        "name": "Изолента",
        "emoji": "🩹",
        "restore": 5,
    },
    "набор_для_ремонта": {
        "name": "Набор для ремонта",
        "emoji": "🧰",
        "restore": 25,
    },
}


def get_tool_config(tool_id: str) -> dict:
    return REPAIR_TOOLS.get(tool_id, {})


def get_tool_restore_amount(tool_id: str) -> int:
    cfg = get_tool_config(tool_id)
    try:
        return int(cfg.get("restore", 0))
    except (TypeError, ValueError):
        return 0


def get_tool_name(tool_id: str) -> str:
    cfg = get_tool_config(tool_id)
    return cfg.get("name", tool_id)


def get_tool_emoji(tool_id: str) -> str:
    cfg = get_tool_config(tool_id)
    return cfg.get("emoji", "🧰")


# ==================== КОНФИГ ====================

def get_repair_config() -> dict:
    return BALANCE.get('repair', {})


def get_base_success_chance() -> int:
    return int(get_repair_config().get('base_success_chance', 45))


def get_engineering_bonus_per_level() -> int:
    return int(get_repair_config().get('engineering_bonus_per_level', 5))


def get_engineering_level(player) -> int:
    skills = getattr(player, 'skills', {}) or {}
    try:
        return int(skills.get('инженерия', 0))
    except (TypeError, ValueError):
        return 0


def get_repair_success_chance(player) -> int:
    """Итоговый шанс успеха ремонта любым расходником."""
    base = get_base_success_chance()
    bonus = get_engineering_level(player) * get_engineering_bonus_per_level()
    return min(base + bonus, 95)


# ==================== СУЩНОСТИ, КОТОРЫЕ МОЖНО РЕМОНТИРОВАТЬ ====================

def get_repairable_items(player) -> list:
    """
    Возвращает список словарей:
        {
          "slot": "gas_mask" | "melee" | "armor" | "helmet",
          "name": str,
          "emoji": str,
          "current": float,
          "max": float,
          "percent": int,
          "can_repair": bool,
        }
    """
    items = []

    # Противогаз
    gas_mask = getattr(player, 'gas_mask', {}) or {}
    if gas_mask and gas_mask.get('прочность', 0) is not None:
        try:
            current = float(gas_mask.get('прочность', 0) or 0)
            max_dur = float(player.get_gas_mask_max_durability()) \
                if hasattr(player, 'get_gas_mask_max_durability') else 25.0
        except (TypeError, ValueError):
            current, max_dur = 0.0, 25.0

        if max_dur > 0:
            percent = int(current / max_dur * 100)
            items.append({
                "slot": "gas_mask",
                "name": "Противогаз",
                "emoji": "🎒",
                "current": current,
                "max": max_dur,
                "percent": percent,
                "can_repair": current < max_dur,
            })

    # Оружие ближнего боя
    melee_id = getattr(player, 'melee_weapon', None)
    if melee_id:
        melee_data = MELEE.get('melee_weapons', {}).get(melee_id, {})
        if isinstance(melee_data, dict):
            indestructible = bool(melee_data.get('indestructible', False))
            try:
                max_durability = int(melee_data.get('max_durability', 999))
                current = int(getattr(player, 'melee_weapon_durability', max_durability))
            except (TypeError, ValueError):
                max_durability, current = 999, 999

            if not indestructible and max_durability < 900:
                percent = int(current / max_durability * 100) if max_durability > 0 else 0
                items.append({
                    "slot": "melee",
                    "name": melee_data.get('name', melee_id),
                    "emoji": melee_data.get('emoji', '🗡️'),
                    "current": current,
                    "max": max_durability,
                    "percent": percent,
                    "can_repair": current < max_durability,
                })

    # Броня и шлем
    armor_durability = getattr(player, 'armor_durability', {}) or {}

    armor_id = getattr(player, 'armor', None)
    if armor_id:
        armor_data = ARMOR.get('armor_sets', {}).get(armor_id, {})
        if isinstance(armor_data, dict):
            try:
                max_dur = float(armor_data.get('max_durability', 100))
                current = float(armor_durability.get('armor', 0) or 0)
            except (TypeError, ValueError):
                max_dur, current = 100.0, 0.0

            if max_dur > 0:
                percent = int(current / max_dur * 100)
                items.append({
                    "slot": "armor",
                    "name": armor_data.get('name', armor_id),
                    "emoji": armor_data.get('emoji', '🧥'),
                    "current": current,
                    "max": max_dur,
                    "percent": percent,
                    "can_repair": current < max_dur,
                })

    helmet_id = getattr(player, 'helmet', None)
    if helmet_id:
        helmet_data = ARMOR.get('armor_sets', {}).get(helmet_id, {})
        if isinstance(helmet_data, dict):
            try:
                max_dur = float(helmet_data.get('max_durability', 100))
                current = float(armor_durability.get('helmet', 0) or 0)
            except (TypeError, ValueError):
                max_dur, current = 100.0, 0.0

            if max_dur > 0:
                percent = int(current / max_dur * 100)
                items.append({
                    "slot": "helmet",
                    "name": helmet_data.get('name', helmet_id),
                    "emoji": helmet_data.get('emoji', '⛑️'),
                    "current": current,
                    "max": max_dur,
                    "percent": percent,
                    "can_repair": current < max_dur,
                })

    return items


# ==================== РАСХОДНИКИ В ИНВЕНТАРЕ ====================

def get_tool_count(player, tool_id: str) -> int:
    try:
        return int(player.inventory.get(tool_id, 0) or 0)
    except (TypeError, ValueError):
        return 0


def get_available_tools(player) -> list:
    """Возвращает список доступных расходников (id, count, конфиг)."""
    result = []
    for tool_id, cfg in REPAIR_TOOLS.items():
        count = get_tool_count(player, tool_id)
        if count > 0:
            result.append({
                "id": tool_id,
                "count": count,
                "name": cfg.get("name", tool_id),
                "emoji": cfg.get("emoji", "🧰"),
                "restore": cfg.get("restore", 0),
            })
    return result


def consume_tool(player, tool_id: str) -> bool:
    count = get_tool_count(player, tool_id)
    if count <= 0:
        return False
    player.inventory[tool_id] = count - 1
    return True


# Совместимость со старым API
def get_tape_count(player) -> int:
    return get_tool_count(player, "изолента")


def consume_tape(player) -> bool:
    return consume_tool(player, "изолента")


# ==================== РЕМОНТ ====================

def repair_with_item(player, slot: str, tool_id: str = "изолента") -> dict:
    """
    Попытка починить конкретным расходником.

    Возвращает:
      {
        "success": bool,        # валидность операции
        "roll_success": bool,   # выпал ли успешный бросок
        "message": str,
        "slot": str,
        "tool_id": str,
        "restored": float,
        "tool_consumed": bool,
        "chance": int,
      }
    """
    result = {
        "success": False,
        "roll_success": False,
        "message": "",
        "slot": slot,
        "tool_id": tool_id,
        "restored": 0.0,
        "tool_consumed": False,
        "chance": 0,
    }

    tool_cfg = get_tool_config(tool_id)
    if not tool_cfg:
        result["message"] = f"❌ Неизвестный расходник: {tool_id}"
        return result

    if get_tool_count(player, tool_id) <= 0:
        result["message"] = f"❌ У вас нет «{get_tool_name(tool_id)}»!"
        return result

    items = get_repairable_items(player)
    target = next((it for it in items if it["slot"] == slot), None)

    if not target:
        result["message"] = "❌ Нечего ремонтировать в этом слоте."
        return result

    if not target["can_repair"]:
        result["message"] = f"✅ **{target['name']}** уже в идеальном состоянии."
        return result

    chance = get_repair_success_chance(player)
    result["chance"] = chance
    result["success"] = True

    consume_tool(player, tool_id)
    result["tool_consumed"] = True

    roll = random.randint(1, 100)

    restore_amount = get_tool_restore_amount(tool_id)

    if roll <= chance:
        restored = min(restore_amount,
                       target["max"] - target["current"])
        _apply_repair(player, slot, restored)

        result["roll_success"] = True
        result["restored"] = restored
        result["message"] = (
            f"{get_tool_emoji(tool_id)} **{target['name']}**: ремонт успешен! "
            f"+{restored:.0f} прочности.\n"
            f"🎲 Бросок: {roll} ≤ {chance} (шанс {chance}%)"
        )
        logger.info(
            f"{getattr(player, 'name', '?')}: успешный ремонт {slot} "
            f"через {tool_id} (+{restored}, шанс {chance}%)"
        )
    else:
        result["message"] = (
            f"❌ **{target['name']}**: ремонт не удался.\n"
            f"🎲 Бросок: {roll} > {chance} (шанс {chance}%)"
        )
        logger.info(
            f"{getattr(player, 'name', '?')}: неудачный ремонт {slot} "
            f"через {tool_id} (шанс {chance}%, бросок {roll})"
        )

    return result


# Совместимость со старым API
def repair_with_tape(player, slot: str) -> dict:
    return repair_with_item(player, slot, tool_id="изолента")


def _apply_repair(player, slot: str, amount: float):
    """Начисляет прочность в указанный слот."""
    if amount <= 0:
        return

    if slot == "gas_mask":
        gas_mask = getattr(player, 'gas_mask', {}) or {}
        try:
            current = float(gas_mask.get('прочность', 0) or 0)
        except (TypeError, ValueError):
            current = 0.0

        max_dur = float(player.get_gas_mask_max_durability()) \
            if hasattr(player, 'get_gas_mask_max_durability') else 25.0

        new_val = min(max_dur, current + amount)
        gas_mask['прочность'] = new_val
        if new_val > 0 and gas_mask.get('состояние') == "разбитый":
            gas_mask['состояние'] = "поношенный"
        player.gas_mask = gas_mask

    elif slot == "melee":
        try:
            current = int(getattr(player, 'melee_weapon_durability', 999))
        except (TypeError, ValueError):
            current = 999

        melee_id = getattr(player, 'melee_weapon', None)
        melee_data = MELEE.get('melee_weapons', {}).get(melee_id, {}) \
            if melee_id else {}
        max_durability = int(melee_data.get('max_durability', 999)) \
            if isinstance(melee_data, dict) else 999

        player.melee_weapon_durability = min(max_durability, current + int(amount))

    elif slot in ("armor", "helmet"):
        if not hasattr(player, 'armor_durability') \
                or not isinstance(player.armor_durability, dict):
            player.armor_durability = {"armor": 0.0, "helmet": 0.0}

        try:
            current = float(player.armor_durability.get(slot, 0) or 0)
        except (TypeError, ValueError):
            current = 0.0

        if slot == "armor":
            item_id = getattr(player, 'armor', None)
        else:
            item_id = getattr(player, 'helmet', None)

        item_data = ARMOR.get('armor_sets', {}).get(item_id, {}) if item_id else {}
        max_dur = float(item_data.get('max_durability', 100)) \
            if isinstance(item_data, dict) else 100.0

        player.armor_durability[slot] = min(max_dur, current + amount)


# ==================== ФОРМАТИРОВАНИЕ ====================

def format_repair_status(player) -> str:
    items = get_repairable_items(player)
    if not items:
        return "_Нечего ремонтировать._"

    lines = []
    for it in items:
        state = "✅" if not it["can_repair"] else "🔧"
        lines.append(
            f"{state} {it['emoji']} **{it['name']}** — "
            f"{it['current']:.0f}/{it['max']:.0f} ({it['percent']}%)"
        )
    return "\n".join(lines)


def format_repair_chance(player) -> str:
    chance = get_repair_success_chance(player)
    level = get_engineering_level(player)
    base = get_base_success_chance()
    bonus = get_engineering_bonus_per_level()

    tool_lines = []
    for tool in get_available_tools(player):
        tool_lines.append(
            f"  • {tool['emoji']} {tool['name']} ×{tool['count']} "
            f"(+{tool['restore']} прочности)"
        )

    tools_str = "\n".join(tool_lines) if tool_lines else "  _нет расходников_"

    return (
        f"🎲 Шанс ремонта: **{chance}%** "
        f"(база {base}% + {level}×{bonus}% от Инженерии)\n"
        f"🧰 Расходники:\n{tools_str}"
    )