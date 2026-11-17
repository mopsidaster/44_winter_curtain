# -*- coding: utf-8 -*-
# config/map_config.py - Загрузчик конфигурационных файлов (Билд 0.4.4)
#
# ИСПРАВЛЕНИЯ (патч 0.4.4):
#   • Проверка типа для ключевых конфигов (должны быть dict)
#   • Понятные сообщения об ошибках структуры

import json
import os

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))


EXPECTED_CONFIGS = [
    'balance.json',
    'weapons.json',
    'items.json',
    'magazines.json',
    'ammo.json',
    'food.json',
    'filters.json',
    'mutants.json',
    'melee.json',
    'health.json',
    'modules.json',
    'stations.json',
    'armor.json',
    'diseases.json',
    'pharmacy.json',
    'factions.json',
]


# Какие конфиги должны быть объектами (dict), а не массивами/строками
MUST_BE_DICT = {
    'balance.json',
    'weapons.json',
    'items.json',
    'magazines.json',
    'ammo.json',
    'food.json',
    'filters.json',
    'mutants.json',
    'melee.json',
    'health.json',
    'modules.json',
    'stations.json',
    'armor.json',
    'diseases.json',
    'pharmacy.json',
    'factions.json',
}


# Какие ключи обязательны внутри конфига
REQUIRED_KEYS = {
    'items.json': ['shop', 'sell'],
    'weapons.json': [],  # любые ключи допустимы
    'magazines.json': [],
    'modules.json': ['slots', 'modules'],
    'ammo.json': ['calibers', 'ammo_types'],
    'food.json': ['foods'],
    'filters.json': ['фильтры'],
    'mutants.json': ['mutants'],
    'melee.json': ['melee_weapons'],
    'health.json': ['player'],
    'stations.json': ['станции'],
    'armor.json': ['armor_sets', 'sets'],
    'diseases.json': ['radiation', 'chemical', 'diseases'],
    'pharmacy.json': ['shop_items', 'doctor_services'],
    'balance.json': [],
    'factions.json': ['factions', 'loyalty_thresholds', 'relation_types'],
}


def load_config(filename: str) -> dict:
    """
    Загрузка JSON конфига с обработкой ошибок.
    Бросает понятные ошибки, если структура неверна.
    """
    path = os.path.join(CONFIG_DIR, filename)

    if not os.path.exists(path):
        print("=" * 60)
        print(f"❌ Файл не найден: {path}")
        print("=" * 60)
        raise FileNotFoundError(f"Конфиг {filename} не найден по пути {path}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print("=" * 60)
        print(f"❌ Ошибка JSON в {filename}:")
        print(f"   {e}")
        print(f"   Строка {e.lineno}, колонка {e.colno}")
        print("   Проверьте синтаксис JSON (запятые, кавычки, скобки)")
        print("=" * 60)
        raise

    # Проверка типа: должен быть dict
    if filename in MUST_BE_DICT and not isinstance(data, dict):
        actual_type = type(data).__name__
        print("=" * 60)
        print(f"❌ Неверная структура {filename}:")
        print(f"   Ожидался объект {{...}}, получен {actual_type}")
        if isinstance(data, list):
            print(f"   Похоже, у вас массив [...] вместо объекта {{...}}")
            print(f"   Первые элементы: {data[:2] if len(data) <= 3 else data[:3]}")
        print(f"   Файл: {path}")
        print("=" * 60)
        raise TypeError(
            f"{filename} должен быть объектом (dict), а не {actual_type}. "
            f"Проверьте структуру файла."
        )

    # Проверка обязательных ключей
    required = REQUIRED_KEYS.get(filename, [])
    if required and isinstance(data, dict):
        missing = [k for k in required if k not in data]
        if missing:
            print("=" * 60)
            print(f"❌ В {filename} отсутствуют обязательные ключи:")
            for k in missing:
                print(f"   • {k}")
            print(f"   Файл: {path}")
            print("=" * 60)
            raise KeyError(
                f"{filename}: отсутствуют ключи {missing}"
            )

    return data


def _check_all_configs():
    """Проверить наличие всех ожидаемых конфигов."""
    missing = []
    for name in EXPECTED_CONFIGS:
        path = os.path.join(CONFIG_DIR, name)
        if not os.path.exists(path):
            missing.append(name)

    if missing:
        print("=" * 60)
        print(f"❌ Не найдены конфиги в {CONFIG_DIR}:")
        for m in missing:
            print(f"   • {m}")
        print("Скопируйте их из предыдущего билда или создайте заново.")
        print("=" * 60)
        raise FileNotFoundError(f"Отсутствуют конфиги: {', '.join(missing)}")


# Проверка перед загрузкой
_check_all_configs()

# ==================== ЗАГРУЗКА ====================

BALANCE = load_config('balance.json')
WEAPONS = load_config('weapons.json')
ITEMS = load_config('items.json')
MAGAZINES = load_config('magazines.json')
AMMO = load_config('ammo.json')
FOOD = load_config('food.json')
FILTERS = load_config('filters.json')
MUTANTS = load_config('mutants.json')
MELEE = load_config('melee.json')
HEALTH = load_config('health.json')
MODULES = load_config('modules.json')

ARMOR = load_config('armor.json')
DISEASES = load_config('diseases.json')
PHARMACY = load_config('pharmacy.json')

_raw_stations = load_config('stations.json')
STATIONS = _raw_stations
STATIONS_DICT = _raw_stations.get("станции", {})
LINES_DICT = _raw_stations.get("lines", {})
TECHNICAL_TUNNELS_DICT = _raw_stations.get("technical_tunnels", {})
FACTIONS = load_config('factions.json')
FACTIONS_DICT = FACTIONS.get('factions', {})
NPCS_DICT = FACTIONS.get('npcs', {})
LOYALTY_THRESHOLDS = FACTIONS.get('loyalty_thresholds', {})
RELATION_TYPES = FACTIONS.get('relation_types', {})


# ==================== УДОБНЫЕ АКСЕССОРЫ ====================

def get_armor(armor_id: str) -> dict:
    return ARMOR.get('armor_sets', {}).get(armor_id)


def get_armor_set(set_id: str) -> dict:
    return ARMOR.get('sets', {}).get(set_id)


def get_disease(disease_id: str) -> dict:
    return DISEASES.get('diseases', {}).get(disease_id)


def get_pharmacy_item(item_id: str) -> dict:
    return PHARMACY.get('shop_items', {}).get(item_id)


def get_doctor_service(service_id: str) -> dict:
    return PHARMACY.get('doctor_services', {}).get(service_id)