# -*- coding: utf-8 -*-
# func/views/independent_trader_view.py - Окно независимого торговца (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.8.7 — новый файл. Ганс и Радеон, вкладки Купить / Продать /
#             Задания / Лояльность.

import discord
import uuid

from config.map_config import WEAPONS, MODULES, ARMOR, AMMO
from ..independent_traders import (
    get_trader, get_trader_name, get_trader_emoji,
    get_player_trader_loyalty, get_player_trader_loyalty_level,
    get_trader_loyalty_progress,
    get_visible_items, get_trader_price,
    get_ammo_caliber_from_item,
    get_trader_board, claim_trader_task,
    format_trader_task,
    add_player_trader_loyalty,
)
from ..pharmacy_system import get_inventory_key
from database.db import save_player
from .helpers import game_manager
from utils.logger import get_logger

logger = get_logger()


class IndependentTraderView(discord.ui.View):
    def __init__(self, player, trader_id: str, page: str = "buy"):
        super().__init__(timeout=180)
        self.player = player
        self.trader_id = trader_id
        self.page = page
        self.menu_id = uuid.uuid4().hex[:8]
        self._build()

    def _build(self):
        self.clear_items()

        if self.page == "buy":
            self._add_nav_buttons(active="buy")
        elif self.page == "sell":
            self._add_nav_buttons(active="sell")
        elif self.page == "tasks":
            self._add_nav_buttons(active="tasks")
        elif self.page == "loyalty":
            self._add_nav_buttons(active="loyalty")

    def _add_nav_buttons(self, active: str):
        tabs = [
            ("buy", "🛒 Купить", discord.ButtonStyle.success),
            ("sell", "💰 Продать", discord.ButtonStyle.primary),
            ("tasks", "📋 Задания", discord.ButtonStyle.primary),
            ("loyalty", "💠 Лояльность", discord.ButtonStyle.secondary),
        ]

        for idx, (pid, label, style) in enumerate(tabs):
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.success if active == pid else style,
                custom_id=f"t_{pid}_{self.menu_id}",
                row=0,
                disabled=(active == pid),
            )
            btn.callback = self.create_tab_callback(pid)
            self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад к диалогу",
            style=discord.ButtonStyle.danger,
            custom_id=f"t_back_{self.menu_id}",
            row=4,
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

        # Кнопки действий под вкладку
        if active == "buy":
            items = get_visible_items(self.player, self.trader_id)
            for idx, (item_id, kind) in enumerate(items[:10]):
                if kind == "weapon":
                    w = WEAPONS.get(item_id, {})
                    label = f"🔫 {w.get('name', item_id)}"
                elif kind == "module":
                    m = MODULES.get('modules', {}).get(item_id, {})
                    label = f"🔧 {m.get('name', item_id)}"
                elif kind == "armor":
                    a = ARMOR.get('armor_sets', {}).get(item_id, {})
                    label = f"🧥 {a.get('name', item_id)}"
                elif kind == "ammo_caliber":
                    cal = get_ammo_caliber_from_item(item_id)
                    cal_data = AMMO.get('calibers', {}).get(cal, {})
                    label = f"🎯 Патроны {cal_data.get('name', cal)}"
                else:
                    label = item_id

                btn = discord.ui.Button(
                    label=label[:80],
                    style=discord.ButtonStyle.success,
                    custom_id=f"t_buy_{self.menu_id}_{idx}",
                    row=1 + (idx // 5),
                )
                btn.callback = self.create_buy_callback(item_id, kind)
                self.add_item(btn)

        elif active == "tasks":
            board = get_trader_board(self.trader_id)
            for idx, task in enumerate(board[:3]):
                btn = discord.ui.Button(
                    label=f"📋 Задание #{idx + 1}",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"t_task_{self.menu_id}_{idx}",
                    row=1 + (idx // 3),
                )
                btn.callback = self.create_task_callback(task)
                self.add_item(btn)

    # ==================== NAV ====================

    def create_tab_callback(self, page: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message(
                    "❌ Не ваше окно!", ephemeral=True
                )
                return

            new_view = IndependentTraderView(
                self.player, self.trader_id, page=page
            )
            embed = new_view.build_embed()
            await interaction.response.edit_message(embed=embed, view=new_view)
        return callback

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message(
                "❌ Не ваше окно!", ephemeral=True
            )
            return

        from .faction_npc.dialog_view import DialogView
        npc_map = {"ганс": "ганс", "радеон": "радеон"}
        npc_id = npc_map.get(self.trader_id, self.trader_id)
        try:
            new_view = DialogView(self.player.user_id, npc_id, "greeting")
            await interaction.response.edit_message(
                embed=new_view.build_embed(), view=new_view
            )
        except Exception as e:
            logger.error(f"[TRADER] back: {e}")

    # ==================== BUY ====================

    def create_buy_callback(self, item_id: str, kind: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return

            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()

                if kind == "weapon":
                    w = WEAPONS.get(item_id, {})
                    price = get_trader_price(
                        w.get('price', 0), self.player, self.trader_id
                    )
                    if self.player.inventory.get("никели", 0) < price:
                        await interaction.followup.send(
                            f"❌ Нужно {price} никелей!",
                            ephemeral=True,
                        )
                        return
                    self.player.inventory["никели"] -= price
                    if item_id not in self.player.weapons_inventory \
                            and item_id != self.player.weapon:
                        self.player.weapons_inventory.append(item_id)
                    await save_player(self.player)
                    await interaction.followup.send(
                        f"✅ Куплено **{w.get('name', item_id)}** за {price}",
                        ephemeral=True,
                    )

                elif kind == "module":
                    m = MODULES.get('modules', {}).get(item_id, {})
                    price = get_trader_price(
                        m.get('price', 0), self.player, self.trader_id
                    )
                    if self.player.inventory.get("никели", 0) < price:
                        await interaction.followup.send(
                            f"❌ Нужно {price} никелей!",
                            ephemeral=True,
                        )
                        return
                    self.player.inventory["никели"] -= price
                    if item_id not in self.player.modules_inventory:
                        self.player.modules_inventory.append(item_id)
                    await save_player(self.player)
                    await interaction.followup.send(
                        f"✅ Куплено **{m.get('name', item_id)}** за {price}",
                        ephemeral=True,
                    )

                elif kind == "armor":
                    a = ARMOR.get('armor_sets', {}).get(item_id, {})
                    price = get_trader_price(
                        a.get('price', 0), self.player, self.trader_id
                    )
                    if self.player.inventory.get("никели", 0) < price:
                        await interaction.followup.send(
                            f"❌ Нужно {price} никелей!",
                            ephemeral=True,
                        )
                        return
                    self.player.inventory["никели"] -= price
                    if item_id not in self.player.armor_inventory:
                        self.player.armor_inventory.append(item_id)
                    await save_player(self.player)
                    await interaction.followup.send(
                        f"✅ Куплено **{a.get('name', item_id)}** за {price}",
                        ephemeral=True,
                    )

                elif kind == "ammo_caliber":
                    cal = get_ammo_caliber_from_item(item_id)
                    cal_data = AMMO.get('calibers', {}).get(cal, {})
                    types = cal_data.get('types', [])
                    if not types:
                        await interaction.followup.send(
                            "❌ Нет типов патронов.", ephemeral=True
                        )
                        return
                    # Покупаем по 10 первого типа
                    atype = types[0]
                    from ..weapon_system.ammo import make_ammo_key
                    from config.map_config import BALANCE as _B
                    base_price = _B.get('prices', {}).get('ammo', {}).get(cal, {}).get(atype, 10)
                    price = get_trader_price(base_price, self.player, self.trader_id) * 10
                    if self.player.inventory.get("никели", 0) < price:
                        await interaction.followup.send(
                            f"❌ Нужно {price} никелей!", ephemeral=True
                        )
                        return
                    self.player.inventory["никели"] -= price
                    inv_key = make_ammo_key(cal, atype)
                    self.player.inventory[inv_key] = (
                            self.player.inventory.get(inv_key, 0) + 10
                    )
                    await save_player(self.player)
                    await interaction.followup.send(
                        f"✅ Куплено 10 × {atype} ({cal}) за {price}",
                        ephemeral=True,
                    )

                else:
                    await interaction.followup.send(
                        "❌ Неизвестный тип товара.", ephemeral=True
                    )
                    return

                new_view = IndependentTraderView(
                    self.player, self.trader_id, page="buy"
                )
                try:
                    await interaction.edit_original_response(
                        embed=new_view.build_embed(), view=new_view
                    )
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"[TRADER] buy {item_id}: {e}", exc_info=True)
                try:
                    await interaction.followup.send(
                        f"❌ Ошибка: {e}", ephemeral=True
                    )
                except Exception:
                    pass

        return callback

    # ==================== TASKS ====================

    def create_task_callback(self, task: dict):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return

            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()

                task_id = task.get("task_id")
                existing = next(
                    (t for t in (getattr(self.player, 'active_tasks', []) or [])
                     if t.get("task_id") == task_id),
                    None,
                )

                if existing is None:
                    # Взять задание
                    new_task = dict(task)
                    new_task["progress"] = 0
                    new_task["completed"] = False
                    new_task["ready_to_claim"] = False

                    if new_task.get("type") == "delivery":
                        cargo_id = new_task.get("cargo_id")
                        if cargo_id:
                            hlam = self.player.inventory.get("хлам", []) or []
                            hlam.append(cargo_id)
                            self.player.inventory["хлам"] = hlam

                    self.player.add_task(new_task)
                    await save_player(self.player)
                    await interaction.followup.send(
                        f"✅ Задание взято:\n{format_trader_task(new_task)}",
                        ephemeral=True,
                    )
                else:
                    # Сдать задание
                    ok, message = claim_trader_task(
                        self.player, self.trader_id, task_id
                    )
                    await save_player(self.player)
                    await interaction.followup.send(message, ephemeral=True)

                new_view = IndependentTraderView(
                    self.player, self.trader_id, page="tasks"
                )
                try:
                    await interaction.edit_original_response(
                        embed=new_view.build_embed(), view=new_view
                    )
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"[TRADER] task: {e}", exc_info=True)
                try:
                    await interaction.followup.send(
                        f"❌ Ошибка: {e}", ephemeral=True
                    )
                except Exception:
                    pass

        return callback

    # ==================== EMBED ====================

    def build_embed(self) -> discord.Embed:
        trader = get_trader(self.trader_id)
        name = get_trader_name(self.trader_id)
        emoji = get_trader_emoji(self.trader_id)

        embed = discord.Embed(
            title=f"{emoji} {name}",
            description=trader.get("description", ""),
            color=discord.Color.dark_gold(),
        )

        progress = get_trader_loyalty_progress(self.player, self.trader_id)
        lvl = progress["level"]
        points = progress["points"]

        embed.add_field(
            name="💠 Лояльность",
            value=f"Ур. **{lvl}/2** • **{points}** очков",
            inline=True,
        )

        # Что открыто на текущем уровне
        trader_data = get_trader(self.trader_id)
        levels = trader_data.get("loyalty_levels", {})
        current_bonus = levels.get(str(lvl), {}).get("description", "—")
        embed.add_field(name="🎁 Бонус", value=current_bonus, inline=False)

        if self.page == "buy":
            items = get_visible_items(self.player, self.trader_id)
            if not items:
                embed.add_field(
                    name="🛒 Ассортимент",
                    value="_Нет доступных товаров на вашем уровне лояльности._",
                    inline=False,
                )
            else:
                lines = []
                for item_id, kind in items:
                    if kind == "weapon":
                        w = WEAPONS.get(item_id, {})
                        price = get_trader_price(
                            w.get('price', 0), self.player, self.trader_id
                        )
                        lines.append(f"🔫 {w.get('name', item_id)} — {price} ник.")
                    elif kind == "module":
                        m = MODULES.get('modules', {}).get(item_id, {})
                        price = get_trader_price(
                            m.get('price', 0), self.player, self.trader_id
                        )
                        lines.append(f"🔧 {m.get('name', item_id)} — {price} ник.")
                    elif kind == "armor":
                        a = ARMOR.get('armor_sets', {}).get(item_id, {})
                        price = get_trader_price(
                            a.get('price', 0), self.player, self.trader_id
                        )
                        lines.append(f"🧥 {a.get('name', item_id)} — {price} ник.")
                    elif kind == "ammo_caliber":
                        cal = get_ammo_caliber_from_item(item_id)
                        cal_data = AMMO.get('calibers', {}).get(cal, {})
                        types = cal_data.get('types', [])
                        if types:
                            from config.map_config import BALANCE as _B
                            base = _B.get('prices', {}).get('ammo', {}).get(cal, {}).get(types[0], 10)
                            price = get_trader_price(base, self.player, self.trader_id)
                            lines.append(
                                f"🎯 Патроны {cal_data.get('name', cal)} "
                                f"({types[0]}) — {price} ник./шт"
                            )
                embed.add_field(
                    name="🛒 Ассортимент (нажмите кнопку)",
                    value="\n".join(lines[:12]),
                    inline=False,
                )

        elif self.page == "sell":
            hlam = self.player.inventory.get("хлам", []) or []
            if not hlam:
                embed.add_field(
                    name="💰 Продажа",
                    value="_У вас нет хлама._",
                    inline=False,
                )
            else:
                counts = {}
                for item in hlam:
                    counts[item] = counts.get(item, 0) + 1
                from config.map_config import ITEMS
                lines = []
                for item_id, cnt in counts.items():
                    data = ITEMS.get('sell', {}).get(item_id, {})
                    base_price = data.get('price', 1)
                    # Бонус: Ганс — ×2 для лута, Радеон — +20%
                    if self.trader_id == "ганс":
                        price = int(base_price * 2.0)
                    elif self.trader_id == "радеон":
                        price = int(base_price * 1.2)
                    else:
                        price = base_price
                    name = data.get('name', item_id)
                    lines.append(f"• {name} ×{cnt} — {price} ник./шт")
                embed.add_field(
                    name="💰 Хлам для продажи (кнопка «Продать всё»)",
                    value="\n".join(lines[:10]),
                    inline=False,
                )
                # Кнопка продажи
                sell_btn = discord.ui.Button(
                    label="💰 Продать всё",
                    style=discord.ButtonStyle.success,
                    custom_id=f"t_sellall_{self.menu_id}",
                    row=3,
                )
                sell_btn.callback = self.sell_all_callback()
                self.add_item(sell_btn)

        elif self.page == "tasks":
            board = get_trader_board(self.trader_id)
            active = getattr(self.player, 'active_tasks', []) or []
            active_ids = {t.get("task_id"): t for t in active}

            if not board:
                embed.add_field(
                    name="📋 Задания",
                    value="_Нет доступных заданий._",
                    inline=False,
                )
            else:
                for idx, task in enumerate(board[:3]):
                    tid = task.get("task_id")
                    ex = active_ids.get(tid)
                    status = "📋 Доступно"
                    if ex:
                        if ex.get("completed"):
                            status = "✅ Выполнено"
                        elif ex.get("ready_to_claim"):
                            status = "🎁 Готово к сдаче"
                        else:
                            status = "⏳ В процессе"
                    embed.add_field(
                        name=f"Задание #{idx + 1} ({status})",
                        value=format_trader_task(task),
                        inline=False,
                    )

        elif self.page == "loyalty":
            trader_data = get_trader(self.trader_id)
            levels = trader_data.get("loyalty_levels", {})
            lines = []
            for lvl_str in ("0", "1", "2"):
                lvl_data = levels.get(lvl_str, {})
                pts = lvl_data.get("points", 0)
                desc = lvl_data.get("description", "")
                mark = "✅" if lvl >= int(lvl_str) else "🔒"
                lines.append(f"{mark} **Ур. {lvl_str}** ({pts} очк.): {desc}")
            embed.add_field(
                name="📈 Уровни лояльности",
                value="\n".join(lines),
                inline=False,
            )
            if progress.get("next_threshold"):
                remaining = progress["next_threshold"] - points
                embed.add_field(
                    name="📊 До следующего уровня",
                    value=f"**{remaining}** очков",
                    inline=True,
                )

        embed.set_footer(
            text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)}"
        )
        return embed

    # ==================== SELL ALL ====================

    def sell_all_callback(self):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                return

            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()

                hlam = self.player.inventory.get("хлам", []) or []
                if not hlam:
                    await interaction.followup.send(
                        "❌ Нет хлама для продажи.", ephemeral=True
                    )
                    return

                from config.map_config import ITEMS

                total = 0
                sold = []
                remaining = []

                for item in hlam:
                    # Не продаём грузы и пропуска
                    if item.startswith("груз_") or item in (
                            "временный_пропуск", "постоянный_пропуск"
                    ):
                        remaining.append(item)
                        continue

                    data = ITEMS.get('sell', {}).get(item)
                    if not data:
                        remaining.append(item)
                        continue

                    base_price = data.get('price', 1)
                    if self.trader_id == "ганс":
                        price = int(base_price * 2.0)
                    elif self.trader_id == "радеон":
                        price = int(base_price * 1.2)
                    else:
                        price = base_price

                    total += price
                    sold.append(data.get('name', item))

                if not sold:
                    await interaction.followup.send(
                        "❌ Нечего продавать.", ephemeral=True
                    )
                    return

                self.player.inventory["хлам"] = remaining
                self.player.inventory["никели"] = (
                        self.player.inventory.get("никели", 0) + total
                )
                await save_player(self.player)

                await interaction.followup.send(
                    f"💰 Продано: {', '.join(sold)}\n"
                    f"Получено: **{total}** никелей",
                    ephemeral=True,
                )

                new_view = IndependentTraderView(
                    self.player, self.trader_id, page="sell"
                )
                try:
                    await interaction.edit_original_response(
                        embed=new_view.build_embed(), view=new_view
                    )
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"[TRADER] sell_all: {e}", exc_info=True)
                try:
                    await interaction.followup.send(
                        f"❌ Ошибка: {e}", ephemeral=True
                    )
                except Exception:
                    pass

        return callback