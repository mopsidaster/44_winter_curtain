# -*- coding: utf-8 -*-
# func/views/pharmacy.py - Меню Аптеки (Билд 0.4.5)
#
# ИСТОРИЯ:
#   0.4.3 — базовая аптека
#   0.4.5 — аспирин и лечение заражения крови

import discord
import uuid
from .helpers import game_manager, save_player, BALANCE
from ..pharmacy_system import (
    get_all_shop_items,
    get_all_doctor_services,
    get_shop_item,
    get_doctor_service,
    buy_item,
    use_medkit,
    use_antirad,
    use_aspirin,
    cure_chemical_poisoning,
    cure_blood_infection,
    format_shop_list,
    format_doctor_services,
)


class PharmacyMenu(discord.ui.View):
    """Главное меню аптеки."""
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]

    @discord.ui.button(label="💊 Товары", style=discord.ButtonStyle.success)
    async def goods_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        embed = discord.Embed(
            title="💊 Аптека — Товары",
            description="Выберите, что купить:",
            color=discord.Color.green()
        )

        for item_id, item in get_all_shop_items().items():
            price = item.get('price', 0)
            embed.add_field(
                name=f"{item.get('emoji', '')} {item.get('name', item_id)}",
                value=f"{item.get('description', '')}\n💰 **{price}** никелей",
                inline=False
            )

        embed.set_footer(text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)}")

        view = PharmacyGoodsMenu(self.player)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="👨‍⚕️ Врач", style=discord.ButtonStyle.primary)
    async def doctor_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.user_id:
            await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
            return

        embed = discord.Embed(
            title="👨‍⚕️ Аптека — Врач",
            description="Услуги врача:",
            color=discord.Color.blue()
        )

        from ..disease_system import ensure_disease_fields, get_disease_data
        ensure_disease_fields(self.player)

        if self.player.diseases:
            disease_lines = []
            for disease_id in self.player.diseases:
                d = get_disease_data(disease_id)
                status = "лечится" if d.get('curable') else "❌ неизлечимо"
                disease_lines.append(f"• {d.get('emoji', '')} **{d.get('name', disease_id)}** ({status})")
            embed.add_field(
                name="💀 Активные болезни",
                value="\n".join(disease_lines),
                inline=False
            )
        else:
            embed.add_field(name="✅ Болезней нет", value="Вам не требуется лечение.", inline=False)

        for service_id, service in get_all_doctor_services().items():
            price = service.get('price', 0)
            embed.add_field(
                name=f"{service.get('emoji', '👨‍⚕️')} {service.get('name', service_id)}",
                value=f"{service.get('description', '')}\n💰 **{price}** никелей",
                inline=False
            )

        embed.set_footer(text=f"💰 Ваши никели: {self.player.inventory.get('никели', 0)}")

        view = PharmacyDoctorMenu(self.player)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .trade import TradeMenu
        embed = discord.Embed(
            title="🏪 Торговая зона",
            description="Нажмите на кнопку для покупки или продажи.",
            color=discord.Color.gold()
        )
        view = TradeMenu(self.player)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)


class PharmacyGoodsMenu(discord.ui.View):
    """Товары аптеки."""
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        items = get_all_shop_items()
        for idx, (item_id, item) in enumerate(items.items()):
            price = item.get('price', 0)
            button = discord.ui.Button(
                label=f"{item.get('emoji', '')} {item.get('name', item_id)} ({price})",
                style=discord.ButtonStyle.success,
                custom_id=f"ph_buy_{self.menu_id}_{idx}",
                row=idx // 3
            )
            button.callback = self.create_buy_callback(item_id)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"ph_back_{self.menu_id}",
            row=4
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_buy_callback(self, item_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            result = buy_item(self.player, item_id)
            await save_player(self.player)

            if result.get('success'):
                embed = discord.Embed(
                    title="✅ Покупка",
                    description=result.get('message', ''),
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="💰 Никели",
                    value=f"Остаток: **{self.player.inventory.get('никели', 0)}**",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=result.get('message', ''),
                    color=discord.Color.red()
                )

            new_view = PharmacyGoodsMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=new_view)
            except Exception:
                pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💊 Аптека",
            description="Выберите раздел:",
            color=discord.Color.green()
        )
        embed.add_field(name="📋 Разделы", value="• 💊 **Товары**\n• 👨‍⚕️ **Врач**", inline=False)
        view = PharmacyMenu(self.player)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)


class PharmacyDoctorMenu(discord.ui.View):
    """Услуги врача."""
    def __init__(self, player):
        super().__init__(timeout=120)
        self.player = player
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        services = get_all_doctor_services()
        for idx, (service_id, service) in enumerate(services.items()):
            price = service.get('price', 0)
            button = discord.ui.Button(
                label=f"{service.get('emoji', '👨‍⚕️')} {service.get('name', service_id)} ({price})",
                style=discord.ButtonStyle.primary,
                custom_id=f"ph_doc_{self.menu_id}_{idx}"
            )
            button.callback = self.create_service_callback(service_id)
            self.add_item(button)

        back_button = discord.ui.Button(
            label="🔙 Назад",
            style=discord.ButtonStyle.danger,
            custom_id=f"ph_doc_back_{self.menu_id}"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_service_callback(self, service_id: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.user_id:
                await interaction.response.send_message("❌ Не ваш инвентарь!", ephemeral=True)
                return

            await interaction.response.defer()

            if service_id == "лечение_хим_отравления":
                result = cure_chemical_poisoning(self.player)
            elif service_id == "лечение_заражения_крови":
                result = cure_blood_infection(self.player)
            else:
                result = {"success": False, "message": "❌ Неизвестная услуга."}

            await save_player(self.player)

            if result.get('success'):
                embed = discord.Embed(
                    title="✅ Лечение завершено",
                    description=result.get('message', ''),
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="💰 Никели",
                    value=f"Остаток: **{self.player.inventory.get('никели', 0)}**",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=result.get('message', ''),
                    color=discord.Color.red()
                )

            new_view = PharmacyDoctorMenu(self.player)
            try:
                await interaction.edit_original_response(embed=embed, view=new_view)
            except Exception:
                pass

        return callback

    async def back_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💊 Аптека",
            description="Выберите раздел:",
            color=discord.Color.green()
        )
        embed.add_field(name="📋 Разделы", value="• 💊 **Товары**\n• 👨‍⚕️ **Врач**", inline=False)
        view = PharmacyMenu(self.player)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=False)