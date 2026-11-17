# server/api.py
import sys
import os
import asyncio
import threading
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# Импорт всех конфигов и модулей
from config.map_config import MAP_DATA
from func.game_manager import game_manager
from func.combat import combat_manager
from func.player import Player
from database.db import get_all_players, save_player
from func.station_utils import is_trade_station
from func.factions import get_npcs_on_station, get_npc_data
from func.views.faction_npc.dialog_trees import DIALOG_TREES

loop = asyncio.new_event_loop()
def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()
threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

async def init_players():
    try:
        players_data = await get_all_players()
        for data in players_data:
            p = Player(data['user_id'], data.get('username', 'Unknown'), data.get('name', 'Stalker'), data)
            game_manager.players[p.user_id] = p
    except Exception as e:
        print(f"[API] Ошибка: {e}")

asyncio.run_coroutine_threadsafe(init_players(), loop)

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

def get_or_create_player(user_data):
    user_id = user_data.get('user_id', 1)
    player = game_manager.get_player(user_id)
    if not player:
        player = Player(user_id, user_data.get('username', 'Unknown'), user_data.get('name', 'Stalker'), user_data)
        player.location = "бульвар_дмитрия_донского"
        game_manager.players[user_id] = player
    if player.location not in MAP_DATA["станции"]:
        player.location = "бульвар_дмитрия_донского"
    return player

# === 1. ГЛАВНОЕ МЕНЮ (Все кнопки) ===
def api_get_main_menu(user_data):
    player = get_or_create_player(user_data)
    location = player.location
    st_data = MAP_DATA["станции"].get(location, {})

    # Определяем, какие кнопки показывать (как в MainMenu из bot)
    npcs = get_npcs_on_station(location)
    is_trade = is_trade_station(location)

    menu = {
        "player_name": player.name,
        "location": st_data.get("name", location),
        "danger": st_data.get("danger", 0),
        "hp": player.get_total_health(),
        "max_hp": player.get_max_total_health(),
        "money": player.inventory.get('никели', 0),
        "weapon": player.weapon,
        "buttons": {
            "actions": True,
            "inventory": True,
            "move": True,
            "map": True,
            "status": True,
            "faction": True,
            "npc": len(npcs) > 0,
            "trade": is_trade
        }
    }
    return {"status": "ok", "menu": menu}

# === 2. ДЕЙСТВИЯ И ПЕРЕМЕЩЕНИЕ ===
def api_get_connections(user_data):
    player = get_or_create_player(user_data)
    connections = MAP_DATA["станции"].get(player.location, {}).get("connections", [])
    stations = [{"id": c, "name": MAP_DATA["станции"].get(c, {}).get("name", c), "danger": MAP_DATA["станции"].get(c, {}).get("danger", 0)} for c in connections]
    return {"status": "ok", "current_location": player.location, "stations": stations}

def api_move_player(user_data, destination):
    player = get_or_create_player(user_data)
    try:
        result = run_async(game_manager.move_player(player.user_id, destination, None))
        run_async(save_player(player))
        return {"status": "ok", "message": result, "player_hp": player.get_total_health(), "new_location": player.location}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# === 3. NPC И ДИАЛОГИ ===
def api_get_npcs(user_data):
    player = get_or_create_player(user_data)
    npcs = get_npcs_on_station(player.location)
    return {"status": "ok", "npcs": npcs}

def api_get_dialog(user_data, npc_id, node_id):
    try:
        npc = get_npc_data(npc_id)
        tree = DIALOG_TREES.get(npc.get("dialog_tree"), {})
        if not tree: return {"status": "ok", "speaker": npc.get("name"), "text": "Нет диалога", "options": []}

        if not node_id: node_id = tree.get("root", "greeting")
        node = tree.get("nodes", {}).get(node_id, {})

        text = node.get("text", "...")
        options = [{"label": o.get("label"), "next": o.get("next"), "action": o.get("action")} for o in node.get("options", [])]

        return {"status": "ok", "speaker": node.get("speaker", npc.get("name")), "text": text, "options": options}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# === 4. ОСТАЛЬНОЕ ===
def api_create_character(user_data, name, backstory, origin, skills):
    player = get_or_create_player(user_data)
    player.name = name
    player.backstory = backstory
    player.origin = origin
    player.skills = skills
    player.prologue_completed = True
    player.recalc_body_parts_max_hp()
    player.recalc_max_stamina()
    player.restore_full_health()
    run_async(save_player(player))
    return {"status": "ok"}

def api_start_combat(user_data, enemy_id="упырь"):
    player = get_or_create_player(user_data)
    try:
        combat = combat_manager.start_combat(player, danger_level=3, channel=None, forced_enemy_ids=[enemy_id])
        return {"status": "ok", "enemy_name": combat.enemy.display_name, "enemy_hp": combat.enemy.lives, "enemy_max_hp": combat.enemy.max_lives, "distance": combat.distance, "player_hp": player.get_total_health()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def api_combat_action(user_data, action, part=None):
    player = get_or_create_player(user_data)
    combat = combat_manager.get_combat(player.user_id)
    if not combat: return {"status": "error", "message": "Нет боя"}
    result = None
    if action == "shoot": result = combat.player_shoot(part, actor_user_id=player.user_id)
    elif action == "heal": result = combat.player_heal_in_combat("аптечка_аи2", actor_user_id=player.user_id)
    elif action == "reload": result = combat.player_reload(actor_user_id=player.user_id)
    elif action == "defend": result = combat.player_defend(actor_user_id=player.user_id)
    elif action == "retreat": result = combat.player_retreat(actor_user_id=player.user_id)

    msg = result.get("message", "") if result else "Ошибка"
    if result and result.get("turn_ended") and combat.is_active:
        for er in combat.enemy_turn(): msg += f"\n{er['message']}"
    return {"status": "ok", "message": msg, "enemy_hp": combat.enemy.lives if combat.enemy else 0, "player_hp": player.get_total_health(), "is_over": not combat.is_active or combat.all_enemies_dead()}