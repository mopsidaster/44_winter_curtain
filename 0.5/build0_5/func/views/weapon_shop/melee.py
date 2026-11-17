# -*- coding: utf-8 -*-
# func/views/weapon_shop/melee.py - Меню покупки оружия ближнего боя (0.4.8)
#
# ИСТОРИЯ:
#   0.4.4.6 — рефакторинг
#   0.4.7.6.1 — защита от не-dict
#   0.4.8 — скидка фракции

import discord
import uuid

from ..helpers import (
    game_manager, save_player, get_trade_discount,
)
from ...factions import get_station_discount
from ...melee_system import get_melee_weapon, get_available_melee_weapons
from utils.logger import get_logger

logger = get_logger()


def _get_discount(player) -> float:
    try:
        return get_trade_discount(game_manager) * get_station_discount(player, player.location)
    except Exception:
        return get_trade_discount(game_manager)


class MeleeBuyMenu(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def build_embed(self) -> discord.Embed:
        """Возвращает готовый embed для меню ближнего боя."""
        discount = _get_discount(self.player)
        embed = discord.Embed(
            title="🗡️ Оружие ближнего боя",
            description="Выберите оружие:",
            color=discord.Color.red()
        )

        available = get_available_melee_weapons()
        for weapon_id in available:
            weapon = get_melee_weapon(weapon_id)
            if not isinstance(weapon, dict):
                continue

            is_current = self.player.melee_weapon == weapon_id
            price = int(weapon.get('price', 0) * discount)
            weapon_type = weapon.get('type', 'тупое')
            type_emoji = "⚔️" if weapon_type == "острое" else "🔨"
            stun = weapon.get('stun_chance', 0)
            stun_text = f" | Оглушение: {stun}%" if stun > 0 else ""
            durability = weapon.get('max_durability', 999)
            durability_text = "∞" if durability >= 999 else str(durability)

            embed.add_field(
                name=f"{'✅ ' if is_current else ''}{weapon.get('emoji', '🗡️')} {weapon.get('name', weapon_id)}",
                value=f"{type_emoji} {weapon_type}{stun_text}\n"
                      f"Урон: {weapon.get('damage', 1.0)} | Точность: {weapon.get('accuracy', 70)}%\n"
                      f"Прочность: {durability_text} | Цена: {price} никелей",
                inline=False
            )
        return embed

    def _add_buttons(self):
        available = get_available_melee_weapons()
        for idx, weapon_id in enumerate(available):
            weapon = get_melee_weapon(weapon_id)
            if not isinstance(weapon, dict):
                logger.warning(
                    f"[MELEE] '{weapon_id}' — не dict: {type(weapon)}"
                )
                continue

            is_current = self.player.melee_weapon == weapon_id
            label = f"{weapon.get('emoji', '🗡️')} {weapon.get('name', weapon_id)}"
            if is_current:
                label = f"✅ {label}"

            button = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.primary if not is_current else discord.ButtonStyle.success,
                custom_id=f"buy_melee_{self.menu_id}_{idx}"
            )
            button.callback = self.create_callback(weapon_id)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.secondary,
            custom_id=f"melee_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_callback(self, weapon_id: str):
        async def callback(interaction: discord.Interaction):
            try:
                if interaction.user.id != self.player.user_id:
                    await interaction.response.send_message("❌ Не ваш аккаунт!", ephemeral=True)
                    return

                await interaction.response.defer()

                weapon = get_melee_weapon(weapon_id)
                if not isinstance(weapon, dict):
                    await interaction.followup.send(
                        f"❌ Ошибка данных оружия '{weapon_id}'",
                        ephemeral=True
                    )
                    logger.error(f"[MELEE] weapon '{weapon_id}' — не dict: {type(weapon)}")
                    return

                discount = _get_discount(self.player)
                final_price = int(weapon.get('price', 0) * discount)

                if self.player.inventory['никели'] < final_price:
                    await interaction.followup.send(
                        f"❌ Нужно {final_price} никелей!",
                        ephemeral=True
                    )
                    return
                if self.player.melee_weapon == weapon_id:
                    await interaction.followup.send(
                        "❌ У вас уже есть это оружие!",
                        ephemeral=True
                    )
                    return

                old_melee = self.player.melee_weapon
                if old_melee and old_melee != weapon_id and old_melee != "кулаки":
                    if old_melee not in self.player.melee_inventory:
                        self.player.melee_inventory.append(old_melee)

                self.player.inventory['никели'] -= final_price
                self.player.melee_weapon = weapon_id
                self.player.melee_weapon_durability = weapon.get('max_durability', 999)
                await save_player(self.player)

                durability = weapon.get('max_durability', 999)
                durability_text = "∞" if durability >= 999 else str(durability)

                await interaction.followup.send(
                    f"✅ Купили **{weapon.get('name', weapon_id)}** "
                    f"за {final_price} никелей!\n"
                    f"🔧 Прочность: {durability_text}",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ Ошибка в melee buy_callback ({weapon_id}): {e}")
                import traceback
                logger.error(traceback.format_exc())
                try:
                    await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
                except Exception:
                    pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш магазин!", ephemeral=True)
                return

            await interaction.response.defer()

            embed = discord.Embed(
                title="🔫 Оружейный магазин",
                description="Выберите раздел:",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📋 Доступные разделы",
                value="• 🔫 **Оружие**\n• 📀 **Магазины**\n• 🎯 **Патроны**\n"
                      "• 🔧 **Модификации**\n• 🗡️ **Ближний бой**\n• 💣 **Расходники**",
                inline=False
            )
            from .main_menu import WeaponShopMainMenu
            view = WeaponShopMainMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Ошибка back (melee): {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback (melee): {e}")