# -*- coding: utf-8 -*-
# func/food_system.py - Система еды и приготовления (Билд 0.4.5)
#
# ИСТОРИЯ:
#   0.4.2.8 — базовая система
#   0.4.5   — eat_food обрабатывает chemical_reduction и cold_reduction
#             (чайный гриб)

import random
from config.map_config import FOOD, BALANCE
from utils.logger import get_logger
from database.db import save_player

logger = get_logger()


def get_food(food_id: str) -> dict:
    return FOOD["foods"].get(food_id)


def get_food_name(food_id: str) -> str:
    food = get_food(food_id)
    if not food:
        return food_id
    return food.get("name", food_id)


def get_food_emoji(food_id: str) -> str:
    food = get_food(food_id)
    if not food:
        return "🍖"
    return food.get("emoji", "🍖")


def get_food_stamina(food_id: str) -> int:
    food = get_food(food_id)
    if not food:
        return 0
    return food.get("stamina", 0)


def get_food_price(food_id: str) -> int:
    return BALANCE.get('prices', {}).get('food', {}).get(food_id, 0)


def can_cook(food_id: str) -> bool:
    food = get_food(food_id)
    if not food:
        return False
    return food.get("can_cook", False)


def get_cooked_version(food_id: str) -> str:
    food = get_food(food_id)
    if not food:
        return None
    return food.get("cooked")


def get_all_foods() -> list:
    return list(FOOD["foods"].keys())


def get_cookable_foods() -> list:
    return [fid for fid, data in FOOD["foods"].items() if data.get("can_cook", False)]


def get_food_description(food_id: str) -> str:
    food = get_food(food_id)
    if not food:
        return ""

    desc = f"{food.get('emoji', '🍖')} **{food.get('name', food_id)}**\n"
    desc += f"📊 Восстанавливает: {food.get('stamina', 0)} выносливости\n"
    if food.get("can_cook", False):
        cooked = get_cooked_version(food_id)
        if cooked:
            cooked_data = get_food(cooked)
            desc += f"🍳 Можно приготовить → **{cooked_data.get('name', cooked)}** (+{cooked_data.get('stamina', 0)} выносливости)\n"
    desc += f"💰 Цена: {get_food_price(food_id)} никелей"
    return desc


def format_food_inventory(player) -> str:
    if not player.food_inventory:
        return "🍖 У вас нет еды"

    food_counts = {}
    for food_id in player.food_inventory:
        food_counts[food_id] = food_counts.get(food_id, 0) + 1

    result = ""
    for food_id, count in food_counts.items():
        food = get_food(food_id)
        if food:
            result += f"{food.get('emoji', '🍖')} **{food.get('name', food_id)}** x{count}\n"
        else:
            result += f"❓ {food_id} x{count}\n"

    return result


async def eat_food(player, food_id: str) -> str:
    """
    Съесть еду.
    0.4.5: обрабатывает chemical_reduction и cold_reduction (чайный гриб).
    """
    food = get_food(food_id)
    if not food:
        return "❌ Такой еды не существует!"

    if food_id not in player.food_inventory:
        return f"❌ У вас нет {food.get('name', food_id)}!"

    # УДАЛЯЕМ ЕДУ ИЗ ИНВЕНТАРЯ
    player.food_inventory.remove(food_id)

    messages = []

    # Восстанавливаем выносливость
    stamina_restore = food.get("stamina", 0)
    player.restore_stamina(stamina_restore)
    messages.append(f"+{stamina_restore} выносливости")

    # 0.4.5: снижение химии
    chemical_reduction = food.get("chemical_reduction", 0)
    if chemical_reduction > 0:
        from .disease_system import ensure_disease_fields
        ensure_disease_fields(player)
        before = player.chemical
        player.chemical = max(0.0, before - chemical_reduction)
        actual = before - player.chemical
        if actual > 0:
            messages.append(f"-{actual:.0f} химии")
            logger.info(f"🍄 {player.name} съел {food.get('name', food_id)}, -{actual:.0f} химии")

    # 0.4.5: снижение холода
    cold_reduction = food.get("cold_reduction", 0)
    if cold_reduction > 0:
        from .cold_system import ensure_cold_fields, get_thermal_resistance
        ensure_cold_fields(player)
        before = player.cold
        player.cold = max(0.0, before - cold_reduction)
        actual = before - player.cold
        if actual > 0:
            messages.append(f"-{actual:.0f} холода")
            # Если обморожение и холод 0 — снять
            if player.cold <= 0 and 'обморожение' in player.diseases:
                player.diseases.remove('обморожение')
                messages.append("обморожение прошло")

    # СОХРАНЯЕМ ИГРОКА
    await save_player(player)

    logger.info(
        f"🍽️ {player.name} съел {food.get('name', food_id)} "
        f"({', '.join(messages)}). Осталось еды: {len(player.food_inventory)}"
    )

    return (
            f"🍽️ **{player.name}** съел {food.get('emoji', '🍖')} "
            f"**{food.get('name', food_id)}**!\n"
            + " | ".join(messages)
    )


async def cook_food(player, food_id: str, campfire_type: str = "safe") -> str:
    food = get_food(food_id)
    if not food:
        return "❌ Такой еды не существует!"

    if not food.get("can_cook", False):
        return f"❌ {food.get('name', food_id)} нельзя приготовить!"

    cooked_id = food.get("cooked")
    if not cooked_id:
        return f"❌ Нет рецепта для {food.get('name', food_id)}!"

    if food_id not in player.food_inventory:
        return f"❌ У вас нет {food.get('name', food_id)} для приготовления!"

    cooked = get_food(cooked_id)
    if not cooked:
        return f"❌ Ошибка: приготовленный продукт не найден!"

    # Опасность при готовке на опасной станции
    if campfire_type == "danger":
        roll = random.randint(1, 100)
        if roll <= 30:
            from .combat import combat_manager
            from .map_data import MAP_DATA
            danger_level = MAP_DATA["станции"][player.location].get("danger", 3)
            combat_manager.start_combat(player, danger_level + 1, None)
            return "⚠️ **ВНИМАНИЕ!** На запах еды прибежал мутант!\n⚔️ Начинается бой!"

    # Готовим
    player.food_inventory.remove(food_id)
    player.food_inventory.append(cooked_id)

    await save_player(player)

    logger.info(f"🍳 {player.name} приготовил {cooked.get('name', cooked_id)}")

    return f"🍳 **{player.name}** приготовил {cooked.get('emoji', '🍖')} **{cooked.get('name', cooked_id)}**! (+{cooked.get('stamina', 0)} выносливости вместо {food.get('stamina', 0)})"


async def cook_at_campfire(interaction, player, campfire_type: str = "safe") -> str:
    cookable = []
    for food_id in player.food_inventory:
        if can_cook(food_id):
            cookable.append(food_id)

    if not cookable:
        return "❌ У вас нет продуктов, которые можно приготовить!"

    result = "🍳 **Доступно для приготовления:**\n\n"
    for food_id in cookable:
        food = get_food(food_id)
        cooked_id = get_cooked_version(food_id)
        cooked = get_food(cooked_id)
        if food and cooked:
            result += f"{food.get('emoji', '🍖')} **{food.get('name', food_id)}** → {cooked.get('emoji', '🍖')} **{cooked.get('name', cooked_id)}** (+{cooked.get('stamina', 0)} выносливости)\n"

    return result


def get_food_categories() -> dict:
    categories = {}
    for food_id, food_data in FOOD["foods"].items():
        if food_data.get("can_cook", False):
            cat = "сырые"
        elif "жареный" in food_data.get("name", "") or "жареное" in food_data.get("name", ""):
            cat = "жареные"
        else:
            cat = "готовые"

        if cat not in categories:
            categories[cat] = []
        categories[cat].append(food_id)

    return categories