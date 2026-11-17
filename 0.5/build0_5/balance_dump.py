# -*- coding: utf-8 -*-
# balance_dump.py - Выгрузка данных игры в XLSX (по листам) или CSV-файлы
#
# Использование:
#   pip install openpyxl      # один раз
#   python balance_dump.py
#
# Что делает:
#   • Если openpyxl установлен → balance_report.xlsx с ЛИСТАМИ:
#       Оружие, Патроны, Магазины, Модули, БлижнийБой, Броня, Сеты,
#       Здоровье, Болезни, Баланс, Цены, Еда, Фильтры, Аптека,
#       Мутанты, Станции
#   • Если openpyxl нет → папка balance_report/ с отдельными .csv
#     (те же листы, по файлу на каждый)

import json
import os
import csv
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

CONFIGS = {
    "weapons": "weapons.json",
    "ammo": "ammo.json",
    "magazines": "magazines.json",
    "modules": "modules.json",
    "melee": "melee.json",
    "armor": "armor.json",
    "items": "items.json",
    "food": "food.json",
    "filters": "filters.json",
    "pharmacy": "pharmacy.json",
    "balance": "balance.json",
    "health": "health.json",
    "diseases": "diseases.json",
    "mutants": "mutants.json",
    "stations": "stations.json",
}


# ==================== ЗАГРУЗКА ====================

def load_json(filename):
    path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Ошибка чтения {filename}: {e}")
        return None


def load_all():
    return {key: load_json(fname) for key, fname in CONFIGS.items()}


def clean_keys(d):
    if not isinstance(d, dict):
        return d
    return {k: v for k, v in d.items() if not k.startswith("_")}


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "да" if v else "нет"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


# ==================== ЛИСТЫ ====================
# Каждый лист = (имя_листа, [заголовки], [строки])

def sheet_weapons(weapons):
    headers = [
        "id", "name", "type", "damage", "accuracy", "price", "caliber",
        "magazines", "shell_loading", "shell_capacity", "builtin_module",
        "duds_chance", "self_explode_chance", "dodge_chance",
        "miss_one_chance", "explosive_multiplier", "description",
    ]
    rows = []
    if not weapons:
        return ("Оружие", headers, rows)
    for wid, w in clean_keys(weapons).items():
        if not isinstance(w, dict):
            continue
        rows.append([
            wid, w.get("name", wid), w.get("type", ""),
            fmt(w.get("damage")), fmt(w.get("accuracy")), fmt(w.get("price")),
            w.get("caliber", ""),
            fmt(w.get("magazines")),
            fmt(w.get("shell_loading")),
            fmt(w.get("shell_capacity")),
            fmt(w.get("builtin_module")),
            fmt(w.get("duds_chance")),
            fmt(w.get("self_explode_chance")),
            fmt(w.get("dodge_chance")),
            fmt(w.get("miss_one_chance")),
            fmt(w.get("explosive_multiplier")),
            w.get("description", ""),
        ])
    return ("Оружие", headers, rows)


def sheet_ammo(ammo):
    headers = ["id", "name", "kind", "multiplier", "armor_piercing",
               "close_multiplier", "damage_bonus", "allow_far", "incendiary",
               "shotgun_only", "description"]
    rows = []
    if not ammo:
        return ("Патроны", headers, rows)

    for tid, t in clean_keys(ammo.get("ammo_types", {})).items():
        if not isinstance(t, dict):
            continue
        rows.append([
            tid, t.get("name", tid), "тип",
            fmt(t.get("multiplier")),
            fmt(t.get("armor_piercing")),
            fmt(t.get("close_multiplier")),
            fmt(t.get("damage_bonus")),
            fmt(t.get("allow_far")),
            fmt(t.get("incendiary")),
            fmt(t.get("shotgun_only")),
            t.get("description", ""),
        ])
    for cal, c in clean_keys(ammo.get("calibers", {})).items():
        if not isinstance(c, dict):
            continue
        rows.append([
            cal, c.get("name", cal), "калибр",
            "", "", "", "", "", "", "",
            fmt(c.get("types")),
        ])
    return ("Патроны", headers, rows)


def sheet_magazines(magazines):
    headers = ["id", "name", "capacity", "caliber", "weapon", "price"]
    rows = []
    if not magazines:
        return ("Магазины", headers, rows)
    for mid, m in clean_keys(magazines).items():
        if not isinstance(m, dict):
            continue
        rows.append([
            mid, m.get("name", mid), fmt(m.get("capacity")),
            m.get("caliber", ""), m.get("weapon", ""), fmt(m.get("price")),
        ])
    return ("Магазины", headers, rows)


def sheet_modules(modules):
    headers = ["id", "name", "slot", "type", "acc_close", "acc_medium",
               "acc_far", "price", "special", "description"]
    rows = []
    if not modules:
        return ("Модули", headers, rows)
    for mid, m in clean_keys(modules.get("modules", {})).items():
        if not isinstance(m, dict):
            continue
        acc = m.get("accuracy", {}) or {}
        rows.append([
            mid, m.get("name", mid), m.get("slot", ""), m.get("type", ""),
            fmt(acc.get("close")), fmt(acc.get("medium")), fmt(acc.get("far")),
            fmt(m.get("price")),
            fmt(m.get("special")),
            m.get("description", ""),
        ])
    return ("Модули", headers, rows)


def sheet_melee(melee):
    headers = ["id", "name", "damage", "accuracy", "type", "stun_chance",
               "durability", "price", "skill_multiplier", "indestructible"]
    rows = []
    if not melee:
        return ("БлижнийБой", headers, rows)
    for wid, w in clean_keys(melee.get("melee_weapons", {})).items():
        if not isinstance(w, dict):
            continue
        rows.append([
            wid, w.get("name", wid), fmt(w.get("damage")), fmt(w.get("accuracy")),
            w.get("type", ""), fmt(w.get("stun_chance")),
            fmt(w.get("max_durability")), fmt(w.get("price")),
            fmt(w.get("skill_multiplier")), fmt(w.get("indestructible")),
        ])
    return ("БлижнийБой", headers, rows)


def sheet_armor(armor):
    headers = ["id", "name", "slot", "zones", "max_durability",
               "impact_protection", "armor_protection", "thermal_resistance",
               "ricochet_chance", "price", "set_id"]
    rows = []
    if not armor:
        return ("Броня", headers, rows)
    for aid, a in clean_keys(armor.get("armor_sets", {})).items():
        if not isinstance(a, dict):
            continue
        rows.append([
            aid, a.get("name", aid), a.get("slot", ""), fmt(a.get("zones")),
            fmt(a.get("max_durability")), fmt(a.get("impact_protection")),
            fmt(a.get("armor_protection")), fmt(a.get("thermal_resistance")),
            fmt(a.get("ricochet_chance")), fmt(a.get("price")),
            a.get("set_id", ""),
        ])
    return ("Броня", headers, rows)


def sheet_armor_sets(armor):
    headers = ["id", "name", "required", "bonuses"]
    rows = []
    if not armor:
        return ("Сеты", headers, rows)
    for sid, s in clean_keys(armor.get("sets", {})).items():
        if not isinstance(s, dict):
            continue
        bonuses = []
        for b in s.get("bonuses", []):
            if isinstance(b, dict):
                bonuses.append(b.get("description", b.get("type", "")))
        rows.append([
            sid, s.get("name", sid), fmt(s.get("required")), "; ".join(bonuses),
        ])
    return ("Сеты", headers, rows)


def sheet_health(health):
    headers = ["id", "name", "max_hp", "multiplier"]
    rows = []
    if not health:
        return ("Здоровье", headers, rows)
    player = health.get("player", {}) or {}
    rows.append(["total_health", "Общее здоровье", fmt(player.get("total_health")), ""])
    for pid, p in clean_keys(player.get("body_parts", {})).items():
        if not isinstance(p, dict):
            continue
        rows.append([
            pid, p.get("name", pid), fmt(p.get("max_hp")), fmt(p.get("multiplier")),
        ])
    block = player.get("block", {}) or {}
    rows.append(["block_base", "Блок — базовое снижение", fmt(block.get("damage_reduction_base")), ""])
    rows.append(["block_per_toughness", "Блок — за уровень Стойкости", fmt(block.get("damage_reduction_per_toughness")), ""])
    return ("Здоровье", headers, rows)


def sheet_diseases(diseases):
    headers = ["id", "name", "kind", "max", "threshold",
               "decay_on_safe", "decay_on_safe_to_safe",
               "damage_per_transition", "curable", "cure_cost", "description"]
    rows = []
    if not diseases:
        return ("Болезни", headers, rows)

    for key in ("radiation", "chemical"):
        d = clean_keys(diseases.get(key, {}))
        if not d:
            continue
        rows.append([
            key, d.get("name", key), "заражение",
            fmt(d.get("max")), fmt(d.get("threshold")),
            fmt(d.get("decay_on_safe")), fmt(d.get("decay_on_safe_to_safe")),
            "", "", "", d.get("description", ""),
        ])
    for did, d in clean_keys(diseases.get("diseases", {})).items():
        if not isinstance(d, dict):
            continue
        rows.append([
            did, d.get("name", did), "болезнь",
            "", "", "", "",
            fmt(d.get("damage_per_transition")),
            fmt(d.get("curable")), fmt(d.get("cure_cost")),
            d.get("description", ""),
        ])
    return ("Болезни", headers, rows)


def sheet_balance(balance):
    headers = ["section", "key", "value"]
    rows = []
    if not balance:
        return ("Баланс", headers, rows)

    for section in ("player", "skills", "combat", "human_combat",
                    "throwables", "armor", "gas_mask", "cold", "optics",
                    "gas_leak", "items"):
        data = clean_keys(balance.get(section, {}))
        for k, v in data.items():
            if k == "comment":
                continue
            rows.append([section, k, fmt(v)])

    for dkey, d in clean_keys(balance.get("distance", {})).items():
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            rows.append([f"distance/{dkey}", k, fmt(v)])

    for k, v in clean_keys(balance.get("shotgun", {})).items():
        rows.append(["shotgun", k, fmt(v)])

    for bid, b in clean_keys(balance.get("bosses", {})).items():
        if not isinstance(b, dict):
            continue
        for k, v in b.items():
            rows.append([f"bosses/{bid}", k, fmt(v)])

    for zone, events in balance.get("transition_events", {}).items():
        if not isinstance(events, dict):
            continue
        for ekey, e in events.items():
            if not isinstance(e, dict):
                continue
            for k, v in e.items():
                rows.append([f"transition/{zone}", f"{ekey}.{k}", fmt(v)])

    return ("Баланс", headers, rows)


def sheet_prices(balance, weapons):
    headers = ["category", "id", "name", "price"]
    rows = []
    if not balance:
        return ("Цены", headers, rows)
    prices = balance.get("prices", {})

    for wid, price in clean_keys(prices.get("weapon", {})).items():
        name = wid
        if weapons and isinstance(weapons.get(wid), dict):
            name = weapons[wid].get("name", wid)
        rows.append(["weapon", wid, name, fmt(price)])

    for mid, price in clean_keys(prices.get("magazine", {})).items():
        rows.append(["magazine", mid, mid, fmt(price)])

    for cal, types in clean_keys(prices.get("ammo", {})).items():
        if not isinstance(types, dict):
            continue
        for t, price in types.items():
            rows.append([f"ammo/{cal}", t, t, fmt(price)])

    for fid, price in clean_keys(prices.get("food", {})).items():
        rows.append(["food", fid, fid, fmt(price)])

    for fid, price in clean_keys(prices.get("filter", {})).items():
        rows.append(["filter", fid, fid, fmt(price)])

    for key in ("medkit", "repair"):
        v = prices.get(key)
        if v is not None:
            rows.append(["misc", key, key, fmt(v)])

    return ("Цены", headers, rows)


def sheet_food(food):
    headers = ["id", "name", "stamina", "price", "can_cook", "cooked"]
    rows = []
    if not food:
        return ("Еда", headers, rows)
    for fid, f in clean_keys(food.get("foods", {})).items():
        if not isinstance(f, dict):
            continue
        rows.append([
            fid, f.get("name", fid), fmt(f.get("stamina")),
            fmt(f.get("price")), fmt(f.get("can_cook")),
            f.get("cooked", ""),
        ])
    return ("Еда", headers, rows)


def sheet_filters(filters):
    headers = ["id", "name", "durability", "price"]
    rows = []
    if not filters:
        return ("Фильтры", headers, rows)
    for fid, f in clean_keys(filters.get("фильтры", {})).items():
        if not isinstance(f, dict):
            continue
        rows.append([fid, f.get("name", fid), fmt(f.get("durability")), fmt(f.get("price"))])
    return ("Фильтры", headers, rows)


def sheet_pharmacy(pharmacy):
    headers = ["kind", "id", "name", "heal", "rad_reduction",
               "price", "effect", "cures_disease", "description"]
    rows = []
    if not pharmacy:
        return ("Аптека", headers, rows)

    for iid, i in clean_keys(pharmacy.get("shop_items", {})).items():
        if not isinstance(i, dict):
            continue
        rows.append([
            "товар", iid, i.get("name", iid),
            fmt(i.get("heal")), fmt(i.get("radiation_reduction")),
            fmt(i.get("price")), fmt(i.get("effect")),
            "", i.get("description", ""),
        ])

    for sid, s in clean_keys(pharmacy.get("doctor_services", {})).items():
        if not isinstance(s, dict):
            continue
        rows.append([
            "услуга", sid, s.get("name", sid),
            "", "", fmt(s.get("price")),
            fmt(s.get("effect")), fmt(s.get("cures_disease")),
            s.get("description", ""),
        ])
    return ("Аптека", headers, rows)


def sheet_mutants(mutants):
    headers = ["id", "name", "is_mutant", "is_human", "is_boss",
               "base_health", "hp_per_danger",
               "dmg_min", "dmg_max", "damage_per_danger",
               "hit_chance_base", "hit_chance_per_danger",
               "min_danger", "max_danger", "spawn_weight",
               "xp_min", "xp_max", "nickels_min", "nickels_max",
               "loot", "attack_texts", "weapons", "armor_choices"]
    rows = []
    if not mutants:
        return ("Мутанты", headers, rows)
    for mid, m in clean_keys(mutants.get("mutants", {})).items():
        if not isinstance(m, dict):
            continue
        rows.append([
            mid, m.get("name", mid),
            fmt(m.get("is_mutant")), fmt(m.get("is_human")), fmt(m.get("is_boss")),
            fmt(m.get("base_health")), fmt(m.get("health_per_danger")),
            fmt(m.get("base_damage_min")), fmt(m.get("base_damage_max")),
            fmt(m.get("damage_per_danger")),
            fmt(m.get("hit_chance_base")), fmt(m.get("hit_chance_per_danger")),
            fmt(m.get("min_danger")), fmt(m.get("max_danger")),
            fmt(m.get("spawn_weight")),
            fmt(m.get("xp_min")), fmt(m.get("xp_max")),
            fmt(m.get("nickels_min")), fmt(m.get("nickels_max")),
            fmt(m.get("loot")), fmt(m.get("attack_texts")),
            fmt(m.get("weapons")), fmt(m.get("armor_choices")),
        ])
    return ("Мутанты", headers, rows)


def sheet_stations(stations):
    headers = ["id", "name", "line", "types", "danger", "ruined",
               "hostile", "connections", "transfer", "technical_tunnel",
               "description"]
    rows = []
    if not stations:
        return ("Станции", headers, rows)
    for sid, s in clean_keys(stations.get("станции", {})).items():
        if not isinstance(s, dict):
            continue
        types = s.get("types", [s.get("type", "")])
        rows.append([
            sid, s.get("name", sid), s.get("line", ""),
            fmt(types), fmt(s.get("danger")), fmt(s.get("ruined")),
            fmt(s.get("hostile")), fmt(s.get("connections")),
            fmt(s.get("transfer")), fmt(s.get("technical_tunnel")),
            s.get("description", ""),
        ])
    return ("Станции", headers, rows)


# ==================== СБОРКА ЛИСТОВ ====================

def build_sheets(configs):
    return [
        sheet_weapons(configs.get("weapons")),
        sheet_ammo(configs.get("ammo")),
        sheet_magazines(configs.get("magazines")),
        sheet_modules(configs.get("modules")),
        sheet_melee(configs.get("melee")),
        sheet_armor(configs.get("armor")),
        sheet_armor_sets(configs.get("armor")),
        sheet_health(configs.get("health")),
        sheet_diseases(configs.get("diseases")),
        sheet_balance(configs.get("balance")),
        sheet_prices(configs.get("balance"), configs.get("weapons")),
        sheet_food(configs.get("food")),
        sheet_filters(configs.get("filters")),
        sheet_pharmacy(configs.get("pharmacy")),
        sheet_mutants(configs.get("mutants")),
        sheet_stations(configs.get("stations")),
    ]


# ==================== ЭКСПОРТ ====================

def export_xlsx(sheets, out_path):
    """Экспорт в XLSX с листами. Требует openpyxl."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        return False

    wb = Workbook()
    wb.remove(wb.active)  # удаляем дефолтный пустой лист

    header_fill = PatternFill("solid", fgColor="2F5B91")
    header_font = Font(bold=True, color="FFFFFF")

    for sheet_name, headers, rows in sheets:
        # Excel ограничивает имя листа 31 символом
        safe_name = sheet_name[:31]
        ws = wb.create_sheet(title=safe_name)

        # заголовки
        for col_idx, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=col_idx, value=h)
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal="center", vertical="center")

        # строки
        for r_idx, row in enumerate(rows, start=2):
            for c_idx, val in enumerate(row, start=1):
                if c_idx > len(headers):
                    break
                ws.cell(row=r_idx, column=c_idx, value=val)

        # авто-ширина колонок (приблизительно)
        for col_idx in range(1, len(headers) + 1):
            max_len = len(str(headers[col_idx - 1]))
            for row in rows[:200]:
                if col_idx - 1 < len(row):
                    l = len(str(row[col_idx - 1]))
                    if l > max_len:
                        max_len = l
            width = min(max_len + 2, 60)
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    wb.save(out_path)
    return True


def export_csv_folder(sheets, out_dir):
    """Fallback: экспорт каждого листа в отдельный CSV."""
    os.makedirs(out_dir, exist_ok=True)
    for sheet_name, headers, rows in sheets:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in sheet_name)
        path = os.path.join(out_dir, f"{safe_name}.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
    return True


# ==================== MAIN ====================

def main():
    print("=" * 60)
    print("📊 Дамп данных для балансировки Метро 2044")
    print("=" * 60)

    configs = load_all()
    loaded = [k for k, v in configs.items() if v is not None]
    missing = [k for k, v in configs.items() if v is None]

    print(f"\n✅ Загружено конфигов: {len(loaded)}/{len(CONFIGS)}")
    if missing:
        print(f"⚠️ Отсутствуют: {', '.join(missing)}")

    sheets = build_sheets(configs)
    total_rows = sum(len(r) for _, _, r in sheets)
    print(f"\n📄 Листов: {len(sheets)} | Всего строк: {total_rows}")

    # Пытаемся XLSX
    xlsx_path = os.path.join(BASE_DIR, "balance_report.xlsx")
    if export_xlsx(sheets, xlsx_path):
        print(f"\n✅ XLSX создан: {xlsx_path}")
        print("💡 Открой в Excel/LibreOffice — каждый раздел на своём листе.")
    else:
        csv_dir = os.path.join(BASE_DIR, "balance_report")
        print("\n⚠️ openpyxl не установлен — экспорт в CSV-файлы.")
        print("💡 Установи: pip install openpyxl")
        export_csv_folder(sheets, csv_dir)
        print(f"✅ CSV-файлы: {csv_dir}")

    print("=" * 60)


if __name__ == "__main__":
    main()