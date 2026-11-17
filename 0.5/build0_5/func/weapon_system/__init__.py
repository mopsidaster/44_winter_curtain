# -*- coding: utf-8 -*-
# func/weapon_system/__init__.py - Публичный API (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.5   — bleeding
#   0.4.7.2 — get_weapon_damage_with_modules
#   0.4.7.6 — подтипы sniper
#   0.4.8.8 — _get_headshot_accuracy_bonus
#   0.4.8.7 — get_weapon_double_shot_config (Дуплет)

from .weapons import (
    get_weapon,
    get_weapon_type,
    is_spec_weapon,
    is_shotgun,
    is_shell_loaded_weapon,
    is_smg,
    is_mg,
    is_light_mg,
    is_heavy_mg,
    is_grenade,
    is_throwing_knife,
    is_throwable,
    has_builtin_suppressor,
    get_weapon_damage,
    get_weapon_damage_with_modules,
    get_modules_damage_bonus,
    get_weapon_base_accuracy,
    get_shotgun_damage_multiplier,
    is_shotgun_far_blocked,
    get_shotgun_close_bonus,
    get_shotgun_ammo_damage_bonus,
    is_pistol_caliber,
    # 0.4.7.6
    is_sniper,
    get_sniper_subtype,
    is_semi_auto_sniper,
    is_bolt_action_sniper,
    get_sniper_subtype_config,
    # 0.4.8.7
    get_weapon_double_shot_config,
)

from .accuracy import get_weapon_accuracy

from .modules import (
    get_module_slots,
    get_module_slot,
    can_install_module,
    get_modules_for_weapon,
    uninstall_all_modules,
)

from .ammo import (
    get_magazine,
    get_weapon_magazines,
    is_magazine_compatible,
    get_magazine_capacity,
    get_available_magazines_for_weapon,
    get_weapon_max_ammo,
    get_current_ammo,
    get_ammo_types_in_magazine,
    can_reload,
    get_weapon_safe,
    get_ammo_type,
    get_caliber,
    get_caliber_ammo_types,
    get_ammo_type_for_caliber,
    get_ammo_price,
    get_ammo_price_for_weapon,
    is_armor_piercing,
    is_incendiary,
    is_expansive,
    is_buckshot,
    is_slug,
    is_shotgun_ammo,
    ammo_ignores_armor,
    get_ammo_damage_multiplier,
    get_incendiary_config,
    get_incendiary_damage_per_tick,
    get_incendiary_turns_per_stack,
    get_incendiary_stacks_enabled,
    get_bleeding_config,
    is_bleeding_ammo,
    get_bleeding_ammo_chances,
    # 0.4.6.3
    make_ammo_key,
    parse_ammo_key,
    is_new_ammo_key,
)

from .prices import (
    get_weapon_price,
    get_magazine_price,
    get_module_price,
)

from .formatting import (
    format_weapon_info,
    format_magazine_info,
    format_ammo_info,
    format_module_info,
)

from .misc import (
    get_shots_per_action,
    get_ammo_cost_per_action,
    get_random_ammo_type,
    get_headshot_accuracy,
)

from ._helpers import (
    _parse_zoom_from_id,
    _is_module_compatible,
    _get_modules_accuracy_bonus,
    _get_optics_close_penalty,
    _get_headshot_accuracy_bonus,
)


__all__ = [
    # weapons
    "get_weapon", "get_weapon_type", "is_spec_weapon", "is_shotgun",
    "is_shell_loaded_weapon", "is_smg", "is_mg", "is_light_mg", "is_heavy_mg",
    "is_grenade", "is_throwing_knife", "is_throwable", "has_builtin_suppressor",
    "get_weapon_damage", "get_weapon_damage_with_modules", "get_modules_damage_bonus",
    "get_weapon_base_accuracy",
    "get_shotgun_damage_multiplier", "is_shotgun_far_blocked",
    "get_shotgun_close_bonus", "get_shotgun_ammo_damage_bonus",
    "is_pistol_caliber",
    # sniper subtypes
    "is_sniper", "get_sniper_subtype", "is_semi_auto_sniper",
    "is_bolt_action_sniper", "get_sniper_subtype_config",
    # 0.4.8.7
    "get_weapon_double_shot_config",
    # accuracy
    "get_weapon_accuracy",
    # modules
    "get_module_slots", "get_module_slot", "can_install_module",
    "get_modules_for_weapon", "uninstall_all_modules",
    # ammo
    "get_magazine", "get_weapon_magazines", "is_magazine_compatible",
    "get_magazine_capacity", "get_available_magazines_for_weapon",
    "get_weapon_max_ammo", "get_current_ammo", "get_ammo_types_in_magazine",
    "can_reload", "get_weapon_safe",
    "get_ammo_type", "get_caliber", "get_caliber_ammo_types",
    "get_ammo_type_for_caliber", "get_ammo_price", "get_ammo_price_for_weapon",
    "is_armor_piercing", "is_incendiary", "is_expansive", "is_buckshot",
    "is_slug", "is_shotgun_ammo", "ammo_ignores_armor", "get_ammo_damage_multiplier",
    "get_incendiary_config", "get_incendiary_damage_per_tick",
    "get_incendiary_turns_per_stack", "get_incendiary_stacks_enabled",
    # bleeding
    "get_bleeding_config", "is_bleeding_ammo", "get_bleeding_ammo_chances",
    # 0.4.6.3
    "make_ammo_key", "parse_ammo_key", "is_new_ammo_key",
    # prices
    "get_weapon_price", "get_magazine_price", "get_module_price",
    # formatting
    "format_weapon_info", "format_magazine_info", "format_ammo_info", "format_module_info",
    # misc
    "get_shots_per_action", "get_ammo_cost_per_action",
    "get_random_ammo_type", "get_headshot_accuracy",
    # helpers
    "_parse_zoom_from_id", "_is_module_compatible",
    "_get_modules_accuracy_bonus", "_get_optics_close_penalty",
    "_get_headshot_accuracy_bonus",
]