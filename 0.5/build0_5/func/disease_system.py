# -*- coding: utf-8 -*-
# func/disease_system.py - Радиация, химия, болезни (Билд 0.4.5)
#
# ИСТОРИЯ:
#   0.4.3.1 — add_radiation: 1 урон = 1 заражение
#   0.4.4   — обморожение
#   0.4.5   — простуда (триггер от холода, авто-излечение, штраф стамины);
#             заражение крови (триггер после боя, лечение у Врача,
#             смягчённые дебаффы на 15 переходов);
#             get_disease_stamina_penalty, get_immunity_reduction,
#             update_disease_transitions.

import random

from config.map_config import DISEASES, BALANCE, PHARMACY

from utils.logger import get_logger

logger = get_logger()


def get_radiation_config() -> dict:
    return DISEASES.get('radiation', {})


def get_chemical_config() -> dict:
    return DISEASES.get('chemical', {})


def get_disease_data(disease_id: str) -> dict:
    return DISEASES.get('diseases', {}).get(disease_id, {})


def get_immunity_reduction(player) -> float:
    health_skill = getattr(player, 'skills', {}).get('здоровье', 0)
    per_level = DISEASES.get('immunity', {}).get('health_skill_reduction_per_level', 5)
    return min((health_skill * per_level) / 100.0, 0.95)


def ensure_disease_fields(player):
    if not hasattr(player, 'radiation'):
        player.radiation = 0.0
    if not hasattr(player, 'chemical'):
        player.chemical = 0.0
    if not hasattr(player, 'diseases'):
        player.diseases = []
    if not hasattr(player, 'cold'):
        player.cold = 0.0
    # 0.4.5
    if not hasattr(player, 'cold_transition_counter'):
        player.cold_transition_counter = 0
    if not hasattr(player, 'cold_sickness_transitions'):
        player.cold_sickness_transitions = 0
    if not hasattr(player, 'blood_infection_soft_transitions'):
        player.blood_infection_soft_transitions = 0


# ==================== НАКОПЛЕНИЕ ====================

def add_radiation(player, amount: float) -> dict:
    """1 единица урона = 1 единица заражения."""
    ensure_disease_fields(player)

    cfg = get_radiation_config()
    max_rad = cfg.get('max', 100)
    threshold = cfg.get('threshold', 50)
    disease_id = cfg.get('disease_id', 'лучевая_болезнь')

    before = player.radiation
    player.radiation = min(before + amount, max_rad)
    delta = player.radiation - before

    result = {
        "before": before,
        "after": player.radiation,
        "delta": delta,
        "disease_triggered": False,
        "message": f"☢️ Радиация +{delta:.1f} ({player.radiation:.0f}/{max_rad})",
    }

    if player.radiation >= threshold and disease_id not in player.diseases:
        chance = player.radiation
        immunity = get_immunity_reduction(player)
        final_chance = chance * (1 - immunity)

        if random.uniform(0, 100) <= final_chance:
            player.diseases.append(disease_id)
            disease_data = get_disease_data(disease_id)
            result['disease_triggered'] = True
            result['message'] += (
                f"\n💀 **Вы заболели: {disease_data.get('name', disease_id)}!**\n"
                f"{disease_data.get('description', '')}"
            )

    return result


def add_chemical(player, amount: float) -> dict:
    ensure_disease_fields(player)

    cfg = get_chemical_config()
    max_chem = cfg.get('max', 100)
    threshold = cfg.get('threshold', 25)
    disease_id = cfg.get('disease_id', 'хим_отравление')

    before = player.chemical
    player.chemical = min(before + amount, max_chem)
    delta = player.chemical - before

    result = {
        "before": before,
        "after": player.chemical,
        "delta": delta,
        "disease_triggered": False,
        "message": f"☣️ Химия +{delta:.1f} ({player.chemical:.0f}/{max_chem})",
    }

    if player.chemical >= threshold and disease_id not in player.diseases:
        chance = 100
        immunity = get_immunity_reduction(player)
        final_chance = chance * (1 - immunity)

        if random.uniform(0, 100) <= final_chance:
            player.diseases.append(disease_id)
            disease_data = get_disease_data(disease_id)
            result['disease_triggered'] = True
            result['message'] += (
                f"\n💀 **Вы заболели: {disease_data.get('name', disease_id)}!**\n"
                f"{disease_data.get('description', '')}"
            )

    return result


# ==================== УМЕНЬШЕНИЕ ====================

def reduce_radiation(player, amount: float) -> dict:
    ensure_disease_fields(player)

    before = player.radiation
    player.radiation = max(0.0, before - amount)

    return {
        "before": before,
        "after": player.radiation,
        "reduced": before - player.radiation,
        "message": f"💉 Радиация снижена на {before - player.radiation:.1f} ({player.radiation:.0f}/100)",
    }


def decay_on_transition(player, from_station_safe: bool, to_station_safe: bool) -> dict:
    ensure_disease_fields(player)

    rad_decay = 0.0
    chem_decay = 0.0

    if to_station_safe:
        rad_cfg = get_radiation_config()
        chem_cfg = get_chemical_config()
        rad_decay = rad_cfg.get('decay_on_safe', 5)
        chem_decay = chem_cfg.get('decay_on_safe', 2)

    if rad_decay > 0:
        before_r = player.radiation
        player.radiation = max(0.0, before_r - rad_decay)
        rad_decay = before_r - player.radiation

    if chem_decay > 0:
        before_c = player.chemical
        player.chemical = max(0.0, before_c - chem_decay)
        chem_decay = before_c - player.chemical

    msg_parts = []
    if rad_decay > 0:
        msg_parts.append(f"☢️ -{rad_decay:.0f} радиации")
    if chem_decay > 0:
        msg_parts.append(f"☣️ -{chem_decay:.0f} химии")

    return {
        "radiation_decay": rad_decay,
        "chemical_decay": chem_decay,
        "message": " | ".join(msg_parts) if msg_parts else "",
    }


# ==================== 0.4.5: ШТРАФ СТАМИНЫ ====================

def get_disease_stamina_penalty(player) -> float:
    """
    Дополнительная стоимость выносливости за переход от активных болезней.
    Складывается из простуды (+2.5) и заражения крови (+3 или +2, если смягчённая).
    """
    ensure_disease_fields(player)
    penalty = 0.0

    if 'простуда' in player.diseases:
        cfg = BALANCE.get('cold_sickness', {})
        penalty += float(cfg.get('stamina_penalty_per_move', 2.5))

    if 'заражение_крови' in player.diseases:
        cfg = BALANCE.get('blood_infection', {})
        soft_left = getattr(player, 'blood_infection_soft_transitions', 0)
        if soft_left > 0:
            penalty += float(cfg.get('soft_stamina_penalty', 2))
        else:
            penalty += float(cfg.get('stamina_penalty_per_move', 3))

    return penalty


# ==================== 0.4.5: ПЕРЕХОДЫ И АВТО-ИЗЛЕЧЕНИЕ ====================

def update_disease_transitions(player, from_station_safe: bool, to_station_safe: bool) -> dict:
    """
    Обновить счётчики болезней после перехода:
      • простуда: копит переходы (опасные / безопасные отдельно через эвристику);
      • заражение крови: уменьшает счётчик мягких дебаффов.

    Логика «опасный/безопасный» — по станции НАЗНАЧЕНИЯ (куда пришли).
    Если destination безопасная — считаем «безопасный» переход, иначе «опасный».

    Returns:
        {"cold_cured": bool, "blood_soft_removed": bool, "messages": [...]}
    """
    ensure_disease_fields(player)
    messages = []
    result = {"cold_cured": False, "blood_soft_removed": False, "messages": messages}

    # === Простуда ===
    if 'простуда' in player.diseases:
        cfg = BALANCE.get('cold_sickness', {})
        danger_need = cfg.get('auto_cure_danger_transitions', 15)
        safe_need = cfg.get('auto_cure_safe_transitions', 30)

        # Определяем тип перехода по станции назначения
        is_safe_dest = to_station_safe
        if is_safe_dest:
            player.cold_sickness_transitions += 1
            need = safe_need
        else:
            player.cold_sickness_transitions += 1
            need = danger_need

        if player.cold_sickness_transitions >= need:
            player.diseases.remove('простуда')
            player.cold_sickness_transitions = 0
            result['cold_cured'] = True
            messages.append("✅ **Простуда прошла сама!**")
            logger.info(f"{player.name}: простуда вылечена автоматически")

    # === Заражение крови — счётчик мягких дебаффов ===
    if 'заражение_крови' in player.diseases:
        soft_left = getattr(player, 'blood_infection_soft_transitions', 0)
        if soft_left > 0:
            player.blood_infection_soft_transitions = soft_left - 1
            if player.blood_infection_soft_transitions == 0:
                player.diseases.remove('заражение_крови')
                result['blood_soft_removed'] = True
                messages.append("✅ **Заражение крови полностью вылечено!**")
                logger.info(f"{player.name}: заражение крови прошло")

    return result


# ==================== УРОН ОТ БОЛЕЗНЕЙ ====================

def apply_disease_damage_on_transition(player) -> dict:
    """
    Урон от болезней при переходе.
    Обморожение — НЕ здесь (см. cold_system).
    Простуда — 0 урона.
    Заражение крови — 2 урона.
    Лучевая и хим. отравление — как в конфиге.
    """
    ensure_disease_fields(player)

    result = {
        "total_damage": 0.0,
        "messages": [],
        "killed": False,
    }

    if not player.diseases:
        return result

    for disease_id in list(player.diseases):
        if disease_id == 'обморожение':
            continue  # обрабатывается в cold_system
        if disease_id == 'простуда':
            continue  # простуда не наносит урон

        disease = get_disease_data(disease_id)
        if not disease:
            continue

        dmg = disease.get('damage_per_transition', 0)
        if dmg <= 0:
            continue

        zones = disease.get('damage_zones', ['голова', 'торс', 'руки', 'ноги'])
        per_zone = dmg / len(zones)

        for zone in zones:
            if zone in player.body_parts and player.body_parts[zone].get('hp', 0) > 0:
                player.take_body_part_damage(zone, per_zone)

        result['total_damage'] += dmg
        result['messages'].append(
            f"{disease.get('emoji', '💀')} **{disease.get('name', disease_id)}**: -{dmg:.0f} HP"
        )

        if not player.is_alive:
            result['killed'] = True
            break

    return result


# ==================== ЛЕЧЕНИЕ ====================

def cure_disease(player, disease_id: str) -> dict:
    ensure_disease_fields(player)

    if disease_id not in player.diseases:
        return {"success": False, "message": f"❌ У вас нет этой болезни!"}

    # Обморожение не лечится медикаментами
    if disease_id == 'обморожение':
        return {
            "success": False,
            "message": "❌ Обморожение лечится только согревом у костра!",
        }

    disease = get_disease_data(disease_id)
    if not disease.get('curable', False):
        return {"success": False, "message": f"❌ {disease.get('name', disease_id)} неизлечима!"}

    player.diseases.remove(disease_id)

    # Сброс счётчиков при лечении
    if disease_id == 'простуда':
        player.cold_sickness_transitions = 0
    elif disease_id == 'заражение_крови':
        player.blood_infection_soft_transitions = 0

    return {
        "success": True,
        "message": f"✅ Вы вылечены от **{disease.get('name', disease_id)}**!",
    }


# ==================== ОБРАБОТКА ПЕРЕХОДА ====================

def process_transition_effects(player, from_station_id: str, to_station_id: str,
                               game_manager=None) -> dict:
    ensure_disease_fields(player)

    from config.map_config import STATIONS_DICT

    def _is_safe(sid):
        s = STATIONS_DICT.get(sid, {})
        return not s.get('ruined', False) and s.get('danger', 0) < 3

    from_safe = _is_safe(from_station_id)
    to_safe = _is_safe(to_station_id)

    decay = decay_on_transition(player, from_safe, to_safe)
    disease_dmg = apply_disease_damage_on_transition(player)

    # 0.4.5: обновляем счётчики болезней (авто-излечение простуды/заражения)
    transitions = update_disease_transitions(player, from_safe, to_safe)

    extra_msg = ""
    if transitions.get('messages'):
        extra_msg = "\n".join(transitions['messages'])

    return {
        "decay_message": decay.get('message', ''),
        "disease_message": "\n".join(disease_dmg.get('messages', [])),
        "transition_message": extra_msg,
        "killed": disease_dmg.get('killed', False),
    }


# ==================== UI ====================

def format_status(player) -> str:
    ensure_disease_fields(player)

    rad_cfg = get_radiation_config()
    chem_cfg = get_chemical_config()

    lines = [
        f"☢️ Радиация: **{player.radiation:.0f}/{rad_cfg.get('max', 100)}** "
        f"(порог болезни: {rad_cfg.get('threshold', 50)})",
        f"☣️ Химия: **{player.chemical:.0f}/{chem_cfg.get('max', 100)}** "
        f"(порог болезни: {chem_cfg.get('threshold', 25)})",
    ]

    if player.diseases:
        lines.append("\n💀 **Активные болезни:**")
        for disease_id in player.diseases:
            if disease_id == 'обморожение':
                from .cold_system import get_frostbite_damage_per_turn
                lines.append(f"  🥶 **Обморожение** — -{get_frostbite_damage_per_turn():.0f} HP/ход")
                continue
            d = get_disease_data(disease_id)
            dmg = d.get('damage_per_transition', 0)
            if dmg > 0:
                lines.append(
                    f"  {d.get('emoji', '')} **{d.get('name', disease_id)}** — "
                    f"-{dmg:.0f} HP/переход"
                )
            else:
                lines.append(f"  {d.get('emoji', '')} **{d.get('name', disease_id)}**")
    else:
        lines.append("\n✅ Болезней нет")

    return "\n".join(lines)


def format_detailed_status(player) -> str:
    ensure_disease_fields(player)

    rad_cfg = get_radiation_config()
    chem_cfg = get_chemical_config()

    lines = []

    rad_pct = (player.radiation / rad_cfg.get('max', 100)) * 100
    rad_bar = "█" * int(rad_pct / 10) + "░" * (10 - int(rad_pct / 10))
    lines.append(f"☢️ **Радиация** [{rad_bar}] {player.radiation:.0f}/100")

    chem_pct = (player.chemical / chem_cfg.get('max', 100)) * 100
    chem_bar = "█" * int(chem_pct / 10) + "░" * (10 - int(chem_pct / 10))
    lines.append(f"☣️ **Химия** [{chem_bar}] {player.chemical:.0f}/100")

    # Холод
    from .cold_system import format_detailed_status as format_cold
    lines.append("")
    lines.append(format_cold(player))

    # 0.4.5: кровотечение
    if getattr(player, 'bleeding_stacks', None):
        preview = player.get_bleeding_preview()
        parts = ", ".join(f"{p} -{d:.0f}" for p, d in preview['damage_by_part'].items())
        lines.append(f"\n🩸 **Кровотечение:** {preview['stacks']} стек. → {parts}")

    if player.diseases:
        lines.append("\n💀 **Болезни:**")
        for disease_id in player.diseases:
            if disease_id == 'обморожение':
                from .cold_system import get_frostbite_damage_per_turn
                lines.append(
                    f"  🥶 **Обморожение** (лечится согревом) — "
                    f"-{get_frostbite_damage_per_turn():.0f} HP/ход"
                )
                continue

            d = get_disease_data(disease_id)
            curable = "лечится" if d.get('curable') else "неизлечимо"

            extra = ""
            if disease_id == 'простуда':
                need_danger = BALANCE.get('cold_sickness', {}).get('auto_cure_danger_transitions', 15)
                need_safe = BALANCE.get('cold_sickness', {}).get('auto_cure_safe_transitions', 30)
                extra = f" (пройдёт: {player.cold_sickness_transitions}/{need_safe} безоп. или {need_danger} опасн.)"
            elif disease_id == 'заражение_крови':
                soft_left = getattr(player, 'blood_infection_soft_transitions', 0)
                if soft_left > 0:
                    extra = f" (смягчённые дебаффы: ещё {soft_left} переходов)"
                else:
                    extra = f" (лечение: 500 никелей у Врача)"

            dmg = d.get('damage_per_transition', 0)
            dmg_text = f" — -{dmg:.0f} HP/переход" if dmg > 0 else ""
            lines.append(
                f"  {d.get('emoji', '')} **{d.get('name', disease_id)}** "
                f"({curable}){dmg_text}{extra}"
            )
    else:
        lines.append("\n✅ Болезней нет")

    return "\n".join(lines)