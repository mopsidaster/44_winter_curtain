# -*- coding: utf-8 -*-
# func/views/campfire.py - Меню костра (0.4.7.2)
#
# ИСТОРИЯ:
#   0.4.4   — розжиг/хлам, согрев, готовка
#   0.4.4.5.2 — «Подкинуть хлам» только когда костёр горит
#   0.4.6   — групповой согрев: согреваются все члены группы
#   0.4.7.2 — согрев дополнительно восстанавливает +2 выносливости

import discord
import uuid
from .helpers import (
    game_manager, save_player, combat_manager,
    get_food, can_cook, get_cooked_version, cook_food
)
from .combat_views import CombatView
from ..cold_system import (
    reduce_cold, format_detailed_status,
    can_warm_up_at_campfire, ensure_cold_fields,
    get_campfire_stamina_bonus,
)


class CampfireMenu(discord.ui.View):
    """
    Главное меню костра.
    Показывает текущий заряд и кнопки действий.
    """
    def __init__(self, player, is_dangerous: bool, cookable: list, charges: int = 0):
        super().__init__(timeout=180)
        self.player = player
        self.is_dangerous = is_dangerous
        self.cookable = cookable
        self.charges = charges
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        if self.charges > 0:
            charge_btn = discord.ui.Button(
                label=f"🔥 Заряд: {self.charges}",
                style=discord.ButtonStyle.success,
                custom_id=f"cf_charge_{self.menu_id}",
                row=0,
                disabled=True
            )
            self.add_item(charge_btn)
        else:
            charge_btn = discord.ui.Button(
                label="🔥 Костёр не разожжён",
                style=discord.ButtonStyle.secondary,
                custom_id=f"cf_nocharge_{self.menu_id}",
                row=0,
                disabled=True
            )
            self.add_item(charge_btn)

        if self.charges > 0:
            warm_btn = discord.ui.Button(
                label="🔥 Согреться (-5 холода, +2 вын.)",
                style=discord.ButtonStyle.danger,
                custom_id=f"cf_warm_{self.menu_id}",
                row=1
            )
            warm_btn.callback = self.warm_callback
            self.add_item(warm_btn)

            hlam_count = len(self.player.inventory.get('хлам', []) or [])
            hlam_btn = discord.ui.Button(
                label=f"📦 Подкинуть хлам (+1 заряд) [{hlam_count}]" if hlam_count > 0
                else "📦 Хлама нет",
                style=discord.ButtonStyle.primary if hlam_count > 0 else discord.ButtonStyle.secondary,
                custom_id=f"cf_hlam_{self.menu_id}",
                row=1,
                disabled=(hlam_count <= 0)
            )
            hlam_btn.callback = self.hlam_callback
            self.add_item(hlam_btn)

            putout_btn = discord.ui.Button(
                label="🌫️ Потушить костёр",
                style=discord.ButtonStyle.secondary,
                custom_id=f"cf_putout_{self.menu_id}",
                row=1
            )
            putout_btn.callback = self.putout_callback
            self.add_item(putout_btn)

        for idx, food_id in enumerate(self.cookable[:6]):
            food = get_food(food_id)
            cooked_id = get_cooked_version(food_id)
            cooked = get_food(cooked_id)
            if food and cooked:
                btn = discord.ui.Button(
                    label=f"🍳 {food.get('name', food_id)} → {cooked.get('name', cooked_id)}"[:80],
                    style=discord.ButtonStyle.primary,
                    custom_id=f"cf_cook_{self.menu_id}_{idx}",
                    row=2 + (idx // 3),
                    disabled=(self.charges <= 0)
                )
                btn.callback = self.create_cook_callback(food_id)
                self.add_item(btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"cf_back_{self.menu_id}",
            row=3
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def create_cook_callback(self, food_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            if self.charges <= 0:
                await interaction.response.send_message(
                    "❌ Костёр не разожжён! Используйте розжиг.",
                    ephemeral=True
                )
                return

            if food_id not in self.player.food_inventory:
                await interaction.response.send_message("❌ У вас больше нет этого продукта!", ephemeral=True)
                return

            await interaction.response.defer()

            campfire_type = "danger" if self.is_dangerous else "safe"
            result = await cook_food(self.player, food_id, campfire_type)

            if "Начинается бой" in result:
                combat = combat_manager.get_combat(self.player.user_id)
                if combat:
                    embed = combat.get_status_embed()
                    embed.add_field(name="⚔️ БОЙ!", value="На вас напал мутант!", inline=False)
                    view = CombatView(self.player.user_id)
                    await interaction.edit_original_response(embed=embed, view=view)
                    return

            self.charges -= 1
            await save_player(self.player)

            remaining = [fid for fid in self.player.food_inventory if can_cook(fid)]

            embed = discord.Embed(
                title="🔥 Результат приготовления",
                description=result,
                color=discord.Color.green() if "приготовил" in result else discord.Color.red()
            )
            embed.add_field(name="🔥 Заряд костра", value=f"{self.charges}", inline=False)

            if remaining and self.charges > 0:
                new_view = CampfireMenu(self.player, self.is_dangerous, remaining, self.charges)
                embed.add_field(
                    name="🍳 Доступно ещё",
                    value=f"Можно приготовить: {len(remaining)} шт.",
                    inline=False
                )
                await interaction.edit_original_response(embed=embed, view=new_view)
            else:
                if self.charges <= 0:
                    embed.add_field(
                        name="⚠️ Костёр потух",
                        value="Заряд костра закончился.",
                        inline=False
                    )
                    new_view = CampfireEmptyMenu()
                else:
                    new_view = CampfireEmptyMenu()
                await interaction.edit_original_response(embed=embed, view=new_view)

        return callback

    async def warm_callback(self, interaction: discord.Interaction):
        """0.4.6: групповой согрев. 0.4.7.2: +2 выносливости."""
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        if self.charges <= 0:
            await interaction.response.send_message("❌ Костёр не разожжён!", ephemeral=True)
            return

        await interaction.response.defer()

        ensure_cold_fields(self.player)

        if self.player.cold <= 0:
            await interaction.followup.send(
                "🔥 Вам не нужно согреваться — вы не замёрзли.", ephemeral=True
            )
            return

        stamina_bonus = get_campfire_stamina_bonus()

        from ..social.brigade_manager import brigade_manager
        brigade = brigade_manager.get_user_brigade(self.player.user_id)

        affected = []
        if brigade and brigade.is_active():
            for uid in brigade.get_member_ids():
                member = game_manager.get_player(uid)
                if member and member.is_alive and member.location == self.player.location:
                    ensure_cold_fields(member)
                    if member.cold > 0:
                        reduce_cold(member, 5)
                        member.restore_stamina(stamina_bonus)
                        affected.append(member.name)
                        await save_player(member)
            if not affected:
                affected = [self.player.name]
                reduce_cold(self.player, 5)
                self.player.restore_stamina(stamina_bonus)
        else:
            reduce_cold(self.player, 5)
            self.player.restore_stamina(stamina_bonus)
            affected.append(self.player.name)

        self.charges -= 1
        await save_player(self.player)

        affected_text = ", ".join(affected) if affected else "никто"

        embed = discord.Embed(
            title="🔥 Согрев у костра",
            description=(
                f"Согрелись: **{affected_text}**\n"
                f"❄️ -5 холода, 🏃 +{stamina_bonus:.0f} выносливости каждому"
            ),
            color=discord.Color.orange()
        )
        embed.add_field(name="🔥 Заряд костра", value=f"{self.charges}", inline=False)

        cookable = [fid for fid in self.player.food_inventory if can_cook(fid)]
        new_view = CampfireMenu(self.player, self.is_dangerous, cookable, self.charges)
        await interaction.edit_original_response(embed=embed, view=new_view)

    async def hlam_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        await interaction.response.defer()

        hlam_list = self.player.inventory.get('хлам', []) or []
        if not hlam_list:
            await interaction.followup.send("❌ У вас нет хлама!", ephemeral=True)
            return

        used_item = hlam_list.pop(0)
        self.player.inventory['хлам'] = hlam_list
        self.charges += 1

        await save_player(self.player)

        embed = discord.Embed(
            title="📦 Хлам подкинут",
            description=f"Вы подкинули в костёр: **{used_item}**\n🔥 Заряд: **{self.charges}**",
            color=discord.Color.orange()
        )

        cookable = [fid for fid in self.player.food_inventory if can_cook(fid)]
        new_view = CampfireMenu(self.player, self.is_dangerous, cookable, self.charges)
        await interaction.edit_original_response(embed=embed, view=new_view)

    async def putout_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🌫️ Костёр потушен",
            description="Вы затушили костёр. Остатки заряда потеряны.",
            color=discord.Color.dark_gray()
        )
        new_view = CampfireEmptyMenu()
        await interaction.response.edit_message(embed=embed, view=new_view)

    async def back_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        from .look_around import LookAroundMenu
        embed = discord.Embed(
            title="🔍 Осмотреться",
            description="Что вы хотите сделать?",
            color=discord.Color.blue()
        )
        view = LookAroundMenu()
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)


class CampfireEmptyMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger, custom_id="campfire_empty_back")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .look_around import LookAroundMenu
        embed = discord.Embed(
            title="🔍 Осмотреться",
            description="Что вы хотите сделать?",
            color=discord.Color.blue()
        )
        view = LookAroundMenu()
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)


class CampfireStartMenu(discord.ui.View):
    """
    Меню, которое появляется при нажатии «Костёр».
    Спрашивает: «Вы хотите разжечь костёр здесь?»
    """
    def __init__(self, player, is_dangerous: bool):
        super().__init__(timeout=120)
        self.player = player
        self.is_dangerous = is_dangerous
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        rozzhig_count = self.player.inventory.get('розжиг', 0)
        rozzhig_btn = discord.ui.Button(
            label=f"🪵 Использовать розжиг ({rozzhig_count})" if rozzhig_count > 0 else "🪵 Розжига нет",
            style=discord.ButtonStyle.success if rozzhig_count > 0 else discord.ButtonStyle.secondary,
            custom_id=f"cf_start_roz_{self.menu_id}",
            row=0,
            disabled=(rozzhig_count <= 0)
        )
        rozzhig_btn.callback = self.use_rozzhig_callback
        self.add_item(rozzhig_btn)

        back_btn = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"cf_start_back_{self.menu_id}",
            row=1
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def use_rozzhig_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        count = self.player.inventory.get('розжиг', 0)
        if count <= 0:
            await interaction.response.send_message("❌ У вас нет розжига!", ephemeral=True)
            return

        await interaction.response.defer()

        self.player.inventory['розжиг'] = count - 1
        charges = 5

        await save_player(self.player)
        await _show_campfire_main(interaction, self.player, self.is_dangerous, charges,
                                  f"🔥 Костёр разожжён розжигом! Заряд: {charges}")

    async def back_callback(self, interaction: discord.Interaction):
        from .look_around import LookAroundMenu
        embed = discord.Embed(
            title="🔍 Осмотреться",
            description="Что вы хотите сделать?",
            color=discord.Color.blue()
        )
        view = LookAroundMenu()
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)


async def _show_campfire_main(interaction: discord.Interaction, player, is_dangerous: bool,
                              charges: int, message: str):
    cookable = [fid for fid in player.food_inventory if can_cook(fid)]

    embed = discord.Embed(
        title="🔥 Костёр",
        description=message,
        color=discord.Color.orange()
    )

    ensure_cold_fields(player)
    cold_line = f"❄️ Замерзание: **{player.cold:.0f}/100**"

    if cookable:
        embed.add_field(
            name="🍳 Готовка",
            value=f"Доступно продуктов: **{len(cookable)}**",
            inline=False
        )
    else:
        embed.add_field(
            name="🍳 Готовка",
            value="Нет продуктов для готовки.",
            inline=False
        )

    embed.add_field(name="❄️ Холод", value=cold_line, inline=False)
    embed.add_field(
        name="🔋 Заряд",
        value=f"**{charges}** использований",
        inline=False
    )

    view = CampfireMenu(player, is_dangerous, cookable, charges)
    try:
        await interaction.edit_original_response(embed=embed, view=view)
    except Exception as e:
        from utils.logger import get_logger
        get_logger().error(f"Ошибка показа меню костра: {e}")