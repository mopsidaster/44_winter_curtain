# -*- coding: utf-8 -*-
# func/views/tutorial.py - Обучающий гайд (0.4.8.9)

import discord

TOTAL_PAGES = 7

def build_tutorial_page(page: int) -> discord.Embed:
    page = max(1, min(page, TOTAL_PAGES))

    embed = discord.Embed(
        title=f"📖 КПК Сталкера — стр. {page}/{TOTAL_PAGES}",
        color=discord.Color.gold(),
    )

    if page == 1:
        embed.title = "📖 Шаг 1. Главная цель"
        embed.description = (
            "Твоя цель — **выжить и подняться по уровням** в тоннелях Метро. "
            "Ты спускаешься вниз, ищешь лут, выполняешь контракты и становишься сильнее.\n\n"
            "**Главное правило:** смерть здесь означает вайп. Если у тебя урон по голове или "
            "торсу достигает нуля, персонаж погибает навсегда. Всё снаряжение и лояльность фракций "
            "сгорают. Придётся начинать с чистого листа через `/start`."
        )

    elif page == 2:
        embed.title = "📖 Шаг 2. Интерфейс без духоты"
        embed.description = (
            "Забудь про всё, кроме трёх вещей на экране:\n\n"
            "• ❤️ **Полоска здоровья** — если она красная, срочно жми «Действия» → «Аптечка».\n"
            "• 🏃 **Выносливость** — тратится на переходы между станциями и бои. "
            "Если она упадет до нуля, ты начнешь получать урон от истощения.\n"
            "• 💰 **Никели** — местная валюта. За них покупаешь патроны, броню и еду.\n\n"
            "Кнопка **«🎒 Рюкзак»** — это твой инвентарь и снаряжение. "
            "Кнопка **«🗺️ Переместиться»** — путешествия по станциям."
        )

    elif page == 3:
        embed.title = "📖 Шаг 3. Твой первый цикл"
        embed.description = (
            "Всё делается через кнопки в меню. Вот твой первый маршрут:\n\n"
            "1. Открой **`/menu`**. Если на станции есть NPC (кнопка «👥 NPC рядом») — поговори с ним.\n"
            "2. Жми **«Карта»**, чтобы осмотреть линии, и **«Переместиться»**, чтобы уйти на другую станцию. "
            "Для старта выбирай безопасные зоны (🟢 или 🟡).\n"
            "3. Зайди в торговую зону (🏪). В меню «Торговля» купи патроны и еду.\n"
            "4. Дойди до опасной станции (🔴 или 💀). Победи мутантов и забери их лут.\n"
            "5. Вернись в меню **«Статус»** и прокачай навыки за полученный опыт."
        )

    elif page == 4:
        embed.title = "📖 Шаг 4. Главная опасность"
        embed.description = (
            "**Радиация и фильтры.** Если пойдёшь на станцию с опасностью 3+ без противогаза, "
            "ты наберёшь радиацию и словишь лучевую болезнь. Это верная смерть.\n\n"
            "Перед вылазкой в красные/чёрные зоны проверь в Рюкзаке:\n"
            "• 🎒 Надет ли противогаз?\n"
            "• 🧪 Вставлен ли туда рабочий фильтр?\n\n"
            "**Голод.** Выносливость восстанавливается едой через меню «Действия». "
            "Без еды ты умрёшь от истощения прямо на переходе."
        )

    elif page == 5:
        embed.title = "📖 Шаг 5. Как драться"
        embed.description = (
            "Бой пошаговый. В свой ход ты выбираешь действие и часть тела врага, затем отвечает он.\n\n"
            "• **Дистанция.** На «Близко» враг бьёт больнее, а ты можешь использовать рукопашную (👊). "
            "На «Далеко» попасть сложнее, но дробовики бесполезны — они не стреляют вдаль.\n"
            "• **Зоны поражения.** Стрелять в голову (🎯) выгодно — урон умножается на 2.5, но попасть туда сложно. "
            "Торс — самая большая зона, но урон по нему обычный.\n"
            "• **Очередь.** Из автоматов вылетает по 2 пули, из пистолетов-пулемётов — по 4. "
            "Урон делится между ними, но шанс попасть хотя бы раз — выше.\n"
            "• **Защита.** Если у тебя разряжен магазин, а враг вот-вот ударит — жми «🛡️ Защита». "
            "Ты потратишь ход, но снизишь входящий урон на 50%."
        )

    elif page == 6:
        embed.title = "📖 Лайфхак от про-игрока"
        embed.description = (
            "**Играй в бригаде.** Через **`/brigada new`** можно собрать группу до 3 человек. "
            "В режиме «Вместе» вы будете ходить по станциям одновременно и получите "
            "**+15% опыта** за каждого убитого врага.\n\n"
            "**Не спеши продавать лут.** У торговца Ганса на станции «Павелецкая-Кольцо» есть уникальный бонус: "
            "он скупает части мутантов (шкуры, клыки, хвосты) в **два раза дороже**, чем обычные торговцы. "
            "Копи лут с монстров и сдавай его именно ему. Только учти: чтобы пройти к нему, "
            "нужно будет разобраться с охраной Гутагов."
        )

    elif page == 7:
        embed.title = "📖 Запомни эти команды"
        embed.description = (
            "Почти всё управление происходит через кнопки, но эти три команды нужно знать наизусть:\n\n"
            "• **`/menu`** — вызывает главное меню. Если что-то потерял или не знаешь, что делать — жми её.\n"
            "• **`/brigada`** — управление группой (создать, пригласить друга, идти вместе).\n"
            "• **`/start`** — создать персонажа. Понадобится только в самом начале или после смерти.\n\n"
            "Удачи в Метро, сталкер. Не умирай."
        )

    embed.set_footer(text="◀ / ▶ — листать | 🔙 — вернуться в КПК")
    return embed

class TutorialView(discord.ui.View):
    def __init__(self, user_id: int, page: int = 1):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.page = max(1, min(page, TOTAL_PAGES))
        self._refresh()

    def _refresh(self):
        self.clear_items()

        prev_btn = discord.ui.Button(
            label="◀ Назад", style=discord.ButtonStyle.secondary,
            row=0, disabled=(self.page <= 1), custom_id=f"tut_prev_{self.page}"
        )
        prev_btn.callback = self._prev_callback
        self.add_item(prev_btn)

        page_label = discord.ui.Button(
            label=f"{self.page}/{TOTAL_PAGES}", style=discord.ButtonStyle.secondary,
            row=0, disabled=True, custom_id=f"tut_page_{self.page}"
        )
        self.add_item(page_label)

        next_btn = discord.ui.Button(
            label="Вперёд ▶", style=discord.ButtonStyle.secondary,
            row=0, disabled=(self.page >= TOTAL_PAGES), custom_id=f"tut_next_{self.page}"
        )
        next_btn.callback = self._next_callback
        self.add_item(next_btn)

        # Кнопка возврата в КПК
        close_btn = discord.ui.Button(
            label="🔙 Назад в КПК", style=discord.ButtonStyle.danger,
            row=1, custom_id=f"tut_close_{self.page}"
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)

    async def _prev_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваше обучение!", ephemeral=True)
            return
        self.page = max(1, self.page - 1)
        self._refresh()
        embed = build_tutorial_page(self.page)
        try: await interaction.response.edit_message(embed=embed, view=self)
        except Exception: pass

    async def _next_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваше обучение!", ephemeral=True)
            return
        self.page = min(TOTAL_PAGES, self.page + 1)
        self._refresh()
        embed = build_tutorial_page(self.page)
        try: await interaction.response.edit_message(embed=embed, view=self)
        except Exception: pass

    async def _close_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваше обучение!", ephemeral=True)
            return

        # Возврат в Журнал (КПК)
        try:
            from ..game_manager import game_manager
            from .faction_npc.journal_view import JournalView

            player = game_manager.get_player(self.user_id)
            if not player: return

            new_view = JournalView(player, page=0)
            embed = new_view.build_embed()
            await interaction.response.edit_message(embed=embed, view=new_view)
        except Exception:
            pass