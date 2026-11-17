# -*- coding: utf-8 -*-
# func/player/faction_mixin.py - Фракции и торговцы игрока (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.8 — новый файл (фракции).
#   0.4.8.7 — методы для лояльности независимых торговцев.

from utils.logger import get_logger

logger = get_logger()


class FactionMixin:

    # ==================== ИНИЦИАЛИЗАЦИЯ ====================

    def _init_faction_fields(self):
        if not hasattr(self, 'faction') or not self.faction:
            self.faction = "loners"
        if not hasattr(self, 'faction_relations') or not isinstance(self.faction_relations, dict):
            self.faction_relations = {}
        if not hasattr(self, 'faction_loyalty') or not isinstance(self.faction_loyalty, dict):
            self.faction_loyalty = {}
        if not hasattr(self, 'active_tasks') or not isinstance(self.active_tasks, list):
            self.active_tasks = []
        if not hasattr(self, 'surface_unlocked'):
            self.surface_unlocked = False
        # 0.4.8.7
        if not hasattr(self, 'trader_loyalty') or not isinstance(self.trader_loyalty, dict):
            self.trader_loyalty = {}

    def get_active_tasks(self) -> list:
        return list(getattr(self, 'active_tasks', []) or [])

    def add_task(self, task: dict):
        if not hasattr(self, 'active_tasks') or not isinstance(self.active_tasks, list):
            self.active_tasks = []
        self.active_tasks.append(task)

    def remove_task(self, task_id: str) -> bool:
        tasks = getattr(self, 'active_tasks', []) or []
        for i, t in enumerate(tasks):
            if t.get("task_id") == task_id:
                del tasks[i]
                return True
        return False

    # ==================== ФРАКЦИИ ====================

    def get_faction(self) -> str:
        return getattr(self, 'faction', 'loners') or 'loners'

    def is_member_of(self, faction_id: str) -> bool:
        return self.get_faction() == faction_id

    def get_relation_to(self, faction_id: str) -> str:
        from ..factions import get_player_relation_to
        return get_player_relation_to(self, faction_id)

    def get_loyalty(self, faction_id: str) -> int:
        from ..factions import get_player_loyalty
        return get_player_loyalty(self, faction_id)

    def get_loyalty_level(self, faction_id: str) -> int:
        from ..factions import get_player_loyalty_level
        return get_player_loyalty_level(self, faction_id)

    def get_loyalty_progress(self, faction_id: str) -> dict:
        from ..factions import get_loyalty_progress
        return get_loyalty_progress(self, faction_id)

    def add_loyalty(self, faction_id: str, amount: int) -> int:
        from ..factions import add_player_loyalty
        return add_player_loyalty(self, faction_id, amount)

    def can_join_faction(self, faction_id: str) -> tuple:
        from ..factions import can_join_faction
        return can_join_faction(self, faction_id)

    def join_faction(self, faction_id: str) -> tuple:
        from ..factions import join_faction
        return join_faction(self, faction_id)

    def get_faction_summary(self) -> str:
        from ..factions import get_faction_name, get_faction_emoji

        fid = self.get_faction()
        if fid == "loners":
            return f"🧍 {get_faction_name(fid)}"

        return f"{get_faction_emoji(fid)} {get_faction_name(fid)}"

    def get_full_faction_status(self) -> str:
        from ..factions import format_faction_status
        return format_faction_status(self, self.get_faction())

    # ==================== НЕЗАВИСИМЫЕ ТОРГОВЦЫ (0.4.8.7) ====================

    def get_trader_loyalty(self, trader_id: str) -> int:
        from ..independent_traders import get_player_trader_loyalty
        return get_player_trader_loyalty(self, trader_id)

    def get_trader_loyalty_level(self, trader_id: str) -> int:
        from ..independent_traders import get_player_trader_loyalty_level
        return get_player_trader_loyalty_level(self, trader_id)

    def get_trader_loyalty_progress(self, trader_id: str) -> dict:
        from ..independent_traders import get_trader_loyalty_progress
        return get_trader_loyalty_progress(self, trader_id)

    def add_trader_loyalty(self, trader_id: str, amount: int) -> int:
        from ..independent_traders import add_player_trader_loyalty
        return add_player_trader_loyalty(self, trader_id, amount)