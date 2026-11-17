# -*- coding: utf-8 -*-
# func/combat/__init__.py - Публичный API боевой системы (0.4.6)

from .constants import MAX_COMBAT_LOG, DISTANCES, DISTANCE_NAMES
from .helpers import (
    MUTANTS_CONFIG, MUTANTS_DATA, LOOT_ITEMS, SPAWN_CONFIG,
    get_mutant_data,
    get_random_mutant,
    pick_enemy_type,
    get_random_enemy,
    get_max_enemies,
    get_enemies_count,
    get_spawn_chance,
    get_event_wave_multiplier,
)
from .combatant import Combatant
from .combat import Combat
from .manager import CombatManager, combat_manager
from .api import (
    start_combat,
    start_combat_no_interaction,
    send_combat_log,
    send_combat_logs,
    update_combat_status,
    give_combat_reward,
    handle_combat_action,
)

# === 0.4.6 PvP ===
from .player_combatant import PlayerCombatant
from .pvp_manager import PvPManager, pvp_manager
from .pvp_combat import PvPCombat
from .api_pvp import handle_pvp_action

__all__ = [
    "MAX_COMBAT_LOG", "DISTANCES", "DISTANCE_NAMES",
    "MUTANTS_CONFIG", "MUTANTS_DATA", "LOOT_ITEMS", "SPAWN_CONFIG",
    "get_mutant_data", "get_random_mutant", "pick_enemy_type",
    "get_random_enemy", "get_max_enemies", "get_enemies_count",
    "get_spawn_chance", "get_event_wave_multiplier",
    "Combatant", "Combat",
    "CombatManager", "combat_manager",
    "start_combat", "start_combat_no_interaction",
    "send_combat_log", "send_combat_logs", "update_combat_status",
    "give_combat_reward", "handle_combat_action",
    # 0.4.6
    "PlayerCombatant", "PvPManager", "pvp_manager", "PvPCombat",
    "handle_pvp_action",
]