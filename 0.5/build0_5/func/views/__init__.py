# -*- coding: utf-8 -*-
# func/views/__init__.py - Импорты всех view (Билд 0.4.8.8)

from .map_display import show_map
from .modal import CreateCharacterModal, AccessKeyModal
from .main_menu import MainMenu
from .status import StatusView
from .action_menu import ActionMenu
from .look_around import LookAroundMenu
from .move import MoveMenu, MoveResultView
from .food import FoodMenu, FoodEmptyMenu, FoodBuyMenu
from .trade import TradeMenu, WorkshopMenu
from .weapon_shop import (
    WeaponShopMainMenu, WeaponTypeMenu, MagazineBuyMenu, MeleeBuyMenu,
    ModuleSlotMenu
)
from .ammo import AmmoBuyMenu
from .filter_buy import FilterBuyMenu
from .equipment import (
    EquipmentMenu, EquipmentLoadMenu, EquipmentLoadSelectMenu,
    MagazineInsertMenu, ModuleManagementMenu, ModuleInstallSelect,
    MeleeChangeMenu
)
from .gas_mask import GasMaskMenu, FilterManagementMenu, FilterEquipMenu
from .combat_views import CombatView
from .campfire import CampfireMenu, CampfireEmptyMenu
from .technical_tunnel import TechnicalTunnelMenu
from .skills import SkillsView, SkillsUpgradeView
from .tutorial import TutorialView, build_tutorial_page

# === Патч 0.4.3+ ===
from .pharmacy import PharmacyMenu, PharmacyGoodsMenu, PharmacyDoctorMenu
from .armor_shop import ArmorShopMainMenu, ArmorShopBuyMenu
from .armor_manage import ArmorManageMenu, ArmorEquipSelect
from .faction_view import FactionsMenu, FactionDetailView, build_factions_embed, build_faction_detail_embed
from .repair_view import RepairMenu
from .independent_trader_view import IndependentTraderView

from .helpers import (
    game_manager, MAP_DATA, save_player, combat_manager,
    WEAPONS, get_current_filter_info, get_trade_discount,
    get_stamina_multiplier, can_move, current_event,
    get_active_effects, GLOBAL_EVENTS_ENABLED,
    get_event_color, get_event_icon, get_filter_discount,
    is_workshop_station, is_celebration_station,
    check_tunnel, get_tunnel_zone_type, check_tunnel_contamination,
    enter_technical_tunnel, get_weapon, get_magazine, get_ammo_type,
    get_caliber_ammo_types, get_weapon_accuracy, get_weapon_price,
    get_magazine_price, get_ammo_price, get_current_ammo,
    get_weapon_max_ammo, get_available_magazines_for_weapon,
    format_weapon_info, format_magazine_info, format_ammo_info,
    get_food, get_food_price, get_food_stamina, get_food_emoji,
    format_food_inventory, can_cook, get_cooked_version,
    get_filter, get_filter_price, get_filter_name, get_filter_emoji,
    get_filter_durability, format_filters_inventory,
    equip_filter, unequip_filter,
    get_armor_item, format_armor_status,
    ensure_disease_fields, format_disease_status,
    get_shop_item, get_doctor_service,
)

from .prologue import PrologueView, build_scene_embed
from .faction_npc import NPCPickerView, DialogView, build_npc_list_embed