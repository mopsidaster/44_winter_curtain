# -*- coding: utf-8 -*-
# func/social/transfer.py - Передача денег и вещей (0.4.6)
#
# ИСТОРИЯ:
#   0.4.6 — новый файл.
#
# Функции:
#   • create_money_transfer — /money
#   • create_deliver        — /deliver
#   • Таймаут 10 минут, состояние в памяти (singleton через transfer_manager).

import time
import uuid
from typing import Optional, List

from utils.logger import get_logger

logger = get_logger()

TRANSFER_TIMEOUT_SECONDS = 600  # 10 минут


# ==================== МОДЕЛИ ====================

class MoneyTransfer:
    def __init__(self, sender_id: int, receiver_id: int, amount: int):
        self.transfer_id = uuid.uuid4().hex[:12]
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.amount = amount
        self.created_at = time.time()
        self.resolved = False

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > TRANSFER_TIMEOUT_SECONDS


class DeliverTransfer:
    def __init__(self, sender_id: int, receiver_id: int, items: List[dict]):
        """
        items — список словарей:
            {"type": "inventory_key", "key": "аптечка_аи2", "count": 1}
            {"type": "weapon", "id": "калаш_74"}
            {"type": "armor", "id": "броня_юг"}
            {"type": "helmet", "id": "шлем_юг"}
            {"type": "melee", "id": "сталкерский_нож"}
            {"type": "module", "id": "оптический_х2"}
            {"type": "magazine", "uid": "mag_5"}
            {"type": "grenade", "id": "ргд_5", "count": 1}
            {"type": "knife", "id": "кустарный_метательный_нож", "count": 1}
            {"type": "food", "id": "мясо_крысы", "count": 1}
            {"type": "filter", "id": "поношенный", "count": 1}
            {"type": "hlam", "id": "хлам"}
        """
        self.transfer_id = uuid.uuid4().hex[:12]
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.items = items
        self.created_at = time.time()
        self.resolved = False

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > TRANSFER_TIMEOUT_SECONDS


class TradeOffer:
    def __init__(self, initiator_id: int, receiver_id: int):
        self.trade_id = uuid.uuid4().hex[:12]
        self.initiator_id = initiator_id
        self.receiver_id = receiver_id
        self.initiator_items: List[dict] = []
        self.receiver_items: List[dict] = []
        self.initiator_money: int = 0
        self.receiver_money: int = 0
        self.created_at = time.time()
        self.resolved = False
        self.confirmed_by_initiator: bool = False
        self.confirmed_by_receiver: bool = False

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > TRANSFER_TIMEOUT_SECONDS


# ==================== МЕНЕДЖЕР ====================

class TransferManager:
    def __init__(self):
        self.money_transfers: dict[str, MoneyTransfer] = {}
        self.deliver_transfers: dict[str, DeliverTransfer] = {}
        self.trade_offers: dict[str, TradeOffer] = {}

    def _cleanup(self):
        for d in (self.money_transfers, self.deliver_transfers, self.trade_offers):
            for k in list(d.keys()):
                if d[k].resolved or d[k].is_expired():
                    del d[k]

    # ==================== MONEY ====================

    def create_money_transfer(self, sender_id: int, receiver_id: int, amount: int) -> MoneyTransfer:
        self._cleanup()
        t = MoneyTransfer(sender_id, receiver_id, amount)
        self.money_transfers[t.transfer_id] = t
        logger.info(f"[Transfer] money: {sender_id} → {receiver_id}, {amount}")
        return t

    def get_money_transfer(self, transfer_id: str) -> Optional[MoneyTransfer]:
        t = self.money_transfers.get(transfer_id)
        if t and t.is_expired():
            t.resolved = True
            return None
        return t

    def resolve_money(self, transfer_id: str):
        t = self.money_transfers.get(transfer_id)
        if t:
            t.resolved = True

    # ==================== DELIVER ====================

    def create_deliver(self, sender_id: int, receiver_id: int, items: List[dict]) -> DeliverTransfer:
        self._cleanup()
        t = DeliverTransfer(sender_id, receiver_id, items)
        self.deliver_transfers[t.transfer_id] = t
        logger.info(f"[Transfer] deliver: {sender_id} → {receiver_id}, {len(items)} предметов")
        return t

    def get_deliver(self, transfer_id: str) -> Optional[DeliverTransfer]:
        t = self.deliver_transfers.get(transfer_id)
        if t and t.is_expired():
            t.resolved = True
            return None
        return t

    def resolve_deliver(self, transfer_id: str):
        t = self.deliver_transfers.get(transfer_id)
        if t:
            t.resolved = True

    # ==================== TRADE ====================

    def create_trade(self, initiator_id: int, receiver_id: int) -> TradeOffer:
        self._cleanup()
        t = TradeOffer(initiator_id, receiver_id)
        self.trade_offers[t.trade_id] = t
        logger.info(f"[Transfer] trade: {initiator_id} ↔ {receiver_id}")
        return t

    def get_trade(self, trade_id: str) -> Optional[TradeOffer]:
        t = self.trade_offers.get(trade_id)
        if t and t.is_expired():
            t.resolved = True
            return None
        return t

    def resolve_trade(self, trade_id: str):
        t = self.trade_offers.get(trade_id)
        if t:
            t.resolved = True

    # ==================== ОТМЕНА ПО ПОЛЬЗОВАТЕЛЮ ====================

    def cancel_all_for_user(self, user_id: int):
        for t in self.money_transfers.values():
            if not t.resolved and (t.sender_id == user_id or t.receiver_id == user_id):
                t.resolved = True
        for t in self.deliver_transfers.values():
            if not t.resolved and (t.sender_id == user_id or t.receiver_id == user_id):
                t.resolved = True
        for t in self.trade_offers.values():
            if not t.resolved and (t.initiator_id == user_id or t.receiver_id == user_id):
                t.resolved = True


transfer_manager = TransferManager()