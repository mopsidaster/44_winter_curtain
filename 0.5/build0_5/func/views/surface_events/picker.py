# -*- coding: utf-8 -*-
# func/views/surface_events/picker.py - Выбор ивента (0.4.8.8)

import random
from utils.logger import get_logger

logger = get_logger()

# Все ивенты: id -> {solo, group, weight}
SURFACE_EVENTS = {
    "pack_merzlyaks":  {"solo": True,  "group": True,  "weight": 10},
    "snowdrift":       {"solo": True,  "group": True,  "weight": 10},
    "pack_strazh":     {"solo": True,  "group": True,  "weight": 8},
    "demon":           {"solo": True,  "group": True,  "weight": 3},   # Демон-ивент (не босс-спавн)
    "encirclement":    {"solo": True,  "group": False, "weight": 6},
    "lured_merzlyak":  {"solo": True,  "group": False, "weight": 6},
    "raider":          {"solo": False, "group": True,  "weight": 5},
    "artifact_bridge": {"solo": True,  "group": True,  "weight": 8},
    "artifact_lobby":  {"solo": True,  "group": True,  "weight": 8},
}

SURFACE_EVENT_IDS = list(SURFACE_EVENTS.keys())


def pick_surface_event(leader, group_players: list) -> str:
    """
    Случайный ивент с учётом solo/group.
    """
    is_group = len(group_players) > 1
    pool = []
    for eid, cfg in SURFACE_EVENTS.items():
        if is_group and not cfg["group"]:
            continue
        if not is_group and not cfg["solo"]:
            continue
        pool.extend([eid] * cfg["weight"])

    if not pool:
        return "snowdrift"

    chosen = random.choice(pool)
    logger.info(
        f"[SURFACE] event picked: {chosen} "
        f"(group={is_group}, players={len(group_players)})"
    )
    return chosen