# -*- coding: utf-8 -*-
# func/weapon_system/formatting.py - Форматирование оружия и модулей (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Добавлено логирование через utils.logger.

from config.map_config import WEAPONS, MODULES, AMMO

from .weapons import is_shotgun, is_mg, is_shell_loaded_weapon
from .ammo import get_ammo_type, get_magazine
from .modules import get_module_slot
from .prices import get_magazine_price

from utils.logger import get_logger

logger = get_logger()


def format_weapon_info(weapon_id: str) -> str:
    weapon = WEAPONS.get(weapon_id)
    if not weapon:
        return "❌ Оружие не найдено"

    accuracy = weapon.get('accuracy', 0.5)
    result = f"**{weapon['emoji']} {weapon['name']}**\n"
    result += f"📊 Урон: {weapon['damage']}\n"

    if is_shotgun(weapon_id):
        result += f"🎯 Точность Б: {accuracy * 100:.0f}% (урон ×1)\n"
        result += f"🎯 Точность С: {accuracy * 75:.1f}% (урон ×0.67)\n"
        result += f"🎯 Точность Д: {accuracy * 50:.1f}% (промах, кроме пулевого)\n"
    else:
        result += f"🎯 Точность Б: {accuracy * 100:.0f}%\n"
        result += f"🎯 Точность С: {accuracy * 0.75 * 100:.1f}%\n"
        result += f"🎯 Точность Д: {accuracy * 0.50 * 100:.1f}%\n"

    if is_mg(weapon_id):
        subtype = weapon.get('subtype', 'light')
        subtype_name = "Лёгкий" if subtype == "light" else "Тяжёлый"
        result += f"🔫 Очередь: 3 выстрела ({subtype_name})\n"
    elif weapon.get('type') == 'assault':
        result += "🔫 Очередь: 2 выстрела\n"

    result += f"📦 Калибр: {weapon['caliber']}\n"
    if weapon.get('builtin_module'):
        result += "🔧 Встроенный модуль\n"
    if is_shell_loaded_weapon(weapon_id):
        result += f"🔋 Зарядов в стволе: {weapon.get('shell_capacity', 0)}\n"
    result += f"📝 {weapon['description']}\n"
    return result


def format_magazine_info(magazine_id: str) -> str:
    magazine = get_magazine(magazine_id)
    if not magazine:
        return "❌ Магазин не найден"
    result = f"**{magazine['emoji']} {magazine['name']}**\n"
    result += f"📦 Вместимость: {magazine['capacity']} патронов\n"
    result += f"🔫 Калибр: {magazine['caliber']}\n"
    result += f"🔧 Для: {WEAPONS.get(magazine['weapon'], {}).get('name', magazine['weapon'])}\n"
    result += f"💰 Цена: {get_magazine_price(magazine_id)} никелей\n"
    return result


def format_ammo_info(ammo_type: str) -> str:
    ammo = get_ammo_type(ammo_type)
    if not ammo:
        return "❌ Тип патронов не найден"
    result = f"**{ammo['emoji']} {ammo['name']}**\n"
    result += f"📊 Множитель урона: x{ammo['multiplier']}\n"
    if ammo.get('explosive_multiplier'):
        result += f"🔥 Урон поджога: x{ammo['explosive_multiplier']}\n"
    if ammo.get('incendiary'):
        turns = ammo.get('incendiary_turns', 2)
        dmg = ammo.get('incendiary_damage_per_turn', 1)
        result += f"🔥 Поджигает: {turns} хода, +{dmg} урон/ход\n"
        if ammo.get('incendiary_stacks'):
            result += "   (стакается с каждым попаданием)\n"
    result += f"📝 {ammo['description']}\n"
    return result


def format_module_info(module_id: str) -> str:
    module_data = MODULES.get('modules', {}).get(module_id)
    if not isinstance(module_data, dict):
        return "❌ Модуль не найден"

    slot_key = module_data.get('slot', '')
    slot_name = MODULES.get('slots', {}).get(slot_key, {}).get('name', slot_key)

    result = f"**{module_data['emoji']} {module_data['name']}**\n"
    result += f"🔧 Слот: {slot_name}\n"
    result += f"🎯 Тип: {module_data['type']}\n"

    acc = module_data.get('accuracy', {})
    result += f"📊 Точность Б: +{acc.get('close', 0) * 100:.0f}%\n"
    result += f"📊 Точность С: +{acc.get('medium', 0) * 100:.0f}%\n"
    result += f"📊 Точность Д: +{acc.get('far', 0) * 100:.0f}%\n"

    if module_data.get('special'):
        result += f"✨ Особенность: {module_data['special']}\n"
    result += f"💰 Цена: {module_data['price']} никелей"
    return result