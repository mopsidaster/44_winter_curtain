# -*- coding: utf-8 -*-
# func/social/brigade.py - Модель группы (0.4.8.8)
#
# ИСТОРИЯ:
#   0.4.6   — новый файл.
#   0.4.6.1 — fix: joined_at всегда datetime (парсинг строк из SQLite)
#   0.4.8.8 — Бригада привязана к фракции лидера (faction_id).

import uuid
from datetime import datetime, timezone
from typing import Optional, Union


MAX_BRIGADE_SIZE = 3

STATE_ACTIVE = "active"
STATE_NO_ACTIVE = "no_active"


def _parse_datetime(value) -> datetime:
    """
    Привести значение из БД/кода к datetime.
    Поддерживает:
      • datetime → как есть
      • ISO-строка 'YYYY-MM-DD HH:MM:SS' или 'YYYY-MM-DDTHH:MM:SS'
      • None → now()
    """
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            pass
    return datetime.now()


class BrigadeMember:
    def __init__(self, user_id: int, joined_at: Union[datetime, str, None] = None):
        self.user_id = user_id
        self.joined_at = _parse_datetime(joined_at)


class Brigade:
    def __init__(self, brigade_id: str, name: str, description: str,
                 leader_id: int, state: str = STATE_ACTIVE,
                 created_at: Union[datetime, str, None] = None,
                 faction_id: str = "loners"):
        self.brigade_id = brigade_id
        self.name = name
        self.description = description or ""
        self.leader_id = leader_id
        self.state = state
        self.created_at = _parse_datetime(created_at)
        self.members: list[BrigadeMember] = []
        # 0.4.8.8: фракция бригады = фракция лидера
        self.faction_id = faction_id or "loners"

    # ==================== УЧАСТНИКИ ====================

    def get_member_ids(self) -> list[int]:
        return [m.user_id for m in self.members]

    def has_member(self, user_id: int) -> bool:
        return any(m.user_id == user_id for m in self.members)

    def is_leader(self, user_id: int) -> bool:
        return user_id == self.leader_id

    def is_full(self) -> bool:
        return len(self.members) >= MAX_BRIGADE_SIZE

    def member_count(self) -> int:
        return len(self.members)

    def add_member(self, user_id: int,
                   joined_at: Union[datetime, str, None] = None) -> bool:
        if self.has_member(user_id):
            return False
        if self.is_full():
            return False
        self.members.append(BrigadeMember(user_id, joined_at))
        return True

    def remove_member(self, user_id: int) -> bool:
        for i, m in enumerate(self.members):
            if m.user_id == user_id:
                del self.members[i]
                return True
        return False

    # ==================== ЛИДЕР ====================

    def choose_new_leader(self) -> Optional[int]:
        """Выбрать нового лидера — самого раннего по joined_at."""
        if not self.members:
            return None
        sorted_members = sorted(self.members, key=lambda m: m.joined_at)
        return sorted_members[0].user_id

    # ==================== СОСТОЯНИЕ ====================

    def set_state(self, state: str):
        if state in (STATE_ACTIVE, STATE_NO_ACTIVE):
            self.state = state

    def is_active(self) -> bool:
        return self.state == STATE_ACTIVE

    def is_no_active(self) -> bool:
        return self.state == STATE_NO_ACTIVE