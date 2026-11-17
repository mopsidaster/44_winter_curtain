# -*- coding: utf-8 -*-
# func/spec_weapons/grenades.py - Ручные гранаты (Билд 0.4.4.5)
#
# Механика:
#   • Метание = полноценный ход.
#   • duds_chance — граната не взвелась.
#   • self_explode_chance — игрок взорвал себя.
#   • Каждый враг: dodge_chance (25%) — укрылся.
#   • Один общий бросок miss_one_chance (5%) — одна цель не получит урон.
#   • Урон damage распределяется СЛУЧАЙНО между всеми живыми врагами,
#     сумма долей = damage.
#   • explosive_multiplier (например ×2 для Ф-1) применяется к доле
#     каждого врага, у которого ЗОНА ПОПАДАНИЯ НЕ ПОКРЫТА бронёй.
#   • Броня НЕ поглощает урон гранаты отдельно — либо множитель, либо нет.

import random
from config.map_config import WEAPONS, BALANCE


def get_grenade_data(grenade_id: str) -> dict:
    return WEAPONS.get(grenade_id, {})


def is_grenade(grenade_id: str) -> bool:
    data = get_grenade_data(grenade_id)
    return data.get('type') == 'grenade'


def _choose_part_for_target(target, preferred_part: str = None) -> str:
    """
    Выбрать часть тела для попадания гранаты.
    Граната бьёт по площади — считаем, что попадает в случайную доступную
    часть тела цели.
    """
    try:
        available = target.get_available_parts()
    except Exception:
        available = []

    if not available:
        # fallback
        available = ["торс"]

    # Если задана конкретная часть и она доступна — используем её
    if preferred_part and preferred_part in available:
        return preferred_part

    return random.choice(available)


def _distribute_damage(total_damage: float, count: int) -> list:
    """
    Распределить total_damage на count долей СЛУЧАЙНО так,
    чтобы сумма долей = total_damage.
    """
    if count <= 0:
        return []

    # Генерируем count-1 случайных «точек разреза» в [0, total_damage]
    cuts = sorted(random.uniform(0, total_damage) for _ in range(count - 1))
    shares = []
    prev = 0.0
    for c in cuts:
        shares.append(c - prev)
        prev = c
    shares.append(total_damage - prev)

    # Перемешиваем, чтобы доли не были привязаны к порядку врагов
    random.shuffle(shares)
    return shares


def throw_grenade(player, grenade_id: str, enemies: list,
                  distance: str = "medium",
                  skills: dict = None,
                  preferred_part: str = None) -> dict:
    """
    Метание гранаты.

    Args:
        player: объект Player
        grenade_id: 'ргд_5' | 'ф_1'
        enemies: список Combatant (все, включая мёртвых — фильтруем внутри)
        distance: 'close' | 'medium' | 'far' (на урон не влияет, только информативно)
        skills: player.skills (dict)
        preferred_part: необязательная фиксированная часть тела

    Returns:
        {
          "success": bool,
          "duds": bool,
          "self_exploded": bool,
          "self_damage": float,
          "self_killed": bool,
          "hits": [{"enemy_index", "part", "damage", "covered", "explosive_applied"}],
          "total_damage": float,
          "message": str,
        }
    """
    result = {
        "success": False,
        "duds": False,
        "self_exploded": False,
        "self_damage": 0.0,
        "self_killed": False,
        "hits": [],
        "total_damage": 0.0,
        "message": "",
    }

    grenade = get_grenade_data(grenade_id)
    if not grenade or grenade.get('type') != 'grenade':
        result['message'] = "❌ Это не граната!"
        return result

    name = grenade.get('name', grenade_id)
    emoji = grenade.get('emoji', '💣')
    base_damage = float(grenade.get('damage', 0.0))
    duds_chance = float(grenade.get('duds_chance', 0))
    self_chance = float(grenade.get('self_explode_chance', 0))
    dodge_chance = float(grenade.get('dodge_chance', 25))
    miss_one_chance = float(grenade.get('miss_one_chance', 0))
    explosive_mult = float(grenade.get('explosive_multiplier', 1.0))

    # === 1. Проверка: не взвелась ===
    if random.uniform(0, 100) <= duds_chance:
        result['success'] = True
        result['duds'] = True
        result['message'] = (
            f"💤 {emoji} **{name}** не взвелась! Щелчок — и тишина...\n"
            f"Ход потрачен."
        )
        return result

    # === 2. Проверка: самоподрыв ===
    if random.uniform(0, 100) <= self_chance:
        self_dmg_mult = float(BALANCE.get('throwables', {}).get('grenade_self_damage_mult', 1.0))
        self_zone = BALANCE.get('throwables', {}).get('grenade_self_hits_zone', 'торс')
        self_damage = base_damage * self_dmg_mult

        result['success'] = True
        result['self_exploded'] = True
        result['self_damage'] = self_damage

        # Наносим урон игроку через Combatant-логику вызывающего кода:
        # здесь только считаем, применяет combat.py.
        result['message'] = (
            f"💥 {emoji} **{name}** взорвалась в руках!\n"
            f"☠️ Вы получаете **{self_damage:.1f}** урона в {self_zone}!"
        )
        return result

    # === 3. Собираем живых врагов ===
    alive_indices = []
    for i, e in enumerate(enemies):
        if getattr(e, 'is_alive', False):
            alive_indices.append(i)

    if not alive_indices:
        result['success'] = True
        result['message'] = f"💥 {emoji} **{name}** взорвалась впустую — врагов нет."
        return result

    count = len(alive_indices)

    # === 4. Распределяем урон ===
    shares = _distribute_damage(base_damage, count)

    # === 5. Один общий бросок «одна цель не получит урон» ===
    miss_one_index = None
    if miss_one_chance > 0 and count >= 2 and random.uniform(0, 100) <= miss_one_chance:
        miss_one_index = random.choice(alive_indices)

    # === 6. Обрабатываем каждого врага ===
    hits = []
    total_dealt = 0.0
    target_iter = list(zip(alive_indices, shares))
    random.shuffle(target_iter)

    lines = []

    for enemy_idx, share in target_iter:
        enemy = enemies[enemy_idx]
        part = _choose_part_for_target(enemy, preferred_part)

        # Укрытие
        if random.uniform(0, 100) <= dodge_chance:
            hits.append({
                "enemy_index": enemy_idx,
                "part": part,
                "damage": 0.0,
                "covered": True,
                "explosive_applied": False,
            })
            lines.append(f"   • {enemy.display_name} #{enemy_idx + 1}: укрылся 🛡️")
            continue

        # «Одна цель не получит урон»
        if miss_one_index is not None and enemy_idx == miss_one_index:
            hits.append({
                "enemy_index": enemy_idx,
                "part": part,
                "damage": 0.0,
                "covered": False,
                "missed_by_chance": True,
                "explosive_applied": False,
            })
            lines.append(f"   • {enemy.display_name} #{enemy_idx + 1}: осколки не задели 💨")
            continue

        # Экспансивный множитель: если у цели зона НЕ покрыта бронёй
        explosive_applied = False
        final_share = share
        if explosive_mult > 1.0:
            covered = _is_zone_covered(enemy, part)
            if not covered:
                final_share = share * explosive_mult
                explosive_applied = True

        hits.append({
            "enemy_index": enemy_idx,
            "part": part,
            "damage": final_share,
            "covered": False,
            "explosive_applied": explosive_applied,
        })
        total_dealt += final_share

        suffix = " (экспансив ×{:.1f})".format(explosive_mult) if explosive_applied else ""
        lines.append(
            f"   • {enemy.display_name} #{enemy_idx + 1}: "
            f"{part} — **{final_share:.1f}** урона{suffix}"
        )

    result['success'] = True
    result['hits'] = hits
    result['total_damage'] = total_dealt

    summary = (
            f"💥 {emoji} **{name}** взорвалась!\n"
            f"🎯 Шанс укрытия у врагов: {dodge_chance:.0f}%\n"
            f"📊 Базовый урон: **{base_damage:.0f}**"
            + (f" (экспансив ×{explosive_mult:.1f} по небронированным)" if explosive_mult > 1.0 else "")
            + "\n"
            + "\n".join(lines)
            + f"\n\n💥 **Итого нанесено: {total_dealt:.1f}**"
    )

    result['message'] = summary
    return result


def _is_zone_covered(target, part: str) -> bool:
    """
    Покрыта ли часть тела бронёй цели.
    Для NPC — через equipped_armor_id / equipped_helmet_id.
    Для игрока — через armor / helmet.
    """
    try:
        from ..armor_system import get_armor_item

        armor_id = getattr(target, 'armored_id', None) or getattr(target, 'armor', None) or \
                   getattr(target, 'equipped_armor_id', None)
        helmet_id = getattr(target, 'helmet', None) or getattr(target, 'equipped_helmet_id', None)

        if armor_id:
            a = get_armor_item(armor_id)
            if isinstance(a, dict) and part in a.get('zones', []):
                return True

        if helmet_id:
            h = get_armor_item(helmet_id)
            if isinstance(h, dict) and part in h.get('zones', []):
                return True

        return False
    except Exception:
        return False