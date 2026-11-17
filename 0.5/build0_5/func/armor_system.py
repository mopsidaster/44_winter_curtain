# -*- coding: utf-8 -*-
# func/armor_system.py - Система брони (0.4.7.7)
#
# ИСТОРИЯ:
#   0.4.3.3 — противоудар только против рукопашных
#   0.4.4.5 — броня влияет на ЗОНУ
#   0.4.4.6 — экспансивный ×2/×1.25/×1.5
#   0.4.7.7 — прочность брони списывается ровно на absorbed (поглощённый урон),
#             а не на 10% от final_damage

import random
from config.map_config import ARMOR, BALANCE


def get_armor_item(item_id: str) -> dict:
    if not item_id:
        return {}
    return ARMOR.get('armor_sets', {}).get(item_id, {})


def get_set_data(set_id: str) -> dict:
    if not set_id:
        return {}
    return ARMOR.get('sets', {}).get(set_id, {})


def get_armor_config() -> dict:
    return BALANCE.get('armor', {})


# ==================== ПРОВЕРКИ ЭКИПИРОВКИ ====================

def is_full_set(player) -> bool:
    armor_id = getattr(player, 'armor', None)
    helmet_id = getattr(player, 'helmet', None)

    if not armor_id or not helmet_id:
        return False

    armor_data = get_armor_item(armor_id)
    helmet_data = get_armor_item(helmet_id)

    set_armor = armor_data.get('set_id')
    set_helmet = helmet_data.get('set_id')

    return set_armor is not None and set_armor == set_helmet


def get_active_set(player) -> dict:
    if not is_full_set(player):
        return {}
    armor_id = getattr(player, 'armor', None)
    armor_data = get_armor_item(armor_id)
    return get_set_data(armor_data.get('set_id'))


def has_set_bonus(player, bonus_type: str) -> bool:
    active_set = get_active_set(player)
    if not active_set:
        return False
    for bonus in active_set.get('bonuses', []):
        if bonus.get('type') == bonus_type:
            return True
    return False


def get_set_bonus_value(player, bonus_type: str) -> float:
    active_set = get_active_set(player)
    if not active_set:
        return 0.0
    for bonus in active_set.get('bonuses', []):
        if bonus.get('type') == bonus_type:
            return float(bonus.get('value', 0))
    return 0.0


# ==================== РАСЧЁТ УРОНА ====================

def apply_armor_protection(player, body_part: str, incoming_damage: float,
                           damage_type: str = "generic",
                           ammo_type: str = None,
                           is_melee: bool = False) -> dict:
    """
    Применить защиту брони к входящему урону.

    Returns:
        {final_damage, absorbed, ricochet, zone_covered, message}
    """
    result = {
        "final_damage": incoming_damage,
        "absorbed": 0.0,
        "ricochet": False,
        "zone_covered": False,
        "message": "",
    }

    if incoming_damage <= 0:
        return result

    covering_items = _get_covering_items(player, body_part)

    if not covering_items:
        return result

    result['zone_covered'] = True

    total_impact = 0.0
    total_armor = 0.0
    ricochet_chance = 0.0

    for item_id in covering_items:
        item = get_armor_item(item_id)
        if not item:
            continue

        if not _is_item_working(player, item_id):
            continue

        total_armor += item.get('armor_protection', 0)

        if is_melee:
            total_impact += item.get('impact_protection', 0)

        if item.get('ricochet_zone') == body_part:
            ricochet_chance = max(ricochet_chance, item.get('ricochet_chance', 0))

    is_ap = False
    if ammo_type:
        from .weapon_system import ammo_ignores_armor
        is_ap = ammo_ignores_armor(ammo_type)

    if is_ap:
        total_armor = 0.0

    if (ricochet_chance > 0
            and not is_ap
            and not is_melee
            and random.randint(1, 100) <= ricochet_chance):
        result['ricochet'] = True
        result['final_damage'] = 0.0
        result['absorbed'] = incoming_damage
        result['message'] = "🔰 **РИКОШЕТ!** Урон полностью отражён бронёй."
        return result

    impact_reduction = min(total_impact, 100) / 100.0
    armor_reduction = min(total_armor, 100) / 100.0

    after_impact = incoming_damage * (1.0 - impact_reduction)
    after_armor = after_impact * (1.0 - armor_reduction)

    final = max(after_armor, 0.0)
    absorbed = incoming_damage - final

    result['final_damage'] = final
    result['absorbed'] = absorbed

    if absorbed > 0:
        parts_msg = []
        if total_impact > 0:
            parts_msg.append(f"{total_impact:.0f}% противоудар")
        if total_armor > 0:
            parts_msg.append(f"{total_armor:.0f}% бронезащита")

        if parts_msg:
            result['message'] = (
                f"🛡️ Броня поглотила **{absorbed:.1f}** урона "
                f"({', '.join(parts_msg)})"
            )
        else:
            result['message'] = f"🛡️ Броня поглотила **{absorbed:.1f}** урона"

    return result


def apply_armor_after_hit(player, body_part: str, absorbed: float) -> dict:
    """
    0.4.7.7: списать прочность брони на величину absorbed
    (сколько броня поглотила), а не final_damage.

    Args:
        absorbed: сколько урона броня поглотила (0 = не списываем ничего)
    """
    result = {
        "durability_changes": {},
        "broken_items": [],
    }

    if absorbed <= 0:
        return result

    # Распределяем урон между всеми покрывающими предметами равномерно
    covering_items = _get_covering_items(player, body_part)

    if not covering_items:
        return result

    per_item = absorbed / len(covering_items)

    for item_id in covering_items:
        current = get_item_durability(player, item_id)
        if current <= 0:
            continue

        new_dur = max(0.0, current - per_item)
        set_item_durability(player, item_id, new_dur)
        result['durability_changes'][item_id] = new_dur

        if new_dur <= 0:
            result['broken_items'].append(item_id)

    return result


# ==================== ВНУТРЕННИЕ ====================

def _get_covering_items(player, body_part: str) -> list:
    items = []

    armor_id = getattr(player, 'armor', None)
    if armor_id:
        armor_data = get_armor_item(armor_id)
        if body_part in armor_data.get('zones', []):
            items.append(armor_id)

    helmet_id = getattr(player, 'helmet', None)
    if helmet_id:
        helmet_data = get_armor_item(helmet_id)
        if body_part in helmet_data.get('zones', []):
            items.append(helmet_id)

    return items


def is_zone_covered(player, body_part: str) -> bool:
    return bool(_get_covering_items(player, body_part))


def _is_item_working(player, item_id: str) -> bool:
    cfg = get_armor_config()
    min_dur = cfg.get('min_durability_for_protection', 1.0)
    return get_item_durability(player, item_id) >= min_dur


def get_item_durability(player, item_id: str) -> float:
    slot = _get_slot_of(player, item_id)
    if not slot:
        return 0.0
    dur_dict = getattr(player, 'armor_durability', {})
    return float(dur_dict.get(slot, 0.0))


def set_item_durability(player, item_id: str, value: float):
    slot = _get_slot_of(player, item_id)
    if not slot:
        return
    if not hasattr(player, 'armor_durability'):
        player.armor_durability = {}
    player.armor_durability[slot] = max(0.0, value)


def _get_slot_of(player, item_id: str) -> str:
    if getattr(player, 'armor', None) == item_id:
        return "armor"
    if getattr(player, 'helmet', None) == item_id:
        return "helmet"
    return ""


# ==================== ЭКИПИРОВКА / СНЯТИЕ ====================

def equip_item(player, item_id: str) -> dict:
    item = get_armor_item(item_id)
    if not item:
        return {"success": False, "message": "❌ Такого предмета не существует!"}

    slot = item.get('slot')
    if slot not in ('armor', 'helmet'):
        return {"success": False, "message": "❌ Неизвестный слот брони!"}

    inventory = getattr(player, 'armor_inventory', [])
    if item_id not in inventory:
        return {"success": False, "message": f"❌ У вас нет {item.get('name', item_id)}!"}

    current = getattr(player, slot, None)
    if current == item_id:
        return {"success": False, "message": f"❌ {item.get('name', item_id)} уже надето!"}

    if current:
        inventory.append(current)

    setattr(player, slot, item_id)
    inventory.remove(item_id)

    if not hasattr(player, 'armor_durability'):
        player.armor_durability = {}
    player.armor_durability[slot] = float(item.get('max_durability', 100))

    return {
        "success": True,
        "message": f"✅ Надет **{item.get('emoji', '')} {item.get('name', item_id)}**",
    }


def unequip_item(player, slot: str) -> dict:
    if slot not in ('armor', 'helmet'):
        return {"success": False, "message": f"❌ Неизвестный слот: {slot}"}

    current = getattr(player, slot, None)
    if not current:
        return {"success": False, "message": "❌ На этом слоте ничего нет!"}

    item = get_armor_item(current)

    inventory = getattr(player, 'armor_inventory', [])
    inventory.append(current)
    setattr(player, slot, None)

    if hasattr(player, 'armor_durability'):
        player.armor_durability[slot] = 0.0

    return {
        "success": True,
        "message": f"✅ Снят **{item.get('emoji', '')} {item.get('name', current)}**",
    }


# ==================== ФОРМАТИРОВАНИЕ ====================

def format_armor_status(player) -> str:
    lines = []

    armor_id = getattr(player, 'armor', None)
    helmet_id = getattr(player, 'helmet', None)

    if armor_id:
        data = get_armor_item(armor_id)
        dur = get_item_durability(player, armor_id)
        max_dur = data.get('max_durability', 100)
        zones = ", ".join(data.get('zones', []))
        lines.append(
            f"🧥 **{data.get('name', armor_id)}**\n"
            f"   Прочность: {dur:.0f}/{max_dur}\n"
            f"   Зоны: {zones}\n"
            f"   Противоудар: {data.get('impact_protection', 0)}% (только рукопашная) | "
            f"Броня: {data.get('armor_protection', 0)}%"
        )
    else:
        lines.append("🧥 Броня: ❌ не надета")

    if helmet_id:
        data = get_armor_item(helmet_id)
        dur = get_item_durability(player, helmet_id)
        max_dur = data.get('max_durability', 100)
        zones = ", ".join(data.get('zones', []))
        lines.append(
            f"⛑️ **{data.get('name', helmet_id)}**\n"
            f"   Прочность: {dur:.0f}/{max_dur}\n"
            f"   Зоны: {zones}\n"
            f"   Противоудар: {data.get('impact_protection', 0)}% (только рукопашная) | "
            f"Броня: {data.get('armor_protection', 0)}%"
        )
    else:
        lines.append("⛑️ Шлем: ❌ не надет")

    if is_full_set(player):
        active_set = get_active_set(player)
        lines.append(f"\n✨ **Комплект: {active_set.get('name', '—')}**")
        for bonus in active_set.get('bonuses', []):
            lines.append(f"   • {bonus.get('description', '—')}")

    return "\n".join(lines)


def format_item_info(item_id: str) -> str:
    item = get_armor_item(item_id)
    if not item:
        return "❌ Предмет не найден."

    lines = [
        f"{item.get('emoji', '')} **{item.get('name', item_id)}**",
        f"🔩 Материал: {item.get('material', '—')}",
        f"❤️ Прочность: {item.get('max_durability', 0)}",
        f"🛡️ Противоудар: {item.get('impact_protection', 0)}% _(только рукопашная)_",
        f"🎯 Зоны: {', '.join(item.get('zones', []))}",
    ]

    armor_mat = item.get('armor_material')
    if armor_mat:
        lines.append(f"⚙️ Бронеэлемент: {armor_mat}")
        lines.append(f"🛡️ Бронезащита: {item.get('armor_protection', 0)}% _(все атаки)_")

    ricochet = item.get('ricochet_chance', 0)
    if ricochet > 0:
        zone = item.get('ricochet_zone', '—')
        lines.append(f"🔰 Рикошет: {ricochet}% ({zone})")

    special = item.get('special')
    if special:
        note = item.get('special_note', special)
        lines.append(f"✨ Особое: {note}")

    return "\n".join(lines)