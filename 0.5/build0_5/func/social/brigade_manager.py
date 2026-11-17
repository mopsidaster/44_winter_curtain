# -*- coding: utf-8 -*-
# func/social/brigade_manager.py - Singleton менеджер групп (0.4.8.8)
#
# ИСТОРИЯ:
#   0.4.6   — новый файл.
#   0.4.6.1 — fix: joined_at корректно парсится (см. brigade.py)
#   0.4.8.8 — Бригада привязана к фракции лидера.
#             При загрузке из БД: если колонки faction_id нет —
#             восстанавливаем из фракции лидера.

import asyncio
import time
import uuid
from typing import Dict, Optional

from database.db import get_db
from utils.logger import get_logger

from .brigade import (
    Brigade, STATE_ACTIVE, STATE_NO_ACTIVE, MAX_BRIGADE_SIZE,
    _parse_datetime,
)

logger = get_logger()

INVITE_TIMEOUT_SECONDS = 60


class BrigadeInvite:
    def __init__(self, brigade_id: str, inviter_id: int, invitee_id: int):
        self.invite_id = uuid.uuid4().hex[:12]
        self.brigade_id = brigade_id
        self.inviter_id = inviter_id
        self.invitee_id = invitee_id
        self.created_at = time.time()
        self.resolved = False

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > INVITE_TIMEOUT_SECONDS


class BrigadeManager:
    def __init__(self):
        self.brigades: Dict[str, Brigade] = {}
        self.user_brigade: Dict[int, str] = {}
        self.invites: Dict[str, BrigadeInvite] = {}

    # ==================== ЗАГРУЗКА ИЗ БД ====================

    async def load_all(self):
        try:
            db = await get_db()

            # Проверяем, есть ли колонка faction_id
            has_faction_col = False
            try:
                async with db.execute("PRAGMA table_info(brigades)") as cursor:
                    cols = await cursor.fetchall()
                    col_names = [c[1] for c in cols]
                    has_faction_col = "faction_id" in col_names
                    if not has_faction_col:
                        try:
                            await db.execute(
                                "ALTER TABLE brigades ADD COLUMN faction_id TEXT DEFAULT 'loners'"
                            )
                            await db.commit()
                            has_faction_col = True
                            logger.info("[Brigade] Добавлена колонка faction_id")
                        except Exception as e:
                            logger.error(f"[Brigade] ALTER faction_id: {e}")
            except Exception as e:
                logger.error(f"[Brigade] PRAGMA: {e}")

            async with db.execute("SELECT * FROM brigades") as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    brigade_id = row["brigade_id"]
                    faction_id = "loners"
                    if has_faction_col:
                        try:
                            faction_id = row["faction_id"] or "loners"
                        except (KeyError, IndexError):
                            faction_id = "loners"

                    brigade = Brigade(
                        brigade_id=brigade_id,
                        name=row["name"],
                        description=row["description"] or "",
                        leader_id=row["leader_id"],
                        state=row["state"] or STATE_ACTIVE,
                        created_at=_parse_datetime(row["created_at"]),
                        faction_id=faction_id,
                    )
                    self.brigades[brigade_id] = brigade

            async with db.execute(
                    "SELECT brigade_id, user_id, joined_at FROM brigade_members ORDER BY joined_at"
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    b_id = row["brigade_id"]
                    u_id = row["user_id"]
                    if b_id in self.brigades:
                        self.brigades[b_id].add_member(
                            u_id, joined_at=_parse_datetime(row["joined_at"])
                        )
                        self.user_brigade[u_id] = b_id

            # 0.4.8.8: восстановление фракции из лидера (если в БД пусто)
            try:
                from ...game_manager import game_manager
                for b in self.brigades.values():
                    if b.faction_id == "loners":
                        leader = game_manager.get_player(b.leader_id)
                        if leader:
                            fid = leader.get_faction()
                            if fid and fid != "loners":
                                b.faction_id = fid
            except Exception as e:
                logger.error(f"[Brigade] restore faction: {e}")

            logger.info(f"[Brigade] Загружено групп: {len(self.brigades)}")
        except Exception as e:
            logger.error(f"[Brigade] Ошибка загрузки: {e}")

    # ==================== СОЗДАНИЕ / УДАЛЕНИЕ ====================

    async def create_brigade(self, leader_id: int, name: str,
                             description: str,
                             faction_id: str = "loners") -> Brigade:
        brigade_id = uuid.uuid4().hex[:12]
        brigade = Brigade(
            brigade_id, name, description, leader_id,
            faction_id=faction_id,
        )
        brigade.add_member(leader_id)

        self.brigades[brigade_id] = brigade
        self.user_brigade[leader_id] = brigade_id

        try:
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO brigades "
                    "(brigade_id, name, description, leader_id, state, faction_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (brigade_id, name, description, leader_id,
                     STATE_ACTIVE, faction_id),
                )
            except Exception:
                # fallback — старая схема без faction_id
                await db.execute(
                    "INSERT INTO brigades "
                    "(brigade_id, name, description, leader_id, state) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (brigade_id, name, description, leader_id, STATE_ACTIVE),
                )
            await db.execute(
                "INSERT INTO brigade_members (brigade_id, user_id) VALUES (?, ?)",
                (brigade_id, leader_id),
            )
            await db.commit()
        except Exception as e:
            logger.error(f"[Brigade] Ошибка создания в БД: {e}")

        logger.info(
            f"[Brigade] Создана группа {name} ({brigade_id}) "
            f"лидером {leader_id}, фракция {faction_id}"
        )
        return brigade

    async def disband_brigade(self, brigade_id: str) -> bool:
        brigade = self.brigades.get(brigade_id)
        if not brigade:
            return False

        for uid in brigade.get_member_ids():
            self.user_brigade.pop(uid, None)

        del self.brigades[brigade_id]

        try:
            db = await get_db()
            await db.execute("DELETE FROM brigades WHERE brigade_id = ?", (brigade_id,))
            await db.execute("DELETE FROM brigade_members WHERE brigade_id = ?", (brigade_id,))
            await db.execute("DELETE FROM brigade_invites WHERE brigade_id = ?", (brigade_id,))
            await db.commit()
        except Exception as e:
            logger.error(f"[Brigade] Ошибка удаления в БД: {e}")

        logger.info(f"[Brigade] Группа {brigade_id} распущена")
        return True

    # ==================== ДОБАВЛЕНИЕ / УДАЛЕНИЕ ====================

    async def add_member(self, brigade_id: str, user_id: int) -> bool:
        brigade = self.brigades.get(brigade_id)
        if not brigade or brigade.is_full() or brigade.has_member(user_id):
            return False

        if not brigade.add_member(user_id):
            return False
        self.user_brigade[user_id] = brigade_id

        try:
            db = await get_db()
            await db.execute(
                "INSERT INTO brigade_members (brigade_id, user_id) VALUES (?, ?)",
                (brigade_id, user_id),
            )
            await db.commit()
        except Exception as e:
            logger.error(f"[Brigade] Ошибка добавления участника: {e}")

        logger.info(f"[Brigade] {user_id} вступил в {brigade_id}")
        return True

    async def remove_member(self, brigade_id: str, user_id: int) -> bool:
        brigade = self.brigades.get(brigade_id)
        if not brigade or not brigade.has_member(user_id):
            return False

        brigade.remove_member(user_id)
        self.user_brigade.pop(user_id, None)

        try:
            db = await get_db()
            await db.execute(
                "DELETE FROM brigade_members WHERE brigade_id = ? AND user_id = ?",
                (brigade_id, user_id),
            )
            await db.commit()
        except Exception as e:
            logger.error(f"[Brigade] Ошибка удаления участника: {e}")

        logger.info(f"[Brigade] {user_id} покинул {brigade_id}")
        return True

    async def handle_leader_left(self, brigade_id: str) -> Optional[int]:
        brigade = self.brigades.get(brigade_id)
        if not brigade:
            return None

        if not brigade.members:
            await self.disband_brigade(brigade_id)
            return None

        new_leader = brigade.choose_new_leader()
        if not new_leader:
            await self.disband_brigade(brigade_id)
            return None

        brigade.leader_id = new_leader
        brigade.set_state(STATE_NO_ACTIVE)

        # 0.4.8.8: обновляем фракцию по новому лидеру
        try:
            from ...game_manager import game_manager
            leader = game_manager.get_player(new_leader)
            if leader:
                brigade.faction_id = leader.get_faction()
        except Exception:
            pass

        try:
            db = await get_db()
            await db.execute(
                "UPDATE brigades SET leader_id = ?, state = ?, faction_id = ? "
                "WHERE brigade_id = ?",
                (new_leader, STATE_NO_ACTIVE, brigade.faction_id, brigade_id),
            )
            await db.commit()
        except Exception as e:
            logger.error(f"[Brigade] Ошибка смены лидера в БД: {e}")

        logger.info(f"[Brigade] В {brigade_id} новый лидер: {new_leader}")
        return new_leader

    # ==================== СОСТОЯНИЕ ====================

    async def set_state(self, brigade_id: str, state: str) -> bool:
        brigade = self.brigades.get(brigade_id)
        if not brigade:
            return False

        brigade.set_state(state)

        try:
            db = await get_db()
            await db.execute(
                "UPDATE brigades SET state = ? WHERE brigade_id = ?",
                (state, brigade_id),
            )
            await db.commit()
        except Exception as e:
            logger.error(f"[Brigade] Ошибка смены состояния: {e}")

        logger.info(f"[Brigade] {brigade_id} → {state}")
        return True

    # ==================== ПОИСК ====================

    def get_brigade(self, brigade_id: str) -> Optional[Brigade]:
        return self.brigades.get(brigade_id)

    def get_user_brigade(self, user_id: int) -> Optional[Brigade]:
        b_id = self.user_brigade.get(user_id)
        if not b_id:
            return None
        return self.brigades.get(b_id)

    def is_user_in_brigade(self, user_id: int) -> bool:
        return user_id in self.user_brigade

    def get_all_brigades(self) -> list[Brigade]:
        return list(self.brigades.values())

    # ==================== ПРИГЛАШЕНИЯ ====================

    def create_invite(self, brigade_id: str, inviter_id: int,
                      invitee_id: int) -> Optional[BrigadeInvite]:
        self._cleanup_expired_invites()

        for inv in self.invites.values():
            if (inv.brigade_id == brigade_id
                    and inv.invitee_id == invitee_id
                    and not inv.resolved):
                return inv

        inv = BrigadeInvite(brigade_id, inviter_id, invitee_id)
        self.invites[inv.invite_id] = inv
        logger.info(
            f"[Brigade] Приглашение {inv.invite_id}: "
            f"{inviter_id} → {invitee_id} в {brigade_id}"
        )
        return inv

    def get_invite(self, invite_id: str) -> Optional[BrigadeInvite]:
        inv = self.invites.get(invite_id)
        if inv and inv.is_expired():
            inv.resolved = True
            return None
        return inv

    def resolve_invite(self, invite_id: str):
        inv = self.invites.get(invite_id)
        if inv:
            inv.resolved = True

    def _cleanup_expired_invites(self):
        for inv_id in list(self.invites.keys()):
            inv = self.invites[inv_id]
            if inv.resolved or inv.is_expired():
                del self.invites[inv_id]


brigade_manager = BrigadeManager()