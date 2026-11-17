# -*- coding: utf-8 -*-
# func/combat/mutation.py - Уровень Мутации мутантов (0.4.7.6)
#
# ТЕСТОВАЯ МЕХАНИКА.
# Отключается флагом mutation.enabled = false в balance.json.
#
# Правила:
#   • Уровни УМ0..УМ5 (максимум 5).
#   • Шанс уровня зависит от danger станции (см. balance.mutation.chances_by_danger).
#   • УМ увеличивает базовый урон и HP частей тела мутанта.
#   • Работает ТОЛЬКО для мутантов с флагом can_mutate: true.

import random

from config.map_config import BALANCE
from utils.logger import get_logger

logger = get_logger()


# ==================== КОНФИГ ====================

def get_mutation_config() -> dict:
    return BALANCE.get('mutation', {})


def is_mutation_enabled() -> bool:
    cfg = get_mutation_config()
    return bool(cfg.get('enabled', False))


def get_max_mutation_level() -> int:
    cfg = get_mutation_config()
    try:
        return int(cfg.get('max_level', 5))
    except (TypeError, ValueError):
        return 5


def get_level_data(level: int) -> dict:
    cfg = get_mutation_config()
    levels = cfg.get('levels', {})
    return levels.get(str(level), {"damage_bonus": 0, "health_multiplier": 1.0})


def get_chances_by_danger(danger: int) -> list:
    """
    Возвращает список вероятностей для УМ0..УМ5 для данной danger станции.
    Если danger вне диапазона — берётся ближайший.
    """
    cfg = get_mutation_config()
    chances = cfg.get('chances_by_danger', {})

    if not chances:
        return [100, 0, 0, 0, 0, 0]

    # Ищем точное совпадение
    key = str(danger)
    if key in chances:
        return list(chances[key])

    # Ближайший меньший
    try:
        keys = sorted(int(k) for k in chances.keys())
    except ValueError:
        return [100, 0, 0, 0, 0, 0]

    if not keys:
        return [100, 0, 0, 0, 0, 0]

    if danger <= keys[0]:
        return list(chances[str(keys[0])])
    if danger >= keys[-1]:
        return list(chances[str(keys[-1])])

    for i in range(len(keys) - 1):
        if keys[i] <= danger <= keys[i + 1]:
            # Берём меньший (консервативно)
            return list(chances[str(keys[i])])

    return [100, 0, 0, 0, 0, 0]


# ==================== ВЫБОР УРОВНЯ ====================

def get_max_level_by_danger(danger: int) -> int:
    """
    0.4.7.8: жёсткий лимит уровня мутации для спавна в зависимости от danger.
    """
    cfg = get_mutation_config()
    limits = cfg.get('max_level_by_danger', {})
    if not limits:
        return get_max_mutation_level()

    key = str(danger)
    if key in limits:
        try:
            return int(limits[key])
        except (TypeError, ValueError):
            pass

    # Если danger вне диапазона — берём ближайший
    try:
        keys = sorted(int(k) for k in limits.keys())
    except ValueError:
        return get_max_mutation_level()

    if not keys:
        return get_max_mutation_level()

    if danger <= keys[0]:
        return int(limits[str(keys[0])])
    if danger >= keys[-1]:
        return int(limits[str(keys[-1])])

    for i in range(len(keys) - 1):
        if keys[i] <= danger <= keys[i + 1]:
            return int(limits[str(keys[i])])

    return get_max_mutation_level()


def roll_mutation_level(danger: int) -> int:
    """
    Бросает уровень мутации.
    0.4.7.8: применяется max_level_by_danger — жёсткий лимит сверху.
    """
    if not is_mutation_enabled():
        return 0

    max_level_global = get_max_mutation_level()
    max_level_limit = get_max_level_by_danger(danger)
    max_level = min(max_level_global, max_level_limit)

    if max_level <= 0:
        return 0

    chances = get_chances_by_danger(danger)

    # Обрезаем до max_level+1
    target_len = max_level + 1
    if len(chances) < target_len:
        chances = chances + [0] * (target_len - len(chances))
    else:
        chances = chances[:target_len]

    total = sum(chances)
    if total <= 0:
        return 0

    roll = random.uniform(0, total)
    cumulative = 0.0

    for level, chance in enumerate(chances):
        cumulative += chance
        if roll <= cumulative:
            return level

    return 0


def can_mutate(mutant_data: dict) -> bool:
    """Может ли этот мутант получать уровень мутации."""
    if not isinstance(mutant_data, dict):
        return False
    if not mutant_data.get('is_mutant', False):
        return False
    if mutant_data.get('is_boss', False):
        return False
    if not mutant_data.get('can_mutate', False):
        return False
    return True


# ==================== ПРИМЕНЕНИЕ ====================

def apply_mutation_to_enemy(enemy, level: int, danger: int) -> dict:
    """
    Применяет уровень мутации к объекту Combatant (enemy).

    Изменяет:
      • base_damage — через enemy.mutation_damage_bonus (используется в get_enemy_action).
      • body_parts HP — умножает на health_multiplier.
      • lives / max_lives — пересчитывает.

    Возвращает словарь с изменениями (для логирования).
    """
    result = {
        "level": level,
        "damage_bonus": 0,
        "health_multiplier": 1.0,
        "applied": False,
    }

    if not is_mutation_enabled():
        return result

    if level <= 0:
        enemy.mutation_level = 0
        enemy.mutation_damage_bonus = 0
        return result

    if not can_mutate(getattr(enemy, 'mutant_data', {}) or {}):
        enemy.mutation_level = 0
        enemy.mutation_damage_bonus = 0
        return result

    max_level = get_max_mutation_level()
    level = min(level, max_level)

    # Суммируем бонусы накопительно (с УМ1 до УМN включительно)
    total_damage_bonus = 0
    total_health_mult = 1.0

    for lvl in range(1, level + 1):
        data = get_level_data(lvl)
        try:
            total_damage_bonus += float(data.get('damage_bonus', 0))
        except (TypeError, ValueError):
            pass
        try:
            total_health_mult *= float(data.get('health_multiplier', 1.0))
        except (TypeError, ValueError):
            pass

    enemy.mutation_level = level
    enemy.mutation_damage_bonus = total_damage_bonus

    # Применяем HP ко всем частям тела
    if hasattr(enemy, 'body_parts') and isinstance(enemy.body_parts, dict):
        for part_name, part in enemy.body_parts.items():
            if not isinstance(part, dict):
                continue
            try:
                base_hp = float(part.get('hp', 0))
                base_max = float(part.get('max_hp', 0))
            except (TypeError, ValueError):
                continue

            new_hp = int(round(base_hp * total_health_mult))
            new_max = int(round(base_max * total_health_mult))

            part['hp'] = new_hp
            part['max_hp'] = new_max

    # Пересчитываем lives / max_lives
    try:
        new_lives = sum(
            int(p.get('hp', 0)) for p in enemy.body_parts.values()
            if isinstance(p, dict)
        )
        enemy.lives = new_lives
        enemy.max_lives = new_lives
    except Exception as e:
        logger.error(f"[MUTATION] не смог пересчитать lives: {e}")

    result['damage_bonus'] = total_damage_bonus
    result['health_multiplier'] = total_health_mult
    result['applied'] = True

    logger.info(
        f"[MUTATION] {getattr(enemy, 'display_name', '?')} получил УМ{level}: "
        f"+{total_damage_bonus} урона, HP ×{total_health_mult:.2f}"
    )

    return result


def get_mutation_display(level: int) -> str:
    """Строка для отображения в бою. Например: 'УМ2 🧬'."""
    if level <= 0:
        return ""
    return f"🧬 УМ{level}"