# -*- coding: utf-8 -*-
# func/views/main_menu.py - Главное меню (0.4.9.0 Visual Update)

import discord
from .helpers import (
    game_manager, MAP_DATA, show_map, BALANCE, WEAPONS, ITEMS, MAGAZINES, AMMO, FOOD, FILTERS,
    save_player, get_inventory_embed, get_trade_discount, get_stamina_multiplier, can_move,
    combat_manager, get_current_filter_info, build_progress_bar
)
from .status import StatusView
from .action_menu import ActionMenu
from .look_around import LookAroundMenu
from .combat_views import CombatView
from .social.sleep_view import SleepingMenuView, build_sleeping_embed
from ..food_system import get_food, format_food_inventory
from ..melee_system import get_melee_weapon, get_melee_weapon_name, get_melee_weapon_emoji
from ..station_utils import is_trade_station
from ..factions import get_npcs_on_station

def build_main_embed(player, station_data) -> discord.Embed:
    total_hp = player.get_total_health()
    max_hp = player.get_max_total_health()
    stamina = player.stamina
    max_stamina = player.max_stamina

    # Генерируем красивые полоски
    hp_bar = build_progress_bar(total_hp, max_hp, length=12)
    stamina_bar = build_progress_bar(stamina, max_stamina, length=12)

    # Динамический цвет фона
    if not player.is_alive:
        color = discord.Color.dark_gray()
    elif total_hp / max_hp < 0.3:
        color = discord.Color.dark_red()
    elif total_hp / max_hp < 0.6:
        color = discord.Color.orange()
    else:
        color = discord.Color.dark_blue()

    embed = discord.Embed(
        title=f"🎮 ПЛАНШЕТ: {player.name.upper()}",
        description=(
            f"**Уровень:** ` {player.level} ` | **Опыт:** ` {player.xp}/{player.xp_to_next} `\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=color
    )

    if not player.is_alive:
        embed.description += "\n💀 **ВЫ МЕРТВЫ. ПЕРСОНАЖ УДАЛЕН.**"

    # Блок здоровья
    hp_icon = "🟢" if total_hp/max_hp > 0.6 else ("🟡" if total_hp/max_hp > 0.3 else "🔴")
    embed.add_field(
        name=f"{hp_icon} Здоровье",
        value=f"`{hp_bar}` **{total_hp:.1f}** / {max_hp:.1f} HP",
        inline=False
    )

    # Блок выносливости
    stamina_icon = "⚡" if stamina > 2 else "🥱"
    embed.add_field(
        name=f"{stamina_icon} Выносливость",
        value=f"`{stamina_bar}` **{stamina:.1f}** / {max_stamina:.1f}",
        inline=False
    )

    # Блок локации
    danger = station_data.get("danger", 0)
    danger_emoji = {0: "🟢", 1: "🟡", 2: "🟠", 3: "🔴", 4: "💀", 5: "☠️"}.get(danger, "⬤")
    embed.add_field(
        name="📍 Локация",
        value=f"{danger_emoji} **{station_data['name']}**",
        inline=True
    )
    embed.add_field(name="💰 Никели", value=f"**{player.inventory.get('никели', 0)}**", inline=True)

    # Блок экипировки
    w_data = WEAPONS.get(player.weapon)
    m_data = get_melee_weapon(player.melee_weapon)

    equip_text = ""
    if w_data:
        equip_text += f"🔫 {w_data.get('name', 'Нет')}\n"
    if m_data:
        equip_text += f"🗡️ {m_data.get('name', 'Кулаки')}\n"

    embed.add_field(name="🎒 Снаряжение", value=equip_text if equip_text else "Пусто", inline=True)

    # Блок группы (если есть)
    from ..social.brigade_manager import brigade_manager
    brigade = brigade_manager.get_user_brigade(player.user_id)
    if brigade:
        role = "👑 Лидер" if brigade.is_leader(player.user_id) else "👤 Рядовой"
        state = "🚶 Вместе" if brigade.is_active() else "🔀 Расход"
        embed.add_field(
            name="🤝 Бригада",
            value=f"**{brigade.name}**\n{role} | {state} ({brigade.member_count()}/3)",
            inline=True,
        )

    embed.set_footer(text="44: WHITE CURTAIN | Выберите действие ниже")
    return embed


class MainMenu(discord.ui.View):
    def __init__(self, player=None):
        super().__init__(timeout=None)
        self.player = player
        self._add_buttons()

    def _add_buttons(self):
        self.clear_items()

        # РЯД 0
        btn_actions = discord.ui.Button(label="Действия", emoji="🎯", style=discord.ButtonStyle.success, row=0)
        btn_actions.callback = self.action_callback
        self.add_item(btn_actions)

        btn_look = discord.ui.Button(label="Осмотреться", emoji="🔍", style=discord.ButtonStyle.secondary, row=0)
        btn_look.callback = self.look_around_callback
        self.add_item(btn_look)

        btn_inventory = discord.ui.Button(label="Рюкзак", emoji="🎒", style=discord.ButtonStyle.primary, row=0)
        btn_inventory.callback = self.inventory_callback
        self.add_item(btn_inventory)

        # РЯД 1
        btn_move = discord.ui.Button(label="Переместиться", emoji="🗺️", style=discord.ButtonStyle.primary, row=1)
        btn_move.callback = self.move_callback
        self.add_item(btn_move)

        btn_map = discord.ui.Button(label="Карта", emoji="🚇", style=discord.ButtonStyle.secondary, row=1)
        btn_map.callback = self.map_callback
        self.add_item(btn_map)

        btn_status = discord.ui.Button(label="Статус", emoji="📊", style=discord.ButtonStyle.secondary, row=1)
        btn_status.callback = self.status_callback
        self.add_item(btn_status)

        # РЯД 3: Контекст
        if self.player and not self.player.is_alive:
            btn_revive = discord.ui.Button(label="Возродиться (Вайп)", emoji="💀", style=discord.ButtonStyle.danger, row=3)
            btn_revive.callback = self.revive_callback
            self.add_item(btn_revive)
        else:
            btn_faction = discord.ui.Button(label="Фракции", emoji="🏴", style=discord.ButtonStyle.primary, row=3)
            btn_faction.callback = self.faction_callback
            self.add_item(btn_faction)

            if self.player:
                npcs = get_npcs_on_station(self.player.location)
                if npcs:
                    btn_npc = discord.ui.Button(label="NPC рядом", emoji="👥", style=discord.ButtonStyle.success, row=3)
                    btn_npc.callback = self.npc_callback
                    self.add_item(btn_npc)

                if is_trade_station(self.player.location):
                    btn_trade = discord.ui.Button(label="Торговля", emoji="🏪", style=discord.ButtonStyle.success, row=3)
                    btn_trade.callback = self.trade_callback
                    self.add_item(btn_trade)
            else:
                btn_refresh = discord.ui.Button(label="Обновить меню", emoji="🔄", style=discord.ButtonStyle.secondary, row=3)
                btn_refresh.callback = self.refresh_callback
                self.add_item(btn_refresh)

    # ... остальные callback'и остаются без изменений ...
    async def _get_player(self, interaction):
        from ..game_manager import game_manager
        player = game_manager.get_player(interaction.user.id)
        if player and not self.player:
            self.player = player
        return player

    async def refresh_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player: return
        station_data = MAP_DATA["станции"].get(player.location, {})
        embed = build_main_embed(player, station_data)
        await interaction.response.edit_message(embed=embed, view=MainMenu(player))

    async def action_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player: return
        if not player.is_alive:
            await interaction.response.send_message("💀 Вы мертвы! Используйте кнопку «Возродиться».", ephemeral=True)
            return
        embed = discord.Embed(title="🎯 Действия", description="Выберите тактическое действие:", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=ActionMenu())

    async def look_around_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if player and not player.is_alive:
            await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)
            return
        embed = discord.Embed(title="🔍 Осмотреться", description="Изучить окружение или разжечь костёр:", color=discord.Color.dark_blue())
        await interaction.response.edit_message(embed=embed, view=LookAroundMenu())

    async def inventory_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player: return
        from ..inventory import get_inventory_embed
        embed, view = get_inventory_embed(player)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def move_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player: return
        if not player.is_alive:
            await interaction.response.send_message("💀 Вы мертвы! Используйте кнопку «Возродиться».", ephemeral=True)
            return
        if not can_move(game_manager):
            await interaction.response.send_message("🌍 **Землетрясение!** Переходы временно заблокированы!", ephemeral=True)
            return

        current = player.location
        connections = MAP_DATA["станции"][current]["connections"]
        if not connections:
            await interaction.response.send_message("🚇 Конечная станция!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🗺️ Куда идем?",
            description=f"Текущая: **{MAP_DATA['станции'][current]['name']}**\n"
                        f"🏃 Выносливость: {player.stamina:.1f}/{player.max_stamina}",
            color=discord.Color.blue()
        )
        from .move import MoveMenu
        view = MoveMenu(connections, player)
        await interaction.response.edit_message(embed=embed, view=view)

    async def map_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player: return
        try: await interaction.response.defer()
        except discord.errors.NotFound: return

        from .map_render import MapPaginationView, build_overview_embed
        view = MapPaginationView()
        embed = build_overview_embed(player)
        await interaction.edit_original_response(embed=embed, view=view)

    async def status_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player: return

        embed = discord.Embed(title=f"📊 Статус {player.name}", color=discord.Color.green())
        total_health = player.get_total_health()
        max_health = player.get_max_total_health()

        embed.add_field(name="❤️ Части тела", value=player.get_body_parts_status(), inline=False)
        embed.add_field(name="📊 Общее здоровье", value=f"{total_health:.1f}/{max_health:.1f}", inline=True)
        embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)

        melee_data = get_melee_weapon(player.melee_weapon)
        if melee_data:
            embed.add_field(name="🗡️ Ближний бой", value=f"{melee_data.get('emoji', '👊')} {melee_data.get('name', 'Кулаки')} ({player.get_melee_weapon_durability_percent()}%)", inline=True)

        embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)
        embed.add_field(name="📍 Локация", value=MAP_DATA["станции"][player.location]["name"], inline=True)

        weapon_data = WEAPONS.get(player.weapon, {})
        embed.add_field(name="🔫 Оружие", value=weapon_data.get('name', 'Нет'), inline=True)

        view = StatusView(player)
        await interaction.response.edit_message(embed=embed, view=view)

    async def faction_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player or not player.is_alive:
            return await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)

        from .faction_view import FactionsMenu, build_factions_embed
        embed = build_factions_embed(player)
        view = FactionsMenu(player)
        await interaction.response.edit_message(embed=embed, view=view)

    async def npc_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player or not player.is_alive:
            return await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)

        from .faction_npc import NPCPickerView, build_npc_list_embed
        embed = build_npc_list_embed(player)
        view = NPCPickerView(player)
        await interaction.response.edit_message(embed=embed, view=view)

    async def trade_callback(self, interaction: discord.Interaction):
        player = await self._get_player(interaction)
        if not player or not player.is_alive:
            return await interaction.response.send_message("💀 Вы мертвы!", ephemeral=True)

        from .trade import TradeMenu
        view = TradeMenu(player, page=1)
        embed = view.build_page_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def revive_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💀 ВАЙП ПЕРСОНАЖА",
            description=(
                "Вы уверены, что хотите возродиться?\n\n"
                "⚠️ **ВНИМАНИЕ:** Это действие **удалит** вашего текущего персонажа (весь опыт, навыки, инвентарь, лояльность фракций).\n"
                "Вам придется создавать персонажа заново через `/start`."
            ),
            color=discord.Color.dark_red()
        )
        view = _ReviveConfirmView(interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)