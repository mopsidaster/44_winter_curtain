# -*- coding: utf-8 -*-
# func/combat/pvp_manager.py - Singleton PvP-боёв (0.4.6)
#
# ИСТОРИЯ:
#   0.4.6   — новый файл.
#   0.4.6.1 — поддержка команд (register_combat регистрирует всех участников),
#             is_user_in_combat

import asyncio
import time
import uuid
from typing import Dict, Optional

import discord

from utils.logger import get_logger

logger = get_logger()

INVITE_TIMEOUT_SECONDS = 60


class PvPInvite:
    """Одно активное приглашение на PvP."""

    def __init__(self, initiator_id: int, target_id: int, channel_id: int):
        self.invite_id = uuid.uuid4().hex[:12]
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.channel_id = channel_id
        self.created_at = time.time()
        self.resolved = False

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > INVITE_TIMEOUT_SECONDS


class PvPManager:
    """Singleton для PvP-приглашений и боёв."""

    def __init__(self):
        self.invites: Dict[str, PvPInvite] = {}
        self.combats: Dict[str, "PvPCombat"] = {}
        self.user_combat_map: Dict[int, str] = {}

    # ==================== ПРИГЛАШЕНИЯ ====================

    def create_invite(self, initiator_id: int, target_id: int,
                      channel_id: int) -> PvPInvite:
        self._cleanup_expired_invites()

        for inv in self.invites.values():
            if inv.initiator_id == initiator_id and inv.target_id == target_id \
                    and not inv.resolved:
                return inv

        inv = PvPInvite(initiator_id, target_id, channel_id)
        self.invites[inv.invite_id] = inv
        logger.info(
            f"[PvP] Создано приглашение {inv.invite_id}: "
            f"{initiator_id} → {target_id}"
        )
        return inv

    def get_invite(self, invite_id: str) -> Optional[PvPInvite]:
        inv = self.invites.get(invite_id)
        if inv and inv.is_expired():
            inv.resolved = True
            return None
        return inv

    def resolve_invite(self, invite_id: str) -> bool:
        inv = self.invites.get(invite_id)
        if not inv:
            return False
        inv.resolved = True
        return True

    def cancel_invites_by_user(self, user_id: int) -> list:
        cancelled = []
        for inv in self.invites.values():
            if inv.resolved:
                continue
            if inv.initiator_id == user_id or inv.target_id == user_id:
                inv.resolved = True
                cancelled.append(inv)
        return cancelled

    def _cleanup_expired_invites(self):
        for inv_id in list(self.invites.keys()):
            inv = self.invites[inv_id]
            if inv.resolved or inv.is_expired():
                del self.invites[inv_id]

    # ==================== БОИ ====================

    def register_combat(self, combat: "PvPCombat") -> str:
        combat_id = combat.combat_id
        self.combats[combat_id] = combat

        # 0.4.6.1: регистрируем всех участников обеих команд
        for c in combat.turn_order:
            self.user_combat_map[c.user_id] = combat_id

        logger.info(
            f"[PvP] Зарегистрирован бой {combat_id}: "
            f"A={[c.display_name for c in combat.team_a]} vs "
            f"B={[c.display_name for c in combat.team_b]}"
        )
        return combat_id

    def get_combat_by_user(self, user_id: int) -> Optional["PvPCombat"]:
        combat_id = self.user_combat_map.get(user_id)
        if not combat_id:
            return None
        return self.combats.get(combat_id)

    def is_user_in_combat(self, user_id: int) -> bool:
        """0.4.6: используется в move_mixin, combat_start_mixin, /fight."""
        return user_id in self.user_combat_map

    def get_combat(self, combat_id: str) -> Optional["PvPCombat"]:
        return self.combats.get(combat_id)

    def end_combat(self, combat_id: str):
        combat = self.combats.get(combat_id)
        if not combat:
            return
        # Снимаем маппинг со всех участников
        for c in combat.turn_order:
            self.user_combat_map.pop(c.user_id, None)
        del self.combats[combat_id]
        logger.info(f"[PvP] Бой {combat_id} завершён")


# Singleton
pvp_manager = PvPManager()