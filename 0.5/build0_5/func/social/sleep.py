# -*- coding: utf-8 -*-
# func/social/sleep.py - Логика сна (0.4.6)
#
# ИСТОРИЯ:
#   0.4.6 — новый файл.
#
# Правила:
#   • Сон доступен только на безопасной станции (ruined=False и danger < 3).
#   • Спящий не участвует в ивентах, переходах, боях, PvP.
#   • Нельзя убить спящего.
#   • Пробуждение — по кнопке в /menu.
#   • Группа переводится в «Расход», если один из участников засыпает.

from ..player import Player
from ..map_data import MAP_DATA
from ..social.brigade_manager import brigade_manager
from ..social.brigade import STATE_NO_ACTIVE
from database.db import save_player
from utils.logger import get_logger

logger = get_logger()


def is_safe_station(station_id: str) -> bool:
    """Проверка: безопасная ли станция (для сна)."""
    station = MAP_DATA["станции"].get(station_id)
    if not station:
        return False
    if station.get("ruined", False):
        return False
    if station.get("danger", 0) >= 3:
        return False
    return True


def can_sleep(player: Player) -> tuple:
    """Можно ли заснуть. Возвращает (ok, reason)."""
    if not player.is_alive:
        return False, "💀 Вы мертвы!"
    if getattr(player, 'is_sleeping', False):
        return False, "😴 Вы уже спите!"
    if not is_safe_station(player.location):
        return False, "❌ Спать можно только на безопасной станции (не разрушенной, danger < 3)."

    # 0.4.6: в бою нельзя спать
    from ..combat import combat_manager
    from ..combat.pvp_manager import pvp_manager
    if combat_manager.get_combat(player.user_id) or pvp_manager.is_user_in_combat(player.user_id):
        return False, "⚔️ Нельзя спать в бою!"

    return True, "OK"


async def start_sleep(player: Player) -> str:
    """
    Перевести игрока в сон.
    Возвращает текст результата.
    """
    ok, reason = can_sleep(player)
    if not ok:
        return reason

    player.is_sleeping = True

    # 0.4.6: если игрок в группе — перевести группу в «Расход»
    brigade = brigade_manager.get_user_brigade(player.user_id)
    if brigade and brigade.is_active():
        await brigade_manager.set_state(brigade.brigade_id, STATE_NO_ACTIVE)
        logger.info(f"[Sleep] Группа {brigade.brigade_id} переведена в Расход из-за сна {player.name}")

    await save_player(player)
    logger.info(f"[Sleep] {player.name} уснул на станции {player.location}")

    station_name = MAP_DATA["станции"].get(player.location, {}).get("name", "?")
    return (
        f"😴 **{player.name}** заснул на станции **{station_name}**.\n\n"
        f"💤 Пока вы спите:\n"
        f"• Ивенты и переходы не действуют\n"
        f"• Вас нельзя атаковать\n"
        f"• Группа переведена в режим «Расход»\n\n"
        f"🔔 Чтобы проснуться — используйте /menu и нажмите «Проснуться»."
    )


async def wake_up(player: Player) -> str:
    """Разбудить игрока."""
    if not getattr(player, 'is_sleeping', False):
        return "❌ Вы не спите."

    player.is_sleeping = False
    await save_player(player)
    logger.info(f"[Sleep] {player.name} проснулся")

    station_name = MAP_DATA["станции"].get(player.location, {}).get("name", "?")
    return f"☀️ **{player.name}** проснулся на станции **{station_name}**."


def should_skip_player(player: Player) -> bool:
    """
    Утилита: должен ли игрок быть пропущен в ивентах/переходах/боях.
    Используется в global_events, move_mixin и т.п.
    """
    return bool(getattr(player, 'is_sleeping', False))