# -*- coding: utf-8 -*-
# func/views/prologue.py - Пролог 44: White Curtain (0.4.8)
#
# ИСТОРИЯ:
#   0.4.8 — новый файл. 18 сцен, модалка имени, кнопка пропуска.
#           Добавлена замена <Игрок> и {player_name} на имя персонажа.

import discord
import uuid
import re

from .helpers import game_manager, save_player
from utils.logger import get_logger

logger = get_logger()

TOTAL_SCENES = 18


# ==================== ДАННЫЕ СЦЕН ====================

SCENES = {
    1: {
        "text": "*вспышки света*",
        "title": "Пролог",
        "buttons": [
            {"label": "…", "style": "primary", "next": 2},
        ],
    },
    2: {
        "text": "*<Игрок> пытается открыть глаза>*",
        "title": "Пролог",
        "buttons": [
            {"label": "…", "style": "primary", "next": 3},
        ],
    },
    3: {
        "text": "*Вы обессилены, кажется это конец...*",
        "title": "Пролог",
        "buttons": [
            {"label": "…", "style": "primary", "next": 4},
        ],
    },
    4: {
        "title": "Пролог",
        "dialogue": [
            ("Голос 1", "Эй, смотрите! На пороге школы кто-то есть! Быстрее, быстрее!"),
        ],
        "text": "*вы почувствовали, как голоса приблизились и начали пытаться поднять Вас*",
        "buttons": [
            {"label": "…", "style": "primary", "next": 5},
        ],
    },
    5: {
        "title": "Пролог",
        "dialogue": [
            ("Голос 2", "Ни одного обморожения... Как он так долго пролежал в этом сугробе? Еще и без маски..."),
            ("Голос 3", "Ему очень сильно повезло..."),
        ],
        "text": None,
        "buttons": [
            {"label": "…", "style": "primary", "next": 6},
        ],
    },
    6: {
        "title": "Пролог",
        "text": "*спустя некоторое время Вы начали чувствовать теплый воздух*",
        "dialogue": [
            ("Голос 1", "Разойдись! У нас пациент!"),
        ],
        "buttons": [
            {"label": "Мгмх...", "style": "primary", "next": 7},
        ],
    },
    7: {
        "title": "Пролог",
        "text": "*Вас пронесли через шумный торговый ряд*",
        "dialogue": [
            ("Голос 2", "Черт, да он живой! Парень, держись, щас мы тебя подлатаем!"),
        ],
        "buttons": [
            {"label": "Агх...", "style": "primary", "next": 8},
        ],
    },
    8: {
        "title": "Пролог",
        "text": "*Яркие лампы ударили Вам по закрытым глазам, после чего тебя кинули на стол*",
        "dialogue": [
            ("Голос 1", "На правой руке кровотечение! Также возможно пробито плечо... Братва, следите, я позову Санитара!"),
            ("Голос 3", "Ебаный в рот, не представляю как с таким ранением можно было пролежать так долго, еще и на пороге Школы. Может там тварь какая новая завелась?"),
            ("Голос 2", "Нужно будет туда сходить..."),
        ],
        "buttons": [
            {"label": "…", "style": "primary", "next": 9},
        ],
    },
    9: {
        "title": "Пролог",
        "text": "*В комнату вбегают двое людей*",
        "dialogue": [
            ("Голос 1", "Мы нашли его у Школы. Возможно у него есть ценная информация!"),
            ("Врач", "Сейчас посмотрим..."),
        ],
        "buttons": [
            {"label": "Агкх...", "style": "primary", "next": 10},
        ],
    },
    10: {
        "title": "Пролог",
        "text": "*Вы чувствуете как Вам начинают зашивать рану на плече после обработки*",
        "buttons": [
            {"label": "*Мычать от боли*", "style": "primary", "next": 11},
        ],
    },
    11: {
        "title": "Пролог",
        "text": "*От боли вы вскакиваете на койке, открыв глаза и держа Врача за халат*",
        "buttons": [
            {"label": "Кто ты такой!? Где я!?", "style": "primary", "next": 12},
        ],
    },
    12: {
        "title": "Пролог",
        "dialogue": [
            ("Голос 1", "*отталкивает Вас обратно* Спокойнее мужик, мы тебе жизнь спасли!"),
            ("Врач", "Он напуган... Я вколю Вам обезбол и закончу операцию..."),
            ("Голос 2", "*Хватает Вас сзади* Держу его!"),
        ],
        "text": "*Вы обратно вырубаетесь после введенной инъекции*",
        "buttons": [
            {"label": "…", "style": "primary", "next": 13},
        ],
    },
    13: {
        "title": "Пролог",
        "text": "*Спустя время Вы вновь проснулись*",
        "buttons": [
            {"label": "Как же трещит бошка...", "style": "primary", "next": 14},
        ],
    },
    14: {
        "title": "Пролог",
        "text": "*В палату заходит мужчина с густой бородой и в полицейской форме*",
        "dialogue": [
            ("???", "Друг, проснулся? Меня, значится, Дмитрий Борисович зовут, я здесь местный начальник..."),
        ],
        "buttons": [
            {"label": "Почему вы спасли меня?", "style": "primary", "next": 15},
        ],
    },
    15: {
        "title": "Пролог",
        "text": "*Присев рядом с тобой, Дмитрий Борисович продолжает общаться*",
        "dialogue": [
            ("Дмитрий Борисович", "Все мы здесь остаемся людьми, да и нечасто в наших краях заметишь раненного незнакомца на поверхности..."),
        ],
        "buttons": [
            {"label": "На какой я щас станции? Почему я вообще здесь оказался?", "style": "primary", "next": 16},
        ],
    },
    16: {
        "title": "Пролог",
        "dialogue": [
            ("Дмитрий Борисович", "*Ухмыляясь* Друг, ты на Бульваре Дмитрия Донского, пристанище Антикваров! А вот как ты здесь оказался уж точно никто не знает, это я хотел у тебя спросить..."),
        ],
        "buttons": [
            {"label": "Но я не помню ничего...", "style": "primary", "next": 17},
        ],
    },
    17: {
        "title": "Пролог",
        "dialogue": [
            ("Дмитрий Борисович", "Похоже, что у тебя амнезия. Ну, постараемся вспомнить, а пока лечись и будь как дома. Кстати, ты хоть сам то откуда, помнишь? Как тебя звать?"),
        ],
        "modal": True,  # 0.4.8: открывает модалку имени/происхождения
    },
    18: {
        "title": "Пролог",
        "dialogue": [
            ("Дмитрий Борисович", "Ну, будем знакомы, {player_name}! Будем гадать, как тебя занесло сюда аж с {player_origin}..."),
        ],
        "buttons": [
            {"label": "До встречи!", "style": "primary", "next": None},  # None → end
        ],
    },
}


# ==================== EMBED ====================

def _format_dynamic_text(text: str, player) -> str:
    """Заменяет переменные и <Игрок> на реальные данные."""
    if not text:
        return ""

    p_name = getattr(player, "name", "Сталкер") if player else "Сталкер"
    p_origin = getattr(player, "origin", "неизвестно") if player else "неизвестно"

    # Заменяем {player_name} и {player_origin}
    text = text.replace("{player_name}", p_name)
    text = text.replace("{player_origin}", p_origin)

    # Заменяем <Игрок> и подобные конструкции в угловых скобках
    # Ищем <...> и меняем на имя игрока
    text = re.sub(r'<(?:Игрок|игрок|Player|player)>', p_name, text)

    return text


def build_scene_embed(scene_num: int, player=None) -> discord.Embed:
    scene = SCENES.get(scene_num)
    if not scene:
        return discord.Embed(
            title="Пролог",
            description="*Сцена не найдена.*",
            color=discord.Color.dark_theme(),
        )

    embed = discord.Embed(
        title=scene.get("title", "Пролог"),
        color=discord.Color.dark_theme(),
    )

    # Диалоги
    dialogue_lines = []
    for speaker, text in scene.get("dialogue", []):
        formatted_text = _format_dynamic_text(text, player)
        dialogue_lines.append(f"**{speaker}:** {formatted_text}")

    # Основной текст
    raw_main_text = scene.get("text") or ""
    main_text = _format_dynamic_text(raw_main_text, player)

    parts = []
    if dialogue_lines:
        parts.append("\n\n".join(dialogue_lines))
    if main_text:
        parts.append(f"_{main_text}_")

    embed.description = "\n\n".join(parts) if parts else "*...*"

    # Прогресс
    embed.set_footer(text=f"Сцена {scene_num}/{TOTAL_SCENES}")

    return embed


# ==================== МОДАЛКА ИМЕНИ И ПРОИСХОЖДЕНИЯ ====================

class OriginModal(discord.ui.Modal, title="Назвать имя и происхождение"):
    player_name = discord.ui.TextInput(
        label="Ваше имя",
        placeholder="Как вас звать?",
        min_length=1,
        max_length=50,
        required=True,
        style=discord.TextStyle.short,
    )
    player_origin = discord.ui.TextInput(
        label="Откуда вы? (станция Московского метро)",
        placeholder="Например: Пражская, Комсомольская, Юго-Западная...",
        min_length=2,
        max_length=100,
        required=True,
        style=discord.TextStyle.short,
    )

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        player = game_manager.get_player(self.user_id)
        if not player:
            await interaction.response.send_message(
                "❌ Персонаж не найден.", ephemeral=True
            )
            return

        new_name = self.player_name.value.strip()
        origin = self.player_origin.value.strip()

        if new_name:
            player.name = new_name
        if origin:
            player.origin = origin

        await save_player(player)

        logger.info(f"[PROLOGUE] {self.user_id}: имя='{new_name}', происхождение='{origin}'")

        # Показываем сцену 18
        embed = build_scene_embed(18, player)
        view = PrologueView(self.user_id, scene_num=18)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            try:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            except Exception:
                pass


# ==================== VIEW ====================

class PrologueView(discord.ui.View):
    """
    Пролог.
    scene_num = 1..18
    """

    def __init__(self, user_id: int, scene_num: int = 1):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.scene_num = max(1, min(scene_num, TOTAL_SCENES))
        self.menu_id = uuid.uuid4().hex[:8]
        self._add_buttons()

    def _add_buttons(self):
        self.clear_items()
        scene = SCENES.get(self.scene_num, {})

        # Пропуск на сцене 1
        if self.scene_num == 1:
            skip_btn = discord.ui.Button(
                label="⏭️ Пропустить пролог",
                style=discord.ButtonStyle.secondary,
                custom_id=f"pro_skip_{self.menu_id}",
                row=2,
            )
            skip_btn.callback = self.skip_callback
            self.add_item(skip_btn)

        # Модалка
        if scene.get("modal"):
            modal_btn = discord.ui.Button(
                label="Назвать имя и происхождение",
                style=discord.ButtonStyle.primary,
                custom_id=f"pro_modal_{self.menu_id}",
                row=0,
            )
            modal_btn.callback = self.open_modal_callback
            self.add_item(modal_btn)
            return

        # Обычные кнопки
        for idx, btn_data in enumerate(scene.get("buttons", [])[:4]):
            style_map = {
                "primary": discord.ButtonStyle.primary,
                "secondary": discord.ButtonStyle.secondary,
                "success": discord.ButtonStyle.success,
                "danger": discord.ButtonStyle.danger,
            }
            btn = discord.ui.Button(
                label=btn_data["label"][:80],
                style=style_map.get(btn_data.get("style", "primary"), discord.ButtonStyle.primary),
                custom_id=f"pro_{self.scene_num}_{idx}_{self.menu_id}",
                row=0,
            )
            next_scene = btn_data.get("next")
            btn.callback = self.create_next_callback(next_scene)
            self.add_item(btn)

    async def _check_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Это не ваш пролог!", ephemeral=True
            )
            return False
        return True

    def create_next_callback(self, next_scene):
        async def callback(interaction: discord.Interaction):
            if not await self._check_user(interaction):
                return

            if next_scene is None:
                # Финал — перекидываем в меню!
                await self._finish(interaction)
                return

            new_view = PrologueView(self.user_id, scene_num=next_scene)
            player = game_manager.get_player(self.user_id)
            embed = build_scene_embed(next_scene, player)

            try:
                await interaction.response.edit_message(embed=embed, view=new_view)
            except Exception as e:
                logger.error(f"[PROLOGUE] next: {e}")

        return callback

    async def open_modal_callback(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        try:
            await interaction.response.send_modal(OriginModal(self.user_id))
        except Exception as e:
            logger.error(f"[PROLOGUE] modal: {e}")

    async def skip_callback(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        await self._finish(interaction, skipped=True)

    async def _finish(self, interaction: discord.Interaction, skipped: bool = False):
        """Завершить пролог — открыть MainMenu."""
        player = game_manager.get_player(self.user_id)
        if player:
            player.prologue_completed = True
            await save_player(player)

        logger.info(f"[PROLOGUE] {self.user_id}: пролог завершён (skipped={skipped})")

        try:
            from .main_menu import MainMenu
            from ..map_data import MAP_DATA

            if not player:
                await interaction.response.edit_message(
                    content="❌ Персонаж не найден. Введите /start.",
                    embed=None, view=None,
                )
                return

            station_data = MAP_DATA["станции"].get(player.location, {})
            total_hp = player.get_total_health()
            max_hp = player.get_max_total_health()

            embed = discord.Embed(
                title="🎮 Меню 44: White Curtain",
                description=f"Добро пожаловать, **{player.name}**!\nУровень: **{player.level}**",
                color=discord.Color.blue(),
            )
            embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
            embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
            embed.add_field(name="📍 Локация", value=station_data.get("name", "?"), inline=True)
            embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)

            if skipped:
                embed.add_field(
                    name="⏭️ Пролог пропущен",
                    value="Вы можете посмотреть его позже через обучение.",
                    inline=False,
                )

            await interaction.response.edit_message(embed=embed, view=MainMenu())
        except Exception as e:
            logger.error(f"[PROLOGUE] finish: {e}", exc_info=True)