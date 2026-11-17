# -*- coding: utf-8 -*-
# func/cold_system.py - Система Холода и Термостойкости (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.4.1 — термостойкость только от брони
#   0.4.5   — process_cold_on_transition(custom_amount=...)
#   0.4.7.2 — без изменений логики; добавлен хелпер get_campfire_stamina_bonus

import random
from config.map_config import BALANCE, ARMOR

from utils.logger import get_logger

logger = get_logger()


def get_cold_config() -> dict:
    return BALANCE.get('cold', {})


def get_max_cold() -> int:
    return get_cold_config().get('max', 100)


def get_frostbite_threshold() -> int:
    return get_cold_config().get('frostbite_threshold', 75)


def get_frostbite_chance_per_point() -> float:
    return get_cold_config().get('frostbite_chance_per_point', 1.0)


def get_frostbite_damage_per_turn() -> float:
    return get_cold_config().get('frostbite_damage_per_turn', 10.0)


def get_cold_per_transition_base() -> int:
    return get_cold_config().get('cold_per_transition_no_protection', 25)


def get_warm_up_per_campfire() -> int:
    return get_cold_config().get('warm_up_per_campfire', 5)


def get_campfire_stamina_bonus() -> float:
    """0.4.7.2: бонус выносливости при согреве у костра."""
    cfg = BALANCE.get('campfire', {})
    try:
        return float(cfg.get('warm_up_stamina_bonus', 2.0))
    except (TypeError, ValueError):
        return 2.0


def ensure_cold_fields(player):
    if not hasattr(player, 'cold'):
        player.cold = 0.0


# ==================== ТЕРМОСТОЙКОСТЬ ====================

def get_thermal_resistance(player) -> int:
    """Суммарная термостойкость — ТОЛЬКО от брони (не от шлема)."""
    total = 0

    armor_id = getattr(player, 'armor', None)
    if armor_id:
        armor_data = ARMOR.get('armor_sets', {}).get(armor_id, {})
        if isinstance(armor_data, dict):
            total += armor_data.get('thermal_resistance', 0)

    return total


# ==================== НАКОПЛЕНИЕ ====================

def add_cold(player, amount: float) -> dict:
    ensure_cold_fields(player)

    max_cold = get_max_cold()
    resistance = get_thermal_resistance(player)

    effective_amount = max(0, amount - resistance)

    before = player.cold
    player.cold = min(before + effective_amount, max_cold)
    delta = player.cold - before

    result = {
        "before": before,
        "after": player.cold,
        "delta": delta,
        "thermal_resistance": resistance,
        "frostbite_triggered": False,
        "message": "",
    }

    if delta <= 0:
        if resistance >= amount:
            result['message'] = f"❄️ Холод не берёт: термостойкость {resistance} блокирует замерзание."
        else:
            result['message'] = "❄️ Холод не накапливается."
        return result

    result['message'] = (
        f"❄️ Замерзание +{delta:.0f} ({player.cold:.0f}/{max_cold})"
    )
    if resistance > 0:
        result['message'] += f" [термостойкость -{resistance}]"

    if player.cold >= get_frostbite_threshold():
        frostbite_result = _check_frostbite(player)
        if frostbite_result['triggered']:
            result['frostbite_triggered'] = True
            result['message'] += "\n" + frostbite_result['message']

    return result


def _check_frostbite(player) -> dict:
    ensure_cold_fields(player)

    if 'обморожение' in getattr(player, 'diseases', []):
        return {"triggered": False, "message": ""}

    threshold = get_frostbite_threshold()
    if player.cold < threshold:
        return {"triggered": False, "message": ""}

    chance = player.cold * get_frostbite_chance_per_point()
    chance = min(chance, 100)

    from .disease_system import get_immunity_reduction
    immunity = get_immunity_reduction(player)
    final_chance = chance * (1 - immunity)

    if random.uniform(0, 100) <= final_chance:
        if not hasattr(player, 'diseases'):
            player.diseases = []
        player.diseases.append('обморожение')
        return {
            "triggered": True,
            "message": "🥶 **Вы получили обморожение!** Согрейтесь у костра!",
        }

    return {"triggered": False, "message": ""}


def reduce_cold(player, amount: float) -> dict:
    ensure_cold_fields(player)

    before = player.cold
    player.cold = max(0.0, before - amount)
    reduced = before - player.cold

    frostbite_cured = False
    if player.cold <= 0 and 'обморожение' in getattr(player, 'diseases', []):
        player.diseases.remove('обморожение')
        frostbite_cured = True

    message = f"🔥 Согрев: -{reduced:.0f} холода ({player.cold:.0f}/100)"
    if frostbite_cured:
        message += "\n✅ **Обморожение прошло!**"

    return {
        "before": before,
        "after": player.cold,
        "reduced": reduced,
        "frostbite_cured": frostbite_cured,
        "message": message,
    }


# ==================== ОБРАБОТКА ПЕРЕХОДА ====================

def process_cold_on_transition(player, to_station_in_frost_zone: bool,
                               custom_amount: int = None) -> dict:
    """
    0.4.5: если custom_amount задан — используем его вместо базового.
    """
    ensure_cold_fields(player)

    if not to_station_in_frost_zone and custom_amount is None:
        return {"cold_message": "", "frostbite_triggered": False}

    base = custom_amount if custom_amount is not None else get_cold_per_transition_base()
    result = add_cold(player, base)

    return {
        "cold_message": result.get('message', ''),
        "frostbite_triggered": result.get('frostbite_triggered', False),
    }


def process_cold_on_event_start(player, in_frost_zone: bool) -> dict:
    ensure_cold_fields(player)

    if not in_frost_zone:
        return {"cold_message": "", "frostbite_triggered": False}

    base = get_cold_per_transition_base()
    result = add_cold(player, base)

    return {
        "cold_message": result.get('message', ''),
        "frostbite_triggered": result.get('frostbite_triggered', False),
    }


# ==================== УРОН ОТ ОБМОРОЖЕНИЯ ====================

def apply_frostbite_damage(player) -> dict:
    ensure_cold_fields(player)

    if 'обморожение' not in getattr(player, 'diseases', []):
        return {"total_damage": 0.0, "killed": False, "message": ""}

    dmg = get_frostbite_damage_per_turn()
    zones = ['голова', 'торс', 'руки', 'ноги']
    per_zone = dmg / len(zones)

    for zone in zones:
        if zone in player.body_parts and player.body_parts[zone].get('hp', 0) > 0:
            player.take_body_part_damage(zone, per_zone)

    killed = not player.is_alive

    return {
        "total_damage": dmg,
        "killed": killed,
        "message": f"🥶 **Обморожение**: -{dmg:.0f} HP по всем частям тела",
    }


# ==================== СБРОС ====================

def reset_cold(player):
    ensure_cold_fields(player)
    player.cold = 0.0
    if 'обморожение' in getattr(player, 'diseases', []):
        player.diseases.remove('обморожение')


# ==================== ФОРМАТИРОВАНИЕ ====================

def format_status(player) -> str:
    ensure_cold_fields(player)

    max_cold = get_max_cold()
    threshold = get_frostbite_threshold()
    resistance = get_thermal_resistance(player)

    line = f"❄️ Замерзание: **{player.cold:.0f}/{max_cold}** (порог: {threshold})"
    if resistance > 0:
        line += f"\n🧥 Термостойкость: **{resistance}** (от брони)"

    if 'обморожение' in getattr(player, 'diseases', []):
        line += "\n🥶 **Обморожение активно!** Согрейтесь у костра."

    return line


def format_detailed_status(player) -> str:
    ensure_cold_fields(player)

    max_cold = get_max_cold()
    threshold = get_frostbite_threshold()
    resistance = get_thermal_resistance(player)

    cold_pct = (player.cold / max_cold) * 100 if max_cold > 0 else 0
    bar_filled = int(cold_pct / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    lines = [
        f"❄️ **Замерзание** [{bar}] {player.cold:.0f}/{max_cold}",
        f"🧥 **Термостойкость:** {resistance} (только от брони)",
    ]

    if 'простуда' in getattr(player, 'diseases', []):
        cold_sickness_cfg = BALANCE.get('cold_sickness', {})
        danger_need = cold_sickness_cfg.get('auto_cure_danger_transitions', 15)
        safe_need = cold_sickness_cfg.get('auto_cure_safe_transitions', 30)
        transitions = getattr(player, 'cold_sickness_transitions', 0)
        lines.append(
            f"\n🤧 **Простуда активна!** "
            f"Пройдёт через {danger_need - transitions} опасных / "
            f"{safe_need - transitions} безопасных переходов "
            f"(или выпейте Аспирин)."
        )
    elif player.cold >= BALANCE.get('cold_sickness', {}).get('cold_threshold', 25):
        lines.append(f"\n⚠️ Вы близки к простуде! (порог 25 холода)")

    if 'обморожение' in getattr(player, 'diseases', []):
        lines.append(f"\n🥶 **Обморожение активно!** -{get_frostbite_damage_per_turn():.0f} HP/переход")
        lines.append(f"💡 Согрейтесь у костра (-{get_warm_up_per_campfire()} холода за использование)")

    return "\n".join(lines)


def can_warm_up_at_campfire(player) -> tuple:
    ensure_cold_fields(player)

    if player.cold <= 0:
        return False, "🔥 Вам не нужно согреваться — вы не замёрзли."

    return True, ""