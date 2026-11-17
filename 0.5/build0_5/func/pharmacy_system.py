# -*- coding: utf-8 -*-
# func/pharmacy_system.py - Логика Аптеки (Билд 0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.3.2 — use_medkit работает с любой аптечкой, вывод радиации
#   0.4.4.6 — боевые аптечки
#   0.4.5   — use_medkit снимает кровотечение; cure_cold (аспирин);
#             cure_blood_infection (услуга врача)
#   0.4.8.6 — без изменений
#   0.4.8.7 — Активированный уголь (-20 химии).

from config.map_config import PHARMACY, BALANCE

from utils.logger import get_logger

logger = get_logger()


# Соответствие ID товара → ключ в player.inventory
INVENTORY_KEY_MAP = {
    "аптечка_аи2": "аптечка_аи2",
    "аптечка_аи4": "аптечка_аи4",
    "кустарная_аптечка": "кустарная_аптечка",
    "тактическая_аптечка": "тактическая_аптечка",
    "мед_подсумок": "мед_подсумок",
    "антирад": "антирад",
    "активированный_уголь": "активированный_уголь",  # 0.4.8.7
    "таблетки_от_простуды": "аспирин",
}


# ==================== ДОСТУП К ДАННЫМ ====================

def get_shop_item(item_id: str) -> dict:
    return PHARMACY.get('shop_items', {}).get(item_id, {})


def get_doctor_service(service_id: str) -> dict:
    return PHARMACY.get('doctor_services', {}).get(service_id, {})


def get_all_shop_items() -> dict:
    return PHARMACY.get('shop_items', {})


def get_all_doctor_services() -> dict:
    return PHARMACY.get('doctor_services', {})


def get_inventory_key(item_id: str) -> str:
    return INVENTORY_KEY_MAP.get(item_id, item_id)


# ==================== ПОКУПКА ====================

def buy_item(player, item_id: str) -> dict:
    item = get_shop_item(item_id)
    if not item:
        return {"success": False, "message": "❌ Такого товара нет в аптеке!", "price": 0}

    price = item.get('price', 0)
    nickels = player.inventory.get('никели', 0)

    if nickels < price:
        return {
            "success": False,
            "message": f"❌ Нужно **{price}** никелей, у вас **{nickels}**!",
            "price": price,
        }

    player.inventory['никели'] = nickels - price

    effect = item.get('effect')
    inv_key = get_inventory_key(item_id)

    # 0.4.8.7: добавили reduce_chemical
    if effect in ('heal', 'reduce_radiation', 'reduce_chemical', 'cure_cold'):
        player.inventory[inv_key] = player.inventory.get(inv_key, 0) + 1
    else:
        if 'pharmacy_items' not in player.inventory:
            player.inventory['pharmacy_items'] = []
        player.inventory['pharmacy_items'].append(item_id)

    return {
        "success": True,
        "message": (
            f"✅ Куплено: {item.get('emoji', '')} **{item.get('name', item_id)}** "
            f"за {price} никелей"
        ),
        "price": price,
    }


# ==================== ИСПОЛЬЗОВАНИЕ ====================

def get_available_medkits(player) -> list:
    """Список доступных у игрока аптечек (все с effect='heal')."""
    result = []
    for item_id, inv_key in INVENTORY_KEY_MAP.items():
        item = get_shop_item(item_id)
        if not item:
            continue
        if item.get('effect') != 'heal':
            continue
        count = player.inventory.get(inv_key, 0)
        if count > 0:
            result.append({
                "item_id": item_id,
                "count": count,
                "data": item,
            })
    return result


def get_available_medkits_for_combat(player) -> list:
    cfg = BALANCE.get('healing', {})
    if not cfg.get('in_combat_allowed', True):
        return []
    return get_available_medkits(player)


def use_medkit(player, item_id: str) -> dict:
    """
    Использовать аптечку / подсумок.
    0.4.5: снимает ВСЁ кровотечение у игрока.
    """
    item_data = get_shop_item(item_id)
    if not item_data:
        return {"success": False, "message": f"❌ Предмет `{item_id}` не найден!",
                "healed": 0.0, "rad_reduced": 0.0}

    if item_data.get('effect') != 'heal':
        return {"success": False, "message": "❌ Этот предмет нельзя использовать как аптечку.",
                "healed": 0.0, "rad_reduced": 0.0}

    inv_key = get_inventory_key(item_id)
    count = player.inventory.get(inv_key, 0)
    if count <= 0:
        return {"success": False, "message": f"❌ У вас нет {item_data.get('name', item_id)}!",
                "healed": 0.0, "rad_reduced": 0.0}

    total_hp = player.get_total_health()
    max_hp = player.get_max_total_health()

    from .disease_system import ensure_disease_fields
    ensure_disease_fields(player)

    radiation = getattr(player, 'radiation', 0.0)
    rad_reduction = item_data.get('radiation_reduction', 0)

    has_bleeding = player.has_bleeding() if hasattr(player, 'has_bleeding') else False

    hp_full = total_hp >= max_hp
    rad_zero = radiation <= 0

    if hp_full and (rad_zero or rad_reduction <= 0) and not has_bleeding:
        return {
            "success": False,
            "message": "❤️ Полное здоровье, нет радиации и нет кровотечения — лечение не нужно.",
            "healed": 0.0,
            "rad_reduced": 0.0,
        }

    player.inventory[inv_key] = count - 1

    messages = []
    healed_amount = 0.0
    rad_reduced_amount = 0.0

    heal_amount = item_data.get('heal', 0)
    if heal_amount > 0:
        before_hp = total_hp
        player.heal_all_body_parts(heal_amount)
        after_hp = player.get_total_health()
        healed_amount = after_hp - before_hp
        messages.append(f"❤️ +{heal_amount:.1f} HP по всем частям")

    if rad_reduction > 0 and radiation > 0:
        from .disease_system import reduce_radiation
        rad_result = reduce_radiation(player, rad_reduction)
        rad_reduced_amount = rad_result.get('reduced', 0)
        if rad_reduced_amount > 0:
            messages.append(f"☢️ -{rad_reduced_amount:.0f} радиации")

    bleeding_removed = 0
    if has_bleeding:
        bleeding_removed = player.clear_bleeding()
        if bleeding_removed > 0:
            messages.append(f"🩸 Остановлено кровотечений: {bleeding_removed}")

    return {
        "success": True,
        "message": (
                f"💊 Использовано: **{item_data.get('emoji', '')} {item_data.get('name', item_id)}**\n"
                + "\n".join(messages)
        ),
        "healed": healed_amount,
        "rad_reduced": rad_reduced_amount,
        "bleeding_removed": bleeding_removed,
    }


def use_medkit_in_combat(player, item_id: str) -> dict:
    cfg = BALANCE.get('healing', {})
    if not cfg.get('in_combat_allowed', True):
        return {
            "success": False,
            "message": "❌ В бою нельзя использовать аптечку.",
            "healed": 0.0,
            "rad_reduced": 0.0,
        }

    return use_medkit(player, item_id)


def use_antirad(player) -> dict:
    """Использовать антирад."""
    count = player.inventory.get('антирад', 0)
    if count <= 0:
        return {"success": False, "message": "❌ У вас нет Антирада!"}

    from .disease_system import ensure_disease_fields, reduce_radiation
    ensure_disease_fields(player)

    if player.radiation <= 0:
        return {"success": False, "message": "☢️ У вас нет радиации!"}

    item = get_shop_item('антирад')
    reduction = item.get('radiation_reduction', 50)

    player.inventory['антирад'] = count - 1
    result = reduce_radiation(player, reduction)

    return {
        "success": True,
        "message": (
            f"💉 Использован **Антирад**\n"
            f"{result.get('message', '')}"
        ),
    }


def use_activated_charcoal(player) -> dict:
    """0.4.8.7: Использовать Активированный уголь (-20 химии)."""
    count = player.inventory.get('активированный_уголь', 0)
    if count <= 0:
        return {"success": False, "message": "❌ У вас нет Активированного угля!"}

    from .disease_system import ensure_disease_fields
    ensure_disease_fields(player)

    if player.chemical <= 0:
        return {"success": False, "message": "☣️ У вас нет химического заражения!"}

    item = get_shop_item('активированный_уголь')
    reduction = item.get('chemical_reduction', 20)

    player.inventory['активированный_уголь'] = count - 1

    before = player.chemical
    player.chemical = max(0.0, before - reduction)
    actual = before - player.chemical

    return {
        "success": True,
        "message": (
            f"⚫ Использован **Активированный уголь**\n"
            f"☣️ Химия: -{actual:.0f} ({player.chemical:.0f}/100)"
        ),
    }


# ==================== ЛЕЧЕНИЕ ПРОСТУДЫ ====================

def use_aspirin(player) -> dict:
    """Использовать Аспирин для лечения простуды."""
    count = player.inventory.get('аспирин', 0)
    if count <= 0:
        return {"success": False, "message": "❌ У вас нет Аспирина!"}

    from .disease_system import ensure_disease_fields
    ensure_disease_fields(player)

    if 'простуда' not in player.diseases:
        return {"success": False, "message": "❌ У вас нет простуды!"}

    player.inventory['аспирин'] = count - 1
    player.diseases.remove('простуда')
    player.cold_sickness_transitions = 0

    logger.info(f"{player.name}: простуда вылечена Аспирином")

    return {
        "success": True,
        "message": "💊 **Аспирин** принят! Простуда прошла.",
    }


# ==================== УСЛУГИ ВРАЧА ====================

def cure_chemical_poisoning(player) -> dict:
    service = get_doctor_service('лечение_хим_отравления')
    if not service:
        return {"success": False, "message": "❌ Услуга недоступна!", "price": 0}

    price = service.get('price', 300)
    disease_id = service.get('cures_disease', 'хим_отравление')

    from .disease_system import ensure_disease_fields, cure_disease
    ensure_disease_fields(player)

    if disease_id not in player.diseases:
        return {
            "success": False,
            "message": f"❌ У вас нет {get_disease_name(disease_id)}!",
            "price": 0,
        }

    nickels = player.inventory.get('никели', 0)
    if nickels < price:
        return {
            "success": False,
            "message": f"❌ Нужно **{price}** никелей, у вас **{nickels}**!",
            "price": price,
        }

    player.inventory['никели'] = nickels - price
    result = cure_disease(player, disease_id)

    return {
        "success": result.get('success', False),
        "message": result.get('message', ''),
        "price": price,
    }


def cure_blood_infection(player) -> dict:
    """
    0.4.5: Лечение заражения крови у Врача.
    После оплаты — снимаются острые дебаффы, но 15 переходов
    действуют смягчённые дебаффы, потом болезнь уходит.
    """
    service = get_doctor_service('лечение_заражения_крови')
    if not service:
        return {"success": False, "message": "❌ Услуга недоступна!", "price": 0}

    price = service.get('price', 500)
    disease_id = 'заражение_крови'

    from .disease_system import ensure_disease_fields
    ensure_disease_fields(player)

    if disease_id not in player.diseases:
        return {
            "success": False,
            "message": "❌ У вас нет заражения крови!",
            "price": 0,
        }

    nickels = player.inventory.get('никели', 0)
    if nickels < price:
        return {
            "success": False,
            "message": f"❌ Нужно **{price}** никелей, у вас **{nickels}**!",
            "price": price,
        }

    player.inventory['никели'] = nickels - price

    soft_transitions = service.get('soft_penalty_transitions', 15)
    player.blood_infection_soft_transitions = soft_transitions

    logger.info(
        f"{player.name}: заражение крови обработано Врачом, "
        f"смягчённые дебаффы {soft_transitions} переходов"
    )

    return {
        "success": True,
        "message": (
            f"👨‍⚕️ **Врач обработал рану!**\n"
            f"Острые дебаффы сняты. На {soft_transitions} переходов — "
            f"сниженные дебаффы.\n"
            f"💡 Полностью заживёт через {soft_transitions} переходов."
        ),
        "price": price,
    }


def get_disease_name(disease_id: str) -> str:
    from .disease_system import get_disease_data
    return get_disease_data(disease_id).get('name', disease_id)


# ==================== UI ====================

def format_shop_list() -> str:
    items = get_all_shop_items()
    if not items:
        return "❌ Аптека пуста."

    lines = []
    for item_id, item in items.items():
        price = item.get('price', 0)
        lines.append(
            f"{item.get('emoji', '')} **{item.get('name', item_id)}** — "
            f"**{price}** никелей\n"
            f"   _{item.get('description', '')}_"
        )
    return "\n".join(lines)


def format_doctor_services(player=None) -> str:
    services = get_all_doctor_services()
    if not services:
        return "❌ Врач недоступен."

    lines = []
    for service_id, service in services.items():
        price = service.get('price', 0)
        lines.append(
            f"{service.get('emoji', '👨‍⚕️')} **{service.get('name', service_id)}** — "
            f"**{price}** никелей\n"
            f"   _{service.get('description', '')}_"
        )
    return "\n".join(lines)