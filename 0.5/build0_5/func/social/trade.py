# -*- coding: utf-8 -*-
# func/social/trade.py - Логика обмена (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.6   — новый файл.
#   0.4.7.2 — уточнена валидация новых типов из item_picker;
#             корректный перенос магазина (сохранение ammo).

from typing import List, Tuple
from utils.logger import get_logger

logger = get_logger()


# ==================== ПРОВЕРКИ ====================

def player_has_money(player, amount: int) -> bool:
    return player.inventory.get('никели', 0) >= amount


def validate_offer_items(player, items: List[dict]) -> Tuple[bool, str]:
    """
    Проверить, что у игрока есть все предметы из списка.
    Возвращает (ok, reason).
    """
    inventory_needs: dict[str, int] = {}
    for item in items:
        t = item.get("type")
        if t == "inventory_key":
            k = item["key"]
            inventory_needs[k] = inventory_needs.get(k, 0) + item.get("count", 1)

    for k, need in inventory_needs.items():
        have = player.inventory.get(k, 0)
        if have < need:
            return False, f"Не хватает «{k}»: нужно {need}, есть {have}"

    for item in items:
        t = item.get("type")
        if t == "weapon":
            if item["id"] not in player.weapons_inventory:
                return False, f"Нет оружия «{item['id']}» в инвентаре"
            if item["id"] == player.weapon:
                return False, "Нельзя передать используемое оружие"
        elif t == "melee":
            if item["id"] not in player.melee_inventory:
                return False, f"Нет оружия ближнего боя «{item['id']}»"
            if item["id"] == player.melee_weapon:
                return False, "Нельзя передать используемое оружие ближнего боя"
        elif t == "armor":
            if item["id"] not in player.armor_inventory:
                return False, f"Нет брони «{item['id']}»"
            if item["id"] in (player.armor, player.helmet):
                return False, "Нельзя передать надетый предмет"
        elif t == "module":
            if item["id"] not in player.modules_inventory:
                return False, f"Нет модуля «{item['id']}»"
        elif t == "magazine":
            mag = player.get_magazine_obj(item["uid"])
            if not mag:
                return False, f"Нет магазина `{item['uid']}`"
            if mag.get("installed"):
                return False, "Нельзя передать установленный магазин"
        elif t == "grenade":
            if player.get_grenade_count(item["id"]) < item.get("count", 1):
                return False, f"Нет гранат «{item['id']}»"
        elif t == "knife":
            if player.get_knife_count(item["id"]) < item.get("count", 1):
                return False, f"Нет ножей «{item['id']}»"
        elif t == "food":
            need = item.get("count", 1)
            if player.food_inventory.count(item["id"]) < need:
                return False, f"Нет еды «{item['id']}»: нужно {need}"
        elif t == "filter":
            need = item.get("count", 1)
            if player.filters.count(item["id"]) < need:
                return False, f"Нет фильтров «{item['id']}»: нужно {need}"

    return True, "OK"


# ==================== ПРИМЕНЕНИЕ ====================

def _give_item(receiver, item: dict):
    t = item.get("type")
    if t == "inventory_key":
        k = item["key"]
        cnt = item.get("count", 1)
        receiver.inventory[k] = receiver.inventory.get(k, 0) + cnt
    elif t == "weapon":
        if item["id"] not in receiver.weapons_inventory:
            receiver.weapons_inventory.append(item["id"])
    elif t == "melee":
        if item["id"] not in receiver.melee_inventory:
            receiver.melee_inventory.append(item["id"])
    elif t == "armor":
        if item["id"] not in receiver.armor_inventory:
            receiver.armor_inventory.append(item["id"])
    elif t == "module":
        if item["id"] not in receiver.modules_inventory:
            receiver.modules_inventory.append(item["id"])
    elif t == "magazine":
        # Магазин обрабатывается отдельно через _transfer_magazine.
        pass
    elif t == "grenade":
        receiver.add_grenade(item["id"], item.get("count", 1))
    elif t == "knife":
        receiver.add_knife(item["id"], item.get("count", 1))
    elif t == "food":
        for _ in range(item.get("count", 1)):
            receiver.food_inventory.append(item["id"])
    elif t == "filter":
        for _ in range(item.get("count", 1)):
            receiver.filters.append(item["id"])


def _take_item(player, item: dict):
    t = item.get("type")
    if t == "inventory_key":
        k = item["key"]
        cnt = item.get("count", 1)
        player.inventory[k] = max(0, player.inventory.get(k, 0) - cnt)
    elif t == "weapon":
        if item["id"] in player.weapons_inventory:
            player.weapons_inventory.remove(item["id"])
    elif t == "melee":
        if item["id"] in player.melee_inventory:
            player.melee_inventory.remove(item["id"])
    elif t == "armor":
        if item["id"] in player.armor_inventory:
            player.armor_inventory.remove(item["id"])
    elif t == "module":
        if item["id"] in player.modules_inventory:
            player.modules_inventory.remove(item["id"])
    elif t == "magazine":
        player.remove_magazine_instance(item["uid"])
    elif t == "grenade":
        for _ in range(item.get("count", 1)):
            player.consume_grenade(item["id"])
    elif t == "knife":
        for _ in range(item.get("count", 1)):
            player.consume_knife(item["id"])
    elif t == "food":
        for _ in range(item.get("count", 1)):
            if item["id"] in player.food_inventory:
                player.food_inventory.remove(item["id"])
    elif t == "filter":
        for _ in range(item.get("count", 1)):
            if item["id"] in player.filters:
                player.filters.remove(item["id"])


def _transfer_magazine(sender, receiver, uid: str):
    """Особая передача магазина: сохраняем ammo, новый UID у получателя."""
    mag = sender.get_magazine_obj(uid)
    if not mag:
        return
    new_uid = receiver._generate_magazine_uid()
    receiver.magazines.append({
        "uid": new_uid,
        "type_id": mag["type_id"],
        "ammo": dict(mag.get("ammo", {})),
        "installed": False,
        "weapon": None,
    })
    sender.remove_magazine_instance(uid)


def apply_money(sender, receiver, amount: int) -> bool:
    if not player_has_money(sender, amount):
        return False
    sender.inventory['никели'] = sender.inventory.get('никели', 0) - amount
    receiver.inventory['никели'] = receiver.inventory.get('никели', 0) + amount
    return True


def apply_deliver(sender, receiver, items: List[dict]) -> Tuple[bool, str]:
    ok, reason = validate_offer_items(sender, items)
    if not ok:
        return False, reason

    magazines = [it for it in items if it.get("type") == "magazine"]
    other_items = [it for it in items if it.get("type") != "magazine"]

    for it in other_items:
        _take_item(sender, it)
        _give_item(receiver, it)

    for it in magazines:
        _transfer_magazine(sender, receiver, it["uid"])

    return True, "OK"


def apply_trade(trade, initiator_player, receiver_player) -> Tuple[bool, str]:
    if trade.initiator_money > 0 and not player_has_money(initiator_player, trade.initiator_money):
        return False, "У инициатора недостаточно никелей"
    if trade.receiver_money > 0 and not player_has_money(receiver_player, trade.receiver_money):
        return False, "У получателя недостаточно никелей"

    ok, reason = validate_offer_items(initiator_player, trade.initiator_items)
    if not ok:
        return False, f"У инициатора: {reason}"
    ok, reason = validate_offer_items(receiver_player, trade.receiver_items)
    if not ok:
        return False, f"У получателя: {reason}"

    if trade.initiator_money > 0:
        apply_money(initiator_player, receiver_player, trade.initiator_money)
    if trade.receiver_money > 0:
        apply_money(receiver_player, initiator_player, trade.receiver_money)

    init_magazines = [it for it in trade.initiator_items if it.get("type") == "magazine"]
    init_other = [it for it in trade.initiator_items if it.get("type") != "magazine"]
    recv_magazines = [it for it in trade.receiver_items if it.get("type") == "magazine"]
    recv_other = [it for it in trade.receiver_items if it.get("type") != "magazine"]

    for it in init_other:
        _take_item(initiator_player, it)
        _give_item(receiver_player, it)

    for it in recv_other:
        _take_item(receiver_player, it)
        _give_item(initiator_player, it)

    for it in init_magazines:
        _transfer_magazine(initiator_player, receiver_player, it["uid"])

    for it in recv_magazines:
        _transfer_magazine(receiver_player, initiator_player, it["uid"])

    return True, "OK"