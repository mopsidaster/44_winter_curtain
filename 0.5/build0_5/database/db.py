# -*- coding: utf-8 -*-
# database/db.py - Работа с SQLite (Билд 0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.8.3 — surface_unlocked
#   0.4.8.6 — varyag_pass_kept
#   0.4.8.7 — trader_loyalty (лояльность независимых торговцев)
#             + переименование id (ублюдок→урод, калаш_74→ак_74,
#             калаш_2012→ак_2012, убойник→дробитель, ашот→иж_17) —
#             для новых сохранений. Вайп старых.

import aiosqlite
import json
import os
import secrets
import string
import traceback
from datetime import datetime, timedelta
from typing import Optional

DB_NAME = "metro.db"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), DB_NAME)

_db_connection: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    global _db_connection
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(DB_PATH)
        _db_connection.row_factory = aiosqlite.Row
        await _db_connection.execute('PRAGMA encoding = "UTF-8"')
        await _db_connection.execute('PRAGMA journal_mode = WAL')
        await _db_connection.execute('PRAGMA synchronous = NORMAL')
        await _db_connection.execute('PRAGMA foreign_keys = ON')
        await _db_connection.commit()
    return _db_connection


async def close_db():
    global _db_connection
    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

async def init_db():
    try:
        db = await get_db()

        async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='players'"
        ) as cursor:
            table_exists = await cursor.fetchone()

        if table_exists:
            async with db.execute("PRAGMA table_info(players)") as cursor:
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]

                new_columns = [
                    ('equipped_magazine', 'TEXT'),
                    ('magazines', 'TEXT'),
                    ('ammo_inventory', 'TEXT'),
                    ('equipped_filter', 'TEXT'),
                    ('filters', 'TEXT'),
                    ('food_inventory', 'TEXT'),
                    ('station_defense', 'INTEGER DEFAULT 0'),
                    ('combat_mode', 'INTEGER DEFAULT 0'),
                    ('combat_target', 'TEXT'),
                    ('melee_weapon', 'TEXT DEFAULT "кулаки"'),
                    ('melee_weapon_durability', 'INTEGER DEFAULT 999'),
                    ('body_parts', 'TEXT'),
                    ('equipped_modules', 'TEXT'),
                    ('modules_inventory', 'TEXT'),
                    ('weapons_inventory', 'TEXT'),
                    ('melee_inventory', 'TEXT'),
                    ('next_magazine_uid', 'INTEGER DEFAULT 1'),
                    ('radiation', 'REAL DEFAULT 0'),
                    ('chemical', 'REAL DEFAULT 0'),
                    ('diseases', 'TEXT'),
                    ('armor_id', 'TEXT'),
                    ('helmet_id', 'TEXT'),
                    ('armor_durability', 'TEXT'),
                    ('armor_inventory', 'TEXT'),
                    ('cold', 'REAL DEFAULT 0'),
                    ('shell_ammo', 'TEXT'),
                    ('grenades_inventory', 'TEXT'),
                    ('throwing_knives_inventory', 'TEXT'),
                    ('is_burning', 'TEXT'),
                    ('mg_reload_progress', 'INTEGER DEFAULT 0'),
                    ('bleeding_stacks', 'TEXT'),
                    ('cold_transition_counter', 'INTEGER DEFAULT 0'),
                    ('cold_sickness_transitions', 'INTEGER DEFAULT 0'),
                    ('blood_infection_soft_transitions', 'INTEGER DEFAULT 0'),
                    ('is_sleeping', 'INTEGER DEFAULT 0'),
                    ('faction', 'TEXT DEFAULT "loners"'),
                    ('faction_relations', 'TEXT'),
                    ('faction_loyalty', 'TEXT'),
                    ('origin', 'TEXT'),
                    ('prologue_completed', 'INTEGER DEFAULT 0'),
                    ('active_tasks', 'TEXT'),
                    ('surface_unlocked', 'INTEGER DEFAULT 0'),
                    ('varyag_pass_kept', 'INTEGER DEFAULT 0'),
                    # 0.4.8.7
                    ('trader_loyalty', 'TEXT'),
                ]

                for col_name, col_type in new_columns:
                    if col_name not in column_names:
                        try:
                            await db.execute(
                                f'ALTER TABLE players ADD COLUMN {col_name} {col_type}'
                            )
                            print(f"[DB] Добавлен столбец {col_name}")
                        except Exception as e:
                            print(f"[DB] Ошибка добавления {col_name}: {e}")

            await db.commit()
        else:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    backstory TEXT,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    xp_to_next INTEGER DEFAULT 10,
                    lives REAL DEFAULT 10.0,
                    stamina REAL DEFAULT 10.0,
                    max_stamina REAL DEFAULT 10.0,
                    location TEXT DEFAULT 'бульвар_дмитрия_донского',
                    is_alive INTEGER DEFAULT 1,
                    weapon TEXT DEFAULT 'пистолет_макарова',
                    armor REAL DEFAULT 0,
                    helmet INTEGER DEFAULT 0,
                    skill_points INTEGER DEFAULT 0,
                    skills TEXT,
                    inventory TEXT,
                    gas_mask TEXT,
                    buffs TEXT,
                    debuffs TEXT,
                    equipped_magazine TEXT,
                    magazines TEXT,
                    ammo_inventory TEXT,
                    equipped_filter TEXT,
                    filters TEXT,
                    food_inventory TEXT,
                    station_defense INTEGER DEFAULT 0,
                    combat_mode INTEGER DEFAULT 0,
                    combat_target TEXT,
                    melee_weapon TEXT DEFAULT 'кулаки',
                    melee_weapon_durability INTEGER DEFAULT 999,
                    body_parts TEXT,
                    equipped_modules TEXT,
                    modules_inventory TEXT,
                    weapons_inventory TEXT,
                    melee_inventory TEXT,
                    next_magazine_uid INTEGER DEFAULT 1,
                    radiation REAL DEFAULT 0,
                    chemical REAL DEFAULT 0,
                    diseases TEXT,
                    armor_id TEXT,
                    helmet_id TEXT,
                    armor_durability TEXT,
                    armor_inventory TEXT,
                    cold REAL DEFAULT 0,
                    shell_ammo TEXT,
                    grenades_inventory TEXT,
                    throwing_knives_inventory TEXT,
                    is_burning TEXT,
                    mg_reload_progress INTEGER DEFAULT 0,
                    bleeding_stacks TEXT,
                    cold_transition_counter INTEGER DEFAULT 0,
                    cold_sickness_transitions INTEGER DEFAULT 0,
                    blood_infection_soft_transitions INTEGER DEFAULT 0,
                    is_sleeping INTEGER DEFAULT 0,
                    faction TEXT DEFAULT 'loners',
                    faction_relations TEXT,
                    faction_loyalty TEXT,
                    origin TEXT,
                    prologue_completed INTEGER DEFAULT 0,
                    active_tasks TEXT,
                    surface_unlocked INTEGER DEFAULT 0,
                    varyag_pass_kept INTEGER DEFAULT 0,
                    trader_loyalty TEXT
                )
            ''')
            await db.commit()
            print("[DB] Таблица players создана")

        # === 0.4.6: таблицы бригад ===
        await db.execute('''
            CREATE TABLE IF NOT EXISTS brigades (
                brigade_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                leader_id INTEGER NOT NULL,
                state TEXT DEFAULT 'active',
                faction_id TEXT DEFAULT 'loners',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS brigade_members (
                brigade_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (brigade_id, user_id),
                FOREIGN KEY (brigade_id) REFERENCES brigades(brigade_id) ON DELETE CASCADE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS brigade_invites (
                invite_id TEXT PRIMARY KEY,
                brigade_id TEXT NOT NULL,
                inviter_id INTEGER NOT NULL,
                invitee_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (brigade_id) REFERENCES brigades(brigade_id) ON DELETE CASCADE
            )
        ''')
        await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_brigade_members_user '
            'ON brigade_members(user_id)'
        )
        await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_brigade_invites_invitee '
            'ON brigade_invites(invitee_id)'
        )
        await db.commit()

        # === 0.4.8.8: миграция brigades — faction_id ===
        async with db.execute("PRAGMA table_info(brigades)") as cursor:
            br_cols = await cursor.fetchall()
            br_col_names = [c[1] for c in br_cols]
            if "faction_id" not in br_col_names:
                try:
                    await db.execute(
                        "ALTER TABLE brigades ADD COLUMN faction_id "
                        "TEXT DEFAULT 'loners'"
                    )
                    await db.commit()
                    print("[DB] Добавлен столбец brigades.faction_id")
                except Exception as e:
                    print(f"[DB] Ошибка добавления brigades.faction_id: {e}")

        # === 0.4.7: ключи доступа ===
        await db.execute('''
            CREATE TABLE IF NOT EXISTS access_keys (
                key TEXT PRIMARY KEY,
                key_type TEXT NOT NULL,
                used_by INTEGER,
                activated_at DATETIME,
                expires_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_keys_used_by ON access_keys(used_by)'
        )
        await db.commit()

        await db.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_logs_user ON logs(user_id)'
        )
        await db.execute(
            'CREATE INDEX IF NOT EXISTS idx_logs_time ON logs(timestamp)'
        )
        await db.commit()

        print(f"[OK] База данных {DB_NAME} инициализирована")

    except Exception as e:
        print(f"[ERROR] Ошибка инициализации БД: {e}")
        traceback.print_exc()
        raise


# ==================== СЕРИАЛИЗАЦИЯ ====================

def _row_to_dict(row: aiosqlite.Row) -> dict:
    def _json(value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default

    d = dict(row)

    mw_durability = d.get('melee_weapon_durability')
    if mw_durability is None:
        mw_durability = 999

    armor_id = d.get('armor_id')
    if not armor_id:
        old_armor = d.get('armor')
        armor_id = old_armor if isinstance(old_armor, str) and old_armor else None

    helmet_id = d.get('helmet_id')
    if not helmet_id:
        old_helmet = d.get('helmet')
        if isinstance(old_helmet, str) and old_helmet and old_helmet not in ('0', '1'):
            helmet_id = old_helmet
        else:
            helmet_id = None

    return {
        'user_id': d.get('user_id'),
        'username': d.get('username') or 'Unknown',
        'name': d.get('name') or 'Безымянный',
        'backstory': d.get('backstory') or "Без предыстории",
        'level': d.get('level') or 1,
        'xp': d.get('xp') or 0,
        'xp_to_next': d.get('xp_to_next') or 10,
        'lives': d.get('lives') or 10.0,
        'stamina': d.get('stamina') or 10.0,
        'max_stamina': d.get('max_stamina') or 10.0,
        'location': d.get('location') or 'бульвар_дмитрия_донского',
        'is_alive': bool(d.get('is_alive', 1)),
        'weapon': d.get('weapon') or 'пистолет_макарова',
        'armor': armor_id,
        'helmet': helmet_id,
        'armor_durability': _json(d.get('armor_durability'), {}),
        'armor_inventory': _json(d.get('armor_inventory'), []),
        'skill_points': d.get('skill_points') or 0,
        'skills': _json(d.get('skills'), {}),
        'inventory': _json(d.get('inventory'), {}),
        'gas_mask': _json(d.get('gas_mask'), {}),
        'buffs': _json(d.get('buffs'), []),
        'debuffs': _json(d.get('debuffs'), []),
        'equipped_magazine': d.get('equipped_magazine'),
        'magazines': _json(d.get('magazines'), []),
        'ammo_inventory': _json(d.get('ammo_inventory'), {}),
        'equipped_filter': d.get('equipped_filter'),
        'filters': _json(d.get('filters'), []),
        'food_inventory': _json(d.get('food_inventory'), []),
        'station_defense': d.get('station_defense') or 0,
        'combat_mode': bool(d.get('combat_mode', 0)),
        'combat_target': d.get('combat_target'),
        'melee_weapon': d.get('melee_weapon') or "кулаки",
        'melee_weapon_durability': mw_durability,
        'body_parts': _json(d.get('body_parts'), {}),
        'equipped_modules': _json(d.get('equipped_modules'), {}),
        'modules_inventory': _json(d.get('modules_inventory'), []),
        'weapons_inventory': _json(d.get('weapons_inventory'), []),
        'melee_inventory': _json(d.get('melee_inventory'), []),
        'next_magazine_uid': d.get('next_magazine_uid') or 1,
        'radiation': d.get('radiation') or 0.0,
        'chemical': d.get('chemical') or 0.0,
        'diseases': _json(d.get('diseases'), []),
        'cold': d.get('cold') or 0.0,
        'shell_ammo': _json(d.get('shell_ammo'), {}),
        'grenades_inventory': _json(d.get('grenades_inventory'), {}),
        'throwing_knives_inventory': _json(d.get('throwing_knives_inventory'), {}),
        'is_burning': _json(d.get('is_burning'), []),
        'mg_reload_progress': d.get('mg_reload_progress') or 0,
        'bleeding_stacks': _json(d.get('bleeding_stacks'), []),
        'cold_transition_counter': d.get('cold_transition_counter') or 0,
        'cold_sickness_transitions': d.get('cold_sickness_transitions') or 0,
        'blood_infection_soft_transitions':
            d.get('blood_infection_soft_transitions') or 0,
        'is_sleeping': bool(d.get('is_sleeping', 0)),
        'faction': d.get('faction') or 'loners',
        'faction_relations': _json(d.get('faction_relations'), {}),
        'faction_loyalty': _json(d.get('faction_loyalty'), {}),
        'origin': d.get('origin') or '',
        'prologue_completed': bool(d.get('prologue_completed', 0)),
        'active_tasks': _json(d.get('active_tasks'), []),
        'surface_unlocked': bool(d.get('surface_unlocked', 0)),
        'varyag_pass_kept': bool(d.get('varyag_pass_kept', 0)),
        # 0.4.8.7
        'trader_loyalty': _json(d.get('trader_loyalty'), {}),
    }


def _build_save_params(player) -> dict:
    g = lambda name, default: getattr(player, name, default)

    skills_json = json.dumps(g('skills', {}), ensure_ascii=False)
    inventory_json = json.dumps(g('inventory', {}), ensure_ascii=False)
    gas_mask_json = json.dumps(g('gas_mask', {}), ensure_ascii=False)
    buffs_json = json.dumps(g('buffs', []), ensure_ascii=False)
    debuffs_json = json.dumps(g('debuffs', []), ensure_ascii=False)
    magazines_json = json.dumps(g('magazines', []), ensure_ascii=False)
    ammo_inv_json = json.dumps(g('ammo_inventory', {}), ensure_ascii=False)
    filters_json = json.dumps(g('filters', []), ensure_ascii=False)
    food_inv_json = json.dumps(g('food_inventory', []), ensure_ascii=False)
    body_parts_json = json.dumps(g('body_parts', {}), ensure_ascii=False)
    eq_modules_json = json.dumps(g('equipped_modules', {}), ensure_ascii=False)
    modules_inv_json = json.dumps(g('modules_inventory', []), ensure_ascii=False)
    weapons_inv_json = json.dumps(g('weapons_inventory', []), ensure_ascii=False)
    melee_inv_json = json.dumps(g('melee_inventory', []), ensure_ascii=False)
    diseases_json = json.dumps(g('diseases', []), ensure_ascii=False)
    armor_durability_json = json.dumps(g('armor_durability', {}), ensure_ascii=False)
    armor_inv_json = json.dumps(g('armor_inventory', []), ensure_ascii=False)
    shell_ammo_json = json.dumps(g('shell_ammo', {}), ensure_ascii=False)
    grenades_json = json.dumps(g('grenades_inventory', {}), ensure_ascii=False)
    knives_json = json.dumps(g('throwing_knives_inventory', {}), ensure_ascii=False)
    is_burning_json = json.dumps(g('is_burning', []), ensure_ascii=False)
    bleeding_json = json.dumps(g('bleeding_stacks', []), ensure_ascii=False)
    faction_relations_json = json.dumps(g('faction_relations', {}), ensure_ascii=False)
    faction_loyalty_json = json.dumps(g('faction_loyalty', {}), ensure_ascii=False)
    active_tasks_json = json.dumps(g('active_tasks', []), ensure_ascii=False)
    trader_loyalty_json = json.dumps(g('trader_loyalty', {}), ensure_ascii=False)

    return {
        'user_id': g('user_id', 0),
        'username': g('username', 'Unknown'),
        'name': g('name', 'Безымянный'),
        'backstory': g('backstory', 'Без предыстории'),
        'level': g('level', 1),
        'xp': g('xp', 0),
        'xp_to_next': g('xp_to_next', 10),
        'lives': g('lives', 10.0),
        'stamina': g('stamina', 10.0),
        'max_stamina': g('max_stamina', 10.0),
        'location': g('location', 'бульвар_дмитрия_донского'),
        'is_alive': 1 if g('is_alive', True) else 0,
        'weapon': g('weapon', 'пистолет_макарова'),
        'armor': 0,
        'helmet': g('helmet', None) or 0,
        'skill_points': g('skill_points', 0),
        'skills': skills_json,
        'inventory': inventory_json,
        'gas_mask': gas_mask_json,
        'buffs': buffs_json,
        'debuffs': debuffs_json,
        'equipped_magazine': g('equipped_magazine', None),
        'magazines': magazines_json,
        'ammo_inventory': ammo_inv_json,
        'equipped_filter': g('equipped_filter', None),
        'filters': filters_json,
        'food_inventory': food_inv_json,
        'station_defense': g('station_defense', 0),
        'combat_mode': 1 if g('combat_mode', False) else 0,
        'combat_target': g('combat_target', None),
        'melee_weapon': g('melee_weapon', 'кулаки'),
        'melee_weapon_durability': g('melee_weapon_durability', 999),
        'body_parts': body_parts_json,
        'equipped_modules': eq_modules_json,
        'modules_inventory': modules_inv_json,
        'weapons_inventory': weapons_inv_json,
        'melee_inventory': melee_inv_json,
        'next_magazine_uid': g('next_magazine_uid', 1),
        'radiation': g('radiation', 0.0),
        'chemical': g('chemical', 0.0),
        'diseases': diseases_json,
        'armor_id': g('armor', None),
        'helmet_id': g('helmet', None),
        'armor_durability': armor_durability_json,
        'armor_inventory': armor_inv_json,
        'cold': g('cold', 0.0),
        'shell_ammo': shell_ammo_json,
        'grenades_inventory': grenades_json,
        'throwing_knives_inventory': knives_json,
        'is_burning': is_burning_json,
        'mg_reload_progress': g('mg_reload_progress', 0),
        'bleeding_stacks': bleeding_json,
        'cold_transition_counter': g('cold_transition_counter', 0),
        'cold_sickness_transitions': g('cold_sickness_transitions', 0),
        'blood_infection_soft_transitions': g('blood_infection_soft_transitions', 0),
        'is_sleeping': 1 if g('is_sleeping', False) else 0,
        'faction': g('faction', 'loners'),
        'faction_relations': faction_relations_json,
        'faction_loyalty': faction_loyalty_json,
        'origin': g('origin', ''),
        'prologue_completed': 1 if g('prologue_completed', False) else 0,
        'active_tasks': active_tasks_json,
        'surface_unlocked': 1 if g('surface_unlocked', False) else 0,
        'varyag_pass_kept': 1 if g('varyag_pass_kept', False) else 0,
        'trader_loyalty': trader_loyalty_json,
    }


# ==================== CRUD ====================

async def save_player(player) -> bool:
    try:
        db = await get_db()
        params = _build_save_params(player)

        await db.execute('''
            INSERT OR REPLACE INTO players (
                user_id, username, name, backstory, level, xp, xp_to_next,
                lives, stamina, max_stamina, location, is_alive,
                weapon, armor, helmet, skill_points,
                skills, inventory, gas_mask, buffs, debuffs,
                equipped_magazine, magazines, ammo_inventory,
                equipped_filter, filters, food_inventory,
                station_defense, combat_mode, combat_target,
                melee_weapon, melee_weapon_durability, body_parts,
                equipped_modules, modules_inventory,
                weapons_inventory, melee_inventory, next_magazine_uid,
                radiation, chemical, diseases,
                armor_id, helmet_id, armor_durability, armor_inventory,
                cold, shell_ammo, grenades_inventory, throwing_knives_inventory,
                is_burning, mg_reload_progress,
                bleeding_stacks, cold_transition_counter,
                cold_sickness_transitions, blood_infection_soft_transitions,
                is_sleeping,
                faction, faction_relations, faction_loyalty,
                origin, prologue_completed, active_tasks,
                surface_unlocked, varyag_pass_kept, trader_loyalty
            ) VALUES (
                :user_id, :username, :name, :backstory, :level, :xp, :xp_to_next,
                :lives, :stamina, :max_stamina, :location, :is_alive,
                :weapon, :armor, :helmet, :skill_points,
                :skills, :inventory, :gas_mask, :buffs, :debuffs,
                :equipped_magazine, :magazines, :ammo_inventory,
                :equipped_filter, :filters, :food_inventory,
                :station_defense, :combat_mode, :combat_target,
                :melee_weapon, :melee_weapon_durability, :body_parts,
                :equipped_modules, :modules_inventory,
                :weapons_inventory, :melee_inventory, :next_magazine_uid,
                :radiation, :chemical, :diseases,
                :armor_id, :helmet_id, :armor_durability, :armor_inventory,
                :cold, :shell_ammo, :grenades_inventory, :throwing_knives_inventory,
                :is_burning, :mg_reload_progress,
                :bleeding_stacks, :cold_transition_counter,
                :cold_sickness_transitions, :blood_infection_soft_transitions,
                :is_sleeping,
                :faction, :faction_relations, :faction_loyalty,
                :origin, :prologue_completed, :active_tasks,
                :surface_unlocked, :varyag_pass_kept, :trader_loyalty
            )
        ''', params)
        await db.commit()
        return True

    except Exception as e:
        print(f"[ERROR] Ошибка сохранения игрока: {e}")
        traceback.print_exc()
        return False


async def load_player(user_id: int):
    try:
        db = await get_db()
        async with db.execute(
                'SELECT * FROM players WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return _row_to_dict(row)

    except Exception as e:
        print(f"[ERROR] Ошибка загрузки игрока {user_id}: {e}")
        return None


async def delete_player(user_id: int) -> None:
    try:
        db = await get_db()
        await db.execute('DELETE FROM players WHERE user_id = ?', (user_id,))
        await db.commit()
    except Exception as e:
        print(f"[ERROR] Ошибка удаления: {e}")


async def get_all_players() -> list:
    try:
        db = await get_db()
        async with db.execute('SELECT * FROM players') as cursor:
            rows = await cursor.fetchall()
            return [_row_to_dict(row) for row in rows]

    except Exception as e:
        print(f"[ERROR] Ошибка получения игроков: {e}")
        return []


async def clear_all_players():
    try:
        db = await get_db()
        await db.execute('DELETE FROM players')
        await db.commit()
    except Exception as e:
        print(f"[ERROR] Ошибка очистки: {e}")


async def get_db_info():
    try:
        db = await get_db()
        async with db.execute("PRAGMA table_info(players)") as cursor:
            columns = await cursor.fetchall()
            print(
                f"[INFO] Столбцы в players ({len(columns)}): "
                f"{[col[1] for col in columns]}"
            )
    except Exception as e:
        print(f"[ERROR] {e}")


# ==================== КЛЮЧИ ДОСТУПА ====================

def _generate_key() -> str:
    alphabet = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(alphabet) for _ in range(4))
    part2 = ''.join(secrets.choice(alphabet) for _ in range(4))
    return f"MTR-{part1}-{part2}"


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
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
    return None


async def create_access_key(key_type: str) -> str:
    db = await get_db()

    for _ in range(20):
        key = _generate_key()
        async with db.execute(
                "SELECT 1 FROM access_keys WHERE key = ?", (key,)
        ) as cur:
            exists = await cur.fetchone()
        if not exists:
            break
    else:
        raise RuntimeError("Не удалось сгенерировать уникальный ключ")

    await db.execute(
        "INSERT INTO access_keys (key, key_type) VALUES (?, ?)",
        (key, key_type)
    )
    await db.commit()
    return key


async def get_access_key(key: str) -> Optional[dict]:
    db = await get_db()
    async with db.execute(
            "SELECT * FROM access_keys WHERE key = ?", (key,)
    ) as cur:
        row = await cur.fetchone()
        if not row:
            return None
        return dict(row)


async def activate_access_key(key: str, user_id: int) -> tuple:
    data = await get_access_key(key)
    if not data:
        return False, "❌ Ключ не найден."

    if data['used_by'] is not None and data['used_by'] != user_id:
        return False, "❌ Ключ уже использован другим игроком."

    if data['used_by'] == user_id:
        if data['key_type'] == 'permanent':
            return True, "OK"
        if data['expires_at']:
            exp = _parse_dt(data['expires_at'])
            if exp and datetime.now() > exp:
                return False, "❌ Срок действия ключа истёк."
        return True, "OK"

    now = datetime.now()
    expires_at = None

    if data['key_type'] == '1_day':
        expires_at = now + timedelta(days=1)
    elif data['key_type'] == '7_days':
        expires_at = now + timedelta(days=7)

    db = await get_db()
    await db.execute(
        "UPDATE access_keys SET used_by = ?, activated_at = ?, expires_at = ? "
        "WHERE key = ?",
        (user_id, now, expires_at, key)
    )
    await db.commit()

    return True, "OK"


async def check_player_access(user_id: int) -> tuple:
    db = await get_db()
    async with db.execute(
            "SELECT * FROM access_keys WHERE used_by = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
        if not row:
            return False, "Нет ключа"
        data = dict(row)

    if data['key_type'] == 'permanent':
        return True, "OK"

    if data['expires_at']:
        exp = _parse_dt(data['expires_at'])
        if exp and datetime.now() > exp:
            return False, "Срок действия ключа истёк."
    return True, "OK"


async def list_access_keys(used_only: bool = False, limit: int = 50) -> list:
    db = await get_db()
    if used_only:
        query = (
            "SELECT * FROM access_keys WHERE used_by IS NOT NULL "
            "ORDER BY activated_at DESC LIMIT ?"
        )
    else:
        query = "SELECT * FROM access_keys ORDER BY created_at DESC LIMIT ?"
    async with db.execute(query, (limit,)) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def revoke_access_key(key: str) -> bool:
    db = await get_db()
    async with db.execute(
            "SELECT 1 FROM access_keys WHERE key = ?", (key,)
    ) as cur:
        if not await cur.fetchone():
            return False
    await db.execute(
        "UPDATE access_keys SET used_by = NULL, activated_at = NULL, "
        "expires_at = NULL WHERE key = ?",
        (key,)
    )
    await db.commit()
    return True


async def delete_access_key(key: str) -> bool:
    db = await get_db()
    async with db.execute(
            "SELECT 1 FROM access_keys WHERE key = ?", (key,)
    ) as cur:
        if not await cur.fetchone():
            return False
    await db.execute("DELETE FROM access_keys WHERE key = ?", (key,))
    await db.commit()
    return True