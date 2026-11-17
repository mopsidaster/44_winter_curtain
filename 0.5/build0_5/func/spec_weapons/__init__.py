# -*- coding: utf-8 -*-
# func/spec_weapons/__init__.py - Пакет специального оружия (Билд 0.4.4.5)

from .grenade_launcher import (
    can_fire_grenade_launcher,
    fire_single_target,
    fire_group_target,
    get_grenade_launcher_info,
)

from .raider import (
    should_spawn_raider,
    get_raider_config,
    get_raider_weapon_setup,
    get_raider_armor_setup,
    get_raider_body_parts,
    get_raider_hit_chance,
    get_raider_damage,
    get_companion_ids,
)

# === 0.4.4.5: ручные гранаты и метательные ножи ===
from .grenades import (
    throw_grenade,
    is_grenade,
    get_grenade_data,
)

from .throwing_knives import (
    throw_knife,
    is_throwing_knife,
    get_knife_data,
    calculate_throw_accuracy,
)