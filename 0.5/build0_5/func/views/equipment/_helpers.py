# -*- coding: utf-8 -*-
# func/views/equipment/_helpers.py - Хелперы и общий embed (0.4.4.7.1)
#
# Рефакторинг без изменения логики.

from ..helpers import WEAPONS, get_magazine
from ...weapon_system import is_shell_loaded_weapon, is_mg, get_module_slots
from config.map_config import MODULES
from utils.logger import get_logger

logger = get_logger()


# ==================== ЗАЩИТНЫЕ ХЕЛПЕРЫ ====================

def _safe_get_module(module_id) -> dict:
    """
    Вернуть dict модуля по ID или пустой dict.
    Защита от не-dict (например, строк-комментариев).
    """
    if not module_id or not isinstance(module_id, str):
        return {}
    module_data = MODULES.get('modules', {}).get(module_id)
    if not isinstance(module_data, dict):
        return {}
    return module_data


def _safe_get_slots(module_id) -> list:
    """Безопасно получить список слотов модуля."""
    if not module_id or not isinstance(module_id, str):
        return []
    try:
        slots = get_module_slots(module_id)
    except Exception as e:
        logger.error(f"Ошибка get_module_slots({module_id}): {e}")
        return []
    if not isinstance(slots, list):
        return []
    return slots


def _safe_iter_modules(module_ids) -> list:
    """
    Отфильтровать список ID модулей, оставив только те,
    у которых в MODULES['modules'] лежит dict.
    """
    if not isinstance(module_ids, (list, tuple)):
        return []
    result = []
    for mid in module_ids:
        if not isinstance(mid, str):
            continue
        data = MODULES.get('modules', {}).get(mid)
        if isinstance(data, dict):
            result.append(mid)
    return result


# ==================== ОБЩИЙ BUILDER EMBED ====================

def _build_equipment_embed(player) -> "discord.Embed":
    import discord

    embed = discord.Embed(
        title="🔧 Снаряжение",
        description="Управление оружием, магазинами и модулями",
        color=discord.Color.blue()
    )

    current_weapon = WEAPONS.get(player.weapon, {}) or {}
    weapon_note = ""
    if is_mg(player.weapon):
        subtype = current_weapon.get('subtype', 'light')
        subtype_name = "Light" if subtype == "light" else "Heavy"
        weapon_note = f" (пулемёт {subtype_name})"

    embed.add_field(
        name="🔫 Текущее оружие",
        value=f"{current_weapon.get('emoji', '')} **{current_weapon.get('name', 'Нет')}**{weapon_note}",
        inline=False
    )

    weapon_id = player.weapon
    if is_shell_loaded_weapon(weapon_id):
        capacity = current_weapon.get('shell_capacity', 0)
        current = player.get_shell_ammo_count()
        shell = player.get_shell_ammo()
        shell_str = ", ".join([f"{k} ×{v}" for k, v in shell.items()]) or "пусто"

        embed.add_field(
            name="🔋 Ствол",
            value=f"Заряжено: **{current}/{capacity}**\n({shell_str})\n"
                  f"Калибр: **{current_weapon.get('caliber', '?')}**",
            inline=False
        )
    else:
        equipped = player.get_equipped_magazine_obj()
        if equipped:
            mag_data = get_magazine(equipped["type_id"])
            current_ammo = sum(equipped["ammo"].values())
            capacity = mag_data.get("capacity", 0) if mag_data else 0
            mag_name = mag_data.get('name', '?') if mag_data else '?'
            mag_caliber = mag_data.get('caliber', '?') if mag_data else '?'
            embed.add_field(
                name="📀 Установленный магазин",
                value=f"**{mag_name}** (UID: `{equipped['uid']}`)\n"
                      f"Калибр: **{mag_caliber}**\n"
                      f"Патронов: {current_ammo}/{capacity}",
                inline=False
            )
        else:
            embed.add_field(name="📀 Установленный магазин", value="❌ Нет магазина", inline=False)

    # Модули — без дубликатов, с защитой
    modules_text = ""
    shown = set()
    equipped_modules = player.equipped_modules or {}

    for slot_id, slot_data in MODULES.get('slots', {}).items():
        module_id = equipped_modules.get(slot_id)
        if module_id and module_id not in shown:
            module_data = _safe_get_module(module_id)
            if not module_data:
                shown.add(module_id)
                modules_text += f"{slot_data.get('emoji', '🔧')} {slot_data.get('name', slot_id)}: ⚠️ некорректный модуль\n"
                continue
            all_slots = _safe_get_slots(module_id)
            slot_names = ", ".join(
                MODULES['slots'].get(s, {}).get('name', s) for s in all_slots
            ) if all_slots else slot_data.get('name', slot_id)
            modules_text += (f"{slot_data.get('emoji', '🔧')} "
                             f"{slot_names}: "
                             f"{module_data.get('emoji', '')} "
                             f"{module_data.get('name', module_id)}\n")
            shown.add(module_id)
        elif not module_id:
            modules_text += f"{slot_data.get('emoji', '🔧')} {slot_data.get('name', slot_id)}: ❌\n"

    if not modules_text:
        modules_text = "_Пусто_"

    embed.add_field(name="🔧 Модули", value=modules_text, inline=False)

    return embed