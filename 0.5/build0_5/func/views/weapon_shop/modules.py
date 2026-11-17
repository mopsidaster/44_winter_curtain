# -*- coding: utf-8 -*-
# func/views/weapon_shop/modules.py - Меню модулей (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.4.6 — рефакторинг
#   0.4.8 — скидка фракции
#   0.4.8.7 — фильтр trader_only (ACOG, T1, эм-модули — только у торговцев)

import discord
import uuid

from ..helpers import (
    game_manager, save_player, get_trade_discount,
)
from ...factions import get_station_discount
from config.map_config import MODULES
from utils.logger import get_logger

from ._helpers import SLOT_PAGES, get_modules_by_slot

logger = get_logger()


def _get_discount(player) -> float:
    try:
        return (
                get_trade_discount(game_manager)
                * get_station_discount(player, player.location)
        )
    except Exception:
        return get_trade_discount(game_manager)


def _is_trader_only(module_id: str) -> bool:
    """0.4.8.7: модуль только у торговца — не показывать в общей торговле."""
    mdata = MODULES.get('modules', {}).get(module_id, {})
    return bool(mdata.get("trader_only"))


def _get_available_modules(slot_id: str) -> list:
    all_mods = get_modules_by_slot(slot_id)
    return [m for m in all_mods if not _is_trader_only(m)]


class ModuleSlotMenu(discord.ui.View):
    def __init__(self, player, current_slot: str = "scope"):
        super().__init__(timeout=120)
        self.player = player
        self.current_slot = current_slot
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        self.clear_items()

        for idx, (slot_id, slot_data) in enumerate(SLOT_PAGES.items()):
            is_current = (slot_id == self.current_slot)
            count = len(_get_available_modules(slot_id))
            if count == 0:
                continue

            button = discord.ui.Button(
                label=f"{slot_data['emoji']} {slot_data['name']} ({count})",
                style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.secondary,
                custom_id=f"mslot_{self.menu_id}_{idx}",
                row=0,
                disabled=is_current
            )
            button.callback = self.create_slot_callback(slot_id)
            self.add_item(button)

        modules = _get_available_modules(self.current_slot)

        if not modules:
            button = discord.ui.Button(
                label="❌ Нет модулей этого слота",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"mslot_empty_{self.menu_id}",
                row=1
            )
            self.add_item(button)
        else:
            for idx, module_id in enumerate(modules[:6]):
                module_data = MODULES['modules'].get(module_id, {})
                if not isinstance(module_data, dict):
                    continue

                owned = module_id in self.player.modules_inventory

                label = f"{module_data.get('emoji', '🔧')} {module_data.get('name', module_id)}"
                if owned:
                    label = f"✅ {label}"

                button = discord.ui.Button(
                    label=label[:80],
                    style=discord.ButtonStyle.success if owned else discord.ButtonStyle.primary,
                    custom_id=f"mbuy_{self.menu_id}_{idx}",
                    row=1 + (idx // 3),
                    disabled=owned
                )
                button.callback = self.create_buy_callback(module_id)
                self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 К разделам",
            style=discord.ButtonStyle.danger,
            custom_id=f"mslot_back_{self.menu_id}",
            row=3
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def get_embed(self, slot_id: str) -> discord.Embed:
        slot_data = SLOT_PAGES.get(slot_id, {})
        modules = _get_available_modules(slot_id)
        discount = _get_discount(self.player)

        embed = discord.Embed(
            title=f"{slot_data.get('emoji', '🔧')} Модификации: {slot_data.get('name', slot_id)}",
            description=slot_data.get('description', ''),
            color=discord.Color.green()
        )

        if not modules:
            embed.add_field(name="📭 Пусто", value="Модулей этого слота пока нет.", inline=False)
            return embed

        for module_id in modules:
            module_data = MODULES['modules'].get(module_id, {})
            if not isinstance(module_data, dict):
                continue

            price = int(module_data.get('price', 0) * discount)
            owned = module_id in self.player.modules_inventory

            acc = module_data.get('accuracy', {})
            acc_text = (f"Б: +{acc.get('close', 0) * 100:.0f}% | "
                        f"С: +{acc.get('medium', 0) * 100:.0f}% | "
                        f"Д: +{acc.get('far', 0) * 100:.0f}%")

            mod_type = module_data.get('type', 'all')
            type_names = {
                "all": "✅ Все оружия",
                "all_wo_pistol": "⚠️ Без пистолетов",
                "all_wo_shotgun": "⚠️ Без дробовиков",
                "all_wo_pistol_and_shotgun": "⚠️ Без пистолетов и дробовиков",
                "all_wo_pistol_and_sniper": "⚠️ Без пистолетов и снайперок",
                "assault": "💥 Только автоматы",
                "assault_smg": "💥🔫 Только автоматы и ПП",
                "sniper": "🎯 Только снайперки",
                "shotgun": "🔫 Только дробовики",
                "shotgun_and_assault": "💥🔫 Дробовики и автоматы",
                "mg_only": "🔫 Только пулемёты",
            }
            type_text = type_names.get(mod_type, mod_type)

            special = module_data.get('special')
            special_text = ""
            if special and 'proc_chance' in special:
                special_text = f"\n⚡ Срабатывает с шансом {int(special['proc_chance'] * 100)}%"
            if special and 'enemy_hit_bonus' in special:
                special_text = f"\n⚠️ Враг получает +{special['enemy_hit_bonus']}% к точности"

            acc_by_weapon = module_data.get('accuracy_by_weapon')
            if acc_by_weapon:
                acc_by_lines = []
                for wtype, dists in acc_by_weapon.items():
                    acc_by_lines.append(
                        f"   ({wtype}) Б: +{dists.get('close', 0) * 100:.0f}%, "
                        f"С: +{dists.get('medium', 0) * 100:.0f}%, "
                        f"Д: +{dists.get('far', 0) * 100:.0f}%"
                    )
                acc_text += "\n" + "\n".join(acc_by_lines)

            owned_mark = "✅ **КУПЛЕНО**\n" if owned else ""

            slots_note = ""
            if module_data.get('slots') and len(module_data['slots']) > 1:
                slots_note = f"\n🔧 Занимает слоты: {', '.join(module_data['slots'])}"

            headshot_bonus = module_data.get('headshot_accuracy', 0)
            if headshot_bonus:
                acc_text += f"\n🎯 Бонус в голову: +{headshot_bonus}%"

            damage_bonus = module_data.get('damage_bonus', 0)
            dmg_note = ""
            if damage_bonus:
                dmg_note = f"\n💥 Урон: +{damage_bonus}"

            allowed = module_data.get('allowed_weapons')
            allowed_note = ""
            if isinstance(allowed, list) and allowed:
                names = [MODULES.get("modules", {}).get(m, {}).get("name", m) for m in allowed]
                allowed_note = f"\n🔒 Только: {', '.join(names)}"

            embed.add_field(
                name=f"{module_data.get('emoji', '🔧')} {module_data.get('name', module_id)}",
                value=f"{owned_mark}"
                      f"🔧 Тип: {type_text}\n"
                      f"🎯 Точность: {acc_text}{special_text}{slots_note}{dmg_note}{allowed_note}\n"
                      f"💰 Цена: **{price}** никелей" +
                      (f" ~~{module_data.get('price', 0)}~~ 🔥" if discount < 1.0 else ""),
                inline=False
            )

        return embed

    def create_slot_callback(self, slot_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                    return

                await interaction.response.defer()

                self.current_slot = slot_id
                new_view = ModuleSlotMenu(self.player, current_slot=slot_id)
                embed = new_view.get_embed(slot_id)

                try:
                    await interaction.edit_original_response(embed=embed, view=new_view)
                except Exception as e:
                    logger.error(f"Ошибка смены слота: {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в slot_callback ({slot_id}): {e}")

        return callback

    def create_buy_callback(self, module_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                    return

                await interaction.response.defer()

                module_data = MODULES['modules'].get(module_id)
                if not module_data:
                    await interaction.followup.send("❌ Модуль не найден!", ephemeral=True)
                    return

                discount = _get_discount(self.player)
                final_price = int(module_data.get('price', 0) * discount)

                if self.player.inventory['никели'] < final_price:
                    await interaction.followup.send(f"❌ Нужно {final_price} никелей!", ephemeral=True)
                    return
                if module_id in self.player.modules_inventory:
                    await interaction.followup.send("❌ У вас уже есть этот модуль!", ephemeral=True)
                    return

                self.player.inventory['никели'] -= final_price
                self.player.modules_inventory.append(module_id)
                await save_player(self.player)

                await interaction.followup.send(
                    f"✅ Купили **{module_data.get('name', module_id)}** за {final_price} никелей!\n"
                    f"🔧 Модуль в инвентаре.",
                    ephemeral=True
                )

                new_view = ModuleSlotMenu(self.player, current_slot=self.current_slot)
                embed = new_view.get_embed(self.current_slot)
                try:
                    await interaction.edit_original_response(embed=embed, view=new_view)
                except Exception as e:
                    logger.error(f"Ошибка edit после покупки модуля: {e}")

            except Exception as e:
                logger.error(f"❌ Ошибка в module buy_callback ({module_id}): {e}")

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                return

            await interaction.response.defer()

            embed = discord.Embed(title="🔫 Оружейный магазин", description="Выберите раздел:", color=discord.Color.blue())
            embed.add_field(
                name="📋 Доступные разделы",
                value="• 🔫 **Оружие**\n• 📀 **Магазины**\n• 🎯 **Патроны**\n• 🔧 **Модификации**\n• 🗡️ **Ближний бой**\n• 💣 **Расходники**",
                inline=False
            )
            from .main_menu import WeaponShopMainMenu
            view = WeaponShopMainMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка back (module slot): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (module slot): {e}")