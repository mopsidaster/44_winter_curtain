# -*- coding: utf-8 -*-
# func/player/init_mixin.py - Инициализация игрока (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.4.8 — вынесено из player.py
#   0.4.5   — bleeding_stacks, cold_transition_counter и т.д.
#   0.4.8.6 — varyag_pass_kept
#   0.4.8.7 — trader_loyalty

from config.map_config import BALANCE

from ._constants import DEFAULT_SKILLS, _normalize_skills
from utils.logger import get_logger

logger = get_logger()


class PlayerInitMixin:

    def __init__(self, user_id: int, username: str, name: str, data: dict = None):
        self.user_id = user_id
        self.username = username

        self.melee_weapon = "кулаки"
        self.melee_weapon_durability = 999
        self.body_parts = {}

        self.magazines = []
        self.equipped_magazine = None
        self.next_magazine_uid = 1

        self.ammo_inventory = {}

        self.surface_unlocked = False
        self.varyag_pass_kept = False
        self.trader_loyalty = {}

        self.equipped_filter = None
        self.filters = []
        self.food_inventory = []
        self.station_defense = 0
        self.combat_mode = False
        self.combat_target = None

        self.equipped_modules = {"scope": None, "grip": None, "muzzle": None}
        self.modules_inventory = []

        self.weapons_inventory = []
        self.melee_inventory = []

        self.skills = dict(DEFAULT_SKILLS)

        self.radiation = 0.0
        self.chemical = 0.0
        self.diseases = []

        self.armor = None
        self.helmet = None
        self.armor_durability = {"armor": 0.0, "helmet": 0.0}
        self.armor_inventory = []

        self.cold = 0.0
        self.shell_ammo = {}

        self.grenades_inventory = {}
        self.throwing_knives_inventory = {}

        self.is_burning = []
        self.mg_reload_progress = 0

        self.bleeding_stacks = []
        self.cold_transition_counter = 0
        self.cold_sickness_transitions = 0
        self.blood_infection_soft_transitions = 0

        if data:
            self._init_from_data(data, name)
        else:
            self._init_new_player(name)

        self.has_gas_mask = True

    def _init_from_data(self, data: dict, name: str):
        self.name = data.get('name', name)
        self.backstory = data.get('backstory', "Без предыстории")
        self.level = data.get('level', 1)
        self.xp = data.get('xp', 0)
        self.xp_to_next = data.get('xp_to_next', 10)
        self.stamina = data.get('stamina', BALANCE['player']['base_stamina'])
        self.max_stamina = data.get('max_stamina', BALANCE['player']['base_stamina'])
        self.location = data.get('location', "бульвар_дмитрия_донского")
        self.is_alive = data.get('is_alive', True)
        self.weapon = data.get('weapon', "пистолет_макарова")
        self.skill_points = data.get('skill_points', 0)

        self.surface_unlocked = bool(data.get('surface_unlocked', False))
        self.varyag_pass_kept = bool(data.get('varyag_pass_kept', False))

        # 0.4.8.7: лояльность независимых торговцев
        tl = data.get('trader_loyalty', {})
        self.trader_loyalty = tl if isinstance(tl, dict) else {}

        self.melee_weapon = data.get('melee_weapon', "кулаки")
        self.melee_weapon_durability = data.get('melee_weapon_durability', 999)

        self.skills = _normalize_skills(data.get('skills'))

        self.armor = data.get('armor', None)
        self.helmet = data.get('helmet', None)
        self.armor_durability = data.get('armor_durability', {}) or {}
        if 'armor' not in self.armor_durability:
            self.armor_durability['armor'] = 0.0
        if 'helmet' not in self.armor_durability:
            self.armor_durability['helmet'] = 0.0
        self.armor_inventory = data.get('armor_inventory', []) or []

        self.radiation = data.get('radiation', 0.0)
        self.chemical = data.get('chemical', 0.0)
        self.diseases = data.get('diseases', []) or []

        self.cold = data.get('cold', 0.0)
        self.shell_ammo = data.get('shell_ammo', {}) or {}

        gren = data.get('grenades_inventory', {})
        self.grenades_inventory = gren if isinstance(gren, dict) else {}
        knives = data.get('throwing_knives_inventory', {})
        self.throwing_knives_inventory = knives if isinstance(knives, dict) else {}

        burn = data.get('is_burning', [])
        self.is_burning = burn if isinstance(burn, list) else []
        self.mg_reload_progress = data.get('mg_reload_progress', 0)

        bleeding = data.get('bleeding_stacks', [])
        self.bleeding_stacks = bleeding if isinstance(bleeding, list) else []
        self.cold_transition_counter = data.get('cold_transition_counter', 0)
        self.cold_sickness_transitions = data.get('cold_sickness_transitions', 0)
        self.blood_infection_soft_transitions = data.get('blood_infection_soft_transitions', 0)

        self.faction = data.get('faction', 'loners') or 'loners'
        relations = data.get('faction_relations', {})
        self.faction_relations = relations if isinstance(relations, dict) else {}
        loyalty = data.get('faction_loyalty', {})
        self.faction_loyalty = loyalty if isinstance(loyalty, dict) else {}

        tasks = data.get('active_tasks', [])
        self.active_tasks = tasks if isinstance(tasks, list) else []

        self.body_parts = data.get('body_parts', {})
        if not self.body_parts:
            self._init_body_parts()
        else:
            self._recalc_body_parts_max_hp_silent()

        self.inventory = data.get('inventory', {
            "аптечка_аи2": 0,
            "патроны": BALANCE['player']['start_ammo'],
            "никели": BALANCE['player']['start_gold'],
            "еда": BALANCE['player']['start_food'],
            "крысы": 0,
            "хлам": [],
            "фильтры": 0,
            "антирад": 0,
            "мед_подсумок": 0,
        })

        self.gas_mask = data.get('gas_mask', {
            "состояние": "поношенный",
            "прочность": BALANCE['gas_mask']['worn_durability'],
            "фильтры": 1,
            "надет": False,
            "фильтр_вставлен": False,
            "фильтр_прочность": 0.0,
            "max_durability": BALANCE['gas_mask']['max_durability'],
        })

        self.magazines = data.get('magazines', [])
        self.equipped_magazine = data.get('equipped_magazine', None)
        self.next_magazine_uid = data.get('next_magazine_uid', 1)

        if self.magazines and isinstance(self.magazines[0], str):
            self._migrate_old_magazines(data.get('ammo_inventory', {}))

        self.equipped_filter = data.get('equipped_filter', None)
        self.filters = data.get('filters', [])
        self.food_inventory = data.get('food_inventory', [])
        self.station_defense = data.get('station_defense', 0)
        self.combat_mode = data.get('combat_mode', False)
        self.combat_target = data.get('combat_target', None)

        self.equipped_modules = data.get('equipped_modules', {"scope": None, "grip": None, "muzzle": None})
        self.modules_inventory = data.get('modules_inventory', [])
        self.weapons_inventory = data.get('weapons_inventory', [])
        self.melee_inventory = data.get('melee_inventory', [])

        if not self.filters:
            self.filters = ["поношенный"]

        self.buffs = data.get('buffs', [])
        self.debuffs = data.get('debuffs', [])
        self.is_new = False

        if not self.magazines and not self.equipped_magazine and not self._has_shell_weapon():
            self._give_starting_magazines()

        self._apply_gas_mask_bonus()
        self.recalc_max_stamina()

        self._migrate_old_ammo_keys()
        self._init_faction_fields()

        self.origin = data.get('origin', '') or ''
        self.prologue_completed = bool(data.get('prologue_completed', False))

        logger.debug(f"Игрок {self.name} (id={self.user_id}) загружен из БД")

    def _migrate_old_ammo_keys(self):
        try:
            from config.map_config import AMMO
        except Exception:
            return

        ammo_types = AMMO.get('ammo_types', {})
        calibers = AMMO.get('calibers', {})

        for ammo_type in list(self.inventory.keys()):
            if "|" in ammo_type:
                continue
            if ammo_type not in ammo_types:
                continue

            count = self.inventory.get(ammo_type, 0)
            if not isinstance(count, int) or count <= 0:
                continue

            target_caliber = None
            for cal_id, cal_data in calibers.items():
                if ammo_type in cal_data.get('types', []):
                    target_caliber = cal_id
                    break

            if not target_caliber:
                continue

            new_key = f"{target_caliber}|{ammo_type}"
            self.inventory[new_key] = self.inventory.get(new_key, 0) + count
            del self.inventory[ammo_type]
            logger.info(
                f"{self.name}: миграция патронов '{ammo_type}' ×{count} → '{new_key}'"
            )

    def _init_new_player(self, name: str):
        self.name = name
        self.backstory = "Без предыстории"
        self.level = 1
        self.xp = 0
        self.xp_to_next = 10
        self.stamina = BALANCE['player']['base_stamina']
        self.max_stamina = BALANCE['player']['base_stamina']
        self.location = "бульвар_дмитрия_донского"
        self.is_alive = True
        self.weapon = "пистолет_макарова"
        self.skill_points = BALANCE['skills']['start_points']

        self.melee_weapon = "кулаки"
        self.melee_weapon_durability = 999
        self._init_body_parts()

        self.inventory = {
            "аптечка_аи2": 0,
            "патроны": BALANCE['player']['start_ammo'],
            "никели": BALANCE['player']['start_gold'],
            "еда": BALANCE['player']['start_food'],
            "крысы": 0,
            "хлам": [],
            "фильтры": 0,
            "антирад": 0,
            "мед_подсумок": 0,
        }

        self.gas_mask = {
            "состояние": "поношенный",
            "прочность": BALANCE['gas_mask']['worn_durability'],
            "фильтры": 1,
            "надет": False,
            "фильтр_вставлен": False,
            "фильтр_прочность": 0.0,
            "max_durability": BALANCE['gas_mask']['max_durability'],
        }

        self.equipped_filter = None
        self.filters = ["поношенный"]
        self.food_inventory = []
        self.station_defense = 0
        self.combat_mode = False
        self.combat_target = None

        self.equipped_modules = {"scope": None, "grip": None, "muzzle": None}
        self.modules_inventory = []
        self.weapons_inventory = []
        self.melee_inventory = []

        self.buffs = []
        self.debuffs = []
        self.is_new = True

        self.armor = "броня_доходяги"
        self.helmet = "шапка_доходяги"
        self.armor_durability = {"armor": 100.0, "helmet": 100.0}
        self.armor_inventory = []

        self._give_starting_magazines()
        self._apply_gas_mask_bonus()
        self.recalc_max_stamina()

        self._init_faction_fields()

        self.origin = ''
        self.prologue_completed = False

        self.active_tasks = []

        # 0.4.8.7
        self.trader_loyalty = {}

        logger.info(f"Создан новый игрок {self.name} (id={self.user_id})")