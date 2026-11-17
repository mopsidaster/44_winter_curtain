# -*- coding: utf-8 -*-
# func/views/helpers.py - Общие импорты для views (Билд 0.4.9.0 Visual)
#
# ОПТИМИЗАЦИЯ (патч 0.4.2.10):
#   • Убран monkey-patch game_manager.get_player
#   • Убрана ensure_skills
#
# РАСШИРЕНИЕ (патч 0.4.3):
#   • Реэкспорт armor_system, disease_system, pharmacy_system
#
# ВИЗУАЛ (0.4.9.0):
#   • Добавлена функция build_progress_bar для красивых полосок HP/стамины.

import discord
import random
import uuid

from ..game_manager import game_manager
from ..map_data import MAP_DATA
from ..station_utils import (
    has_station_type, is_trade_station, is_start_station,
    get_station_type, get_station_types
)
from .map_display import show_map
from config.map_config import BALANCE, WEAPONS, ITEMS, MAGAZINES, AMMO, FOOD, FILTERS, ARMOR, DISEASES, PHARMACY
from database.db import save_player
from ..inventory import get_inventory_embed
from ..global_events import (
    get_trade_discount, get_stamina_multiplier, can_move,
    current_event, get_active_effects, GLOBAL_EVENTS_ENABLED,
    get_event_color, get_event_icon, get_filter_discount,
    is_workshop_station, is_celebration_station,
)
from ..technical_tunnels import (
    check_tunnel, get_tunnel_zone_type,
    check_tunnel_contamination, enter_technical_tunnel
)
from ..combat import combat_manager, handle_combat_action
from ..weapon_system import (
    get_weapon, get_magazine, get_ammo_type, get_caliber_ammo_types,
    get_weapon_accuracy, get_weapon_price, get_magazine_price, get_ammo_price,
    get_current_ammo, get_weapon_max_ammo, get_available_magazines_for_weapon,
    format_weapon_info, format_magazine_info, format_ammo_info
)
from ..food_system import (
    get_food, get_food_price, get_food_stamina, get_food_emoji,
    format_food_inventory, can_cook, get_cooked_version, cook_food, eat_food
)
from ..filter_system import (
    get_filter, get_filter_price, get_filter_name, get_filter_emoji,
    get_filter_durability, format_filters_inventory,
    equip_filter, unequip_filter, get_current_filter_info
)

# === Патч 0.4.3 ===
from ..armor_system import (
    get_armor_item,
    get_set_data,
    is_full_set,
    get_active_set,
    has_set_bonus,
    get_set_bonus_value,
    apply_armor_protection,
    apply_armor_after_hit,
    equip_item as equip_armor_item,
    unequip_item as unequip_armor_item,
    format_armor_status,
    format_item_info as format_armor_item_info,
    get_item_durability,
)
from ..disease_system import (
    ensure_disease_fields,
    add_radiation,
    add_chemical,
    reduce_radiation,
    cure_disease,
    process_transition_effects,
    get_radiation_config,
    get_chemical_config,
    get_disease_data,
    format_status as format_disease_status,
    format_detailed_status as format_disease_detailed,
    get_immunity_reduction,
)
from ..pharmacy_system import (
    get_shop_item,
    get_doctor_service,
    get_all_shop_items,
    get_all_doctor_services,
    buy_item as buy_pharmacy_item,
    use_medkit,
    use_antirad,
    cure_chemical_poisoning,
    format_shop_list as format_pharmacy_shop,
    format_doctor_services,
)
from ..spec_weapons.grenade_launcher import (
    can_fire_grenade_launcher,
    fire_single_target as grenade_fire_single,
    fire_group_target as grenade_fire_group,
    get_grenade_launcher_info,
)

# ==================== 0.4.9.0 VISUAL HELPERS ====================

def build_progress_bar(current: float, maximum: float, length: int = 10,
                       filled_char: str = "█", empty_char: str = "░") -> str:
    """
    Строит текстовую полоску прогресса.
    Например: █████░░░░░
    """
    if maximum <= 0:
        return empty_char * length
    pct = max(0.0, min(1.0, current / maximum))
    filled = int(round(pct * length))
    return filled_char * filled + empty_char * (length - filled)