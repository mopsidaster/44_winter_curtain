# -*- coding: utf-8 -*-
# func/views/map_render.py - Рендер карты метро (0.4.8.7)
#
# ИСТОРИЯ:
#   0.4.7.4 — карта на страницы
#   0.4.7.4.1 — persistent view
#   0.4.7.5 — теги blocked/hostile
#   0.4.8.7 — иконка Гутагов при наличии пропуска

import discord

from ..map_data import MAP_DATA, LINES
from ..line_colors import (
    LINE_ICONS, LINE_NAMES,
    DANGER_EMOJI, STATION_TAGS, LINE_ORDER,
)


STATIONS_PER_LINE = 3
MAX_EMBED_FIELDS = 10
MAX_EMBED_LEN = 5000
MAX_LINE_BUTTONS = 4

GUTAGI_STATIONS = {
    "павелецкая_кольцо", "добрынинская", "октябрьская_кольцо",
    "серпуховская", "тульская",
}
GUTAGI_EMOJI = "<:gutag:1564608459939389500>"


# ==================== ФОРМИРОВАНИЕ СТАНЦИИ ====================

def _station_marker(station_id: str, current_id: str = None,
                    player=None) -> str:
    st = MAP_DATA["станции"].get(station_id)
    if not st:
        return f"❓ {station_id}"

    danger = st.get("danger", 0)
    danger_emoji = DANGER_EMOJI.get(danger, "⬤")

    is_current = (station_id == current_id)
    marker = "▶" if is_current else "⬤"

    tags = []
    types = st.get("types", []) if "types" in st else [st.get("type", "")]
    if "торговая" in types:
        tags.append(STATION_TAGS["торговая"])
    if "стартовая" in types:
        tags.append(STATION_TAGS["стартовая"])
    if st.get("type") == "на_поверхности":
        tags.append(STATION_TAGS["на_поверхности"])
    if st.get("ruined"):
        tags.append(STATION_TAGS["ruined"])

    # 0.4.8.7: Гутаги — иконка при наличии пропуска
    player_hlam = []
    if player is not None:
        player_hlam = getattr(player, 'inventory', {}).get("хлам", []) or []
    has_perm_pass = "постоянный_пропуск" in player_hlam
    has_temp_pass = "временный_пропуск" in player_hlam

    if st.get("blocked"):
        if station_id in GUTAGI_STATIONS and (has_perm_pass or has_temp_pass):
            tags.append(GUTAGI_EMOJI)
        else:
            tags.append(STATION_TAGS["blocked"])

    if st.get("hostile"):
        tags.append(STATION_TAGS["hostile"])

    tag_str = " " + " ".join(tags) if tags else ""
    return f"{danger_emoji} {marker} {st.get('name', station_id)}{tag_str}"


def _get_transfer_stations_on_line(line_id: str) -> set:
    line_data = LINES.get(line_id, {})
    line_stations = set(line_data.get("stations", []))

    transfers = set()
    for sid in line_stations:
        st = MAP_DATA["станции"].get(sid, {})
        for conn in st.get("connections", []):
            conn_st = MAP_DATA["станции"].get(conn, {})
            if conn_st.get("line") != line_id:
                transfers.add(sid)
                break
    return transfers


def _build_line_segments(line_id: str, current_id: str = None,
                         player=None) -> list:
    line_data = LINES.get(line_id, {})
    stations = line_data.get("stations", [])
    if not stations:
        return []

    transfers = _get_transfer_stations_on_line(line_id)

    segments = []
    i = 0
    n = len(stations)

    while i < n:
        chunk = stations[i: i + STATIONS_PER_LINE]
        parts = []

        for idx, sid in enumerate(chunk):
            marker = _station_marker(sid, current_id, player)
            if idx > 0:
                prev_sid = chunk[idx - 1]
                link = "↔" if (prev_sid in transfers or sid in transfers) else "──"
                parts.append(link)
            parts.append(marker)

        segments.append(" ".join(parts))

        if i + STATIONS_PER_LINE >= n:
            break
        i += STATIONS_PER_LINE - 1

    return segments


def _build_legend() -> str:
    return (
        "★ старт | 🏪 торговля | ☢️ разрушенная | ❄️ поверхность | "
        "🚫 заблокирована | 🔫 враждебная | ▶ вы здесь | "
        f"{GUTAGI_EMOJI} Гутаги (пропуск)\n"
        "🟢🟡🟠🔴💀☠️ — опасность | ↔ пересадка"
    )


def _get_line_order() -> list:
    ordered = [lid for lid in LINE_ORDER if lid in LINES]
    extra = [lid for lid in LINES.keys() if lid not in ordered]
    return ordered + extra


# ==================== EMBED: ОБЗОР ====================

def build_overview_embed(player=None) -> discord.Embed:
    current_id = getattr(player, 'location', None) if player else None

    embed = discord.Embed(
        title="🗺️ Карта 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
        color=discord.Color.dark_blue(),
    )

    if player:
        st = MAP_DATA["станции"].get(current_id, {})
        embed.description = (
            f"📍 Вы на: **{st.get('name', current_id)}** "
            f"{DANGER_EMOJI.get(st.get('danger', 0), '⬤')}"
        )
    else:
        embed.description = "Обзор линий метро."

    line_order = _get_line_order()[:MAX_EMBED_FIELDS]

    for line_id in line_order:
        line_data = LINES.get(line_id, {})
        line_name = line_data.get("name", LINE_NAMES.get(line_id, line_id))
        icon = LINE_ICONS.get(line_id, "⬛")
        stations = line_data.get("stations", [])

        marker = " ← вы здесь" if current_id in stations else ""

        embed.add_field(
            name=f"{icon} {line_name}{marker}"[:256],
            value=f"Станций: **{len(stations)}**",
            inline=False,
        )

    embed.set_footer(text=_build_legend())

    if len(embed) > MAX_EMBED_LEN:
        embed.clear_fields()
        embed.add_field(name="⚠️ Ошибка", value="Обзор не помещается.", inline=False)

    return embed


# ==================== EMBED: ЛИНИЯ ====================

def build_line_embed(line_id: str, player=None) -> discord.Embed:
    current_id = getattr(player, 'location', None) if player else None

    line_data = LINES.get(line_id, {})
    line_name = line_data.get("name", LINE_NAMES.get(line_id, line_id))
    icon = LINE_ICONS.get(line_id, "⬛")
    stations = line_data.get("stations", [])

    embed = discord.Embed(
        title=f"{icon} {line_name}"[:256],
        color=discord.Color.dark_blue(),
    )

    if current_id in stations and player:
        st = MAP_DATA["станции"].get(current_id, {})
        embed.description = (
            f"📍 Вы на: **{st.get('name', current_id)}** "
            f"{DANGER_EMOJI.get(st.get('danger', 0), '⬤')}\n"
            f"Станций: **{len(stations)}**"
        )
    else:
        embed.description = f"Станций на линии: **{len(stations)}**"

    segments = _build_line_segments(line_id, current_id, player)
    if not segments:
        embed.add_field(name="📭 Пусто", value="Станции не найдены.", inline=False)
        embed.set_footer(text=_build_legend())
        return embed

    value = "\n".join(segments)
    if len(value) > 1024:
        cut = 0
        total = 0
        for idx, seg in enumerate(segments):
            total += len(seg) + 1
            if total > 1024:
                cut = idx
                break
        first = "\n".join(segments[:cut])[:1024]
        second = "\n".join(segments[cut:])[:1024]

        embed.add_field(name="🛤️ Схема (1)", value=first, inline=False)
        if second:
            embed.add_field(name="🛤️ Схема (2)", value=second, inline=False)
    else:
        embed.add_field(name="🛤️ Схема", value=value, inline=False)

    embed.set_footer(text=_build_legend())

    if len(embed) > MAX_EMBED_LEN:
        while len(embed) > MAX_EMBED_LEN and embed.fields:
            embed.remove_field(len(embed.fields) - 1)

    return embed


def build_embed_for_page(page: int, player=None) -> discord.Embed:
    if page <= 0:
        return build_overview_embed(player)
    line_order = _get_line_order()
    idx = page - 1
    if 0 <= idx < len(line_order):
        return build_line_embed(line_order[idx], player)
    return build_overview_embed(player)


# ==================== PERSISTENT VIEW ====================

def _get_max_page() -> int:
    return len(_get_line_order())


class MapPaginationView(discord.ui.View):
    """Persistent view. timeout=None. custom_id фиксированы."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="◀ Назад",
        style=discord.ButtonStyle.secondary,
        custom_id="map_nav_prev",
        row=0,
    )
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = self._get_current_page_from_message(interaction)
        target = max(0, current - 1)
        await self._render(interaction, target)

    @discord.ui.button(
        label="📋 Обзор",
        style=discord.ButtonStyle.primary,
        custom_id="map_nav_overview",
        row=0,
    )
    async def overview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, 0)

    @discord.ui.button(
        label="Вперёд ▶",
        style=discord.ButtonStyle.secondary,
        custom_id="map_nav_next",
        row=0,
    )
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = self._get_current_page_from_message(interaction)
        target = min(_get_max_page(), current + 1)
        await self._render(interaction, target)

    @discord.ui.button(
        label="🟠 КРЛ",
        style=discord.ButtonStyle.secondary,
        custom_id="map_line_0",
        row=1,
    )
    async def line_0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, 1)

    @discord.ui.button(
        label="⬜ СТЛ",
        style=discord.ButtonStyle.secondary,
        custom_id="map_line_1",
        row=1,
    )
    async def line_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, 2)

    @discord.ui.button(
        label="🟤 Кол.",
        style=discord.ButtonStyle.secondary,
        custom_id="map_line_2",
        row=1,
    )
    async def line_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, 3)

    @discord.ui.button(
        label="🟢 Ках.",
        style=discord.ButtonStyle.secondary,
        custom_id="map_line_3",
        row=1,
    )
    async def line_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, 4)

    @discord.ui.button(
        label="🟢 Зам.",
        style=discord.ButtonStyle.secondary,
        custom_id="map_line_4",
        row=2,
    )
    async def line_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, 5)

    @discord.ui.button(
        label="🔷 Бут.",
        style=discord.ButtonStyle.secondary,
        custom_id="map_line_5",
        row=2,
    )
    async def line_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, 6)

    @discord.ui.button(
        label="🔙 Назад в меню",
        style=discord.ButtonStyle.danger,
        custom_id="map_back_to_menu",
        row=3,
    )
    async def back_to_menu_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from utils.logger import get_logger
        logger = get_logger()

        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.errors.NotFound:
            return
        except discord.errors.InteractionResponded:
            pass

        try:
            from ..game_manager import game_manager
            player = game_manager.get_player(interaction.user.id)
        except Exception:
            player = None

        try:
            if player:
                from ..map_data import MAP_DATA
                station_data = MAP_DATA["станции"].get(player.location, {})
                total_hp = player.get_total_health()
                max_hp = player.get_max_total_health()

                embed = discord.Embed(
                    title="🎮 Меню 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍",
                    description=f"Добро пожаловать, **{player.name}**!\nУровень: **{player.level}**",
                    color=discord.Color.blue(),
                )
                embed.add_field(name="❤️ Здоровье", value=f"{total_hp:.1f}/{max_hp:.1f}", inline=True)
                embed.add_field(name="🏃 Выносливость", value=f"{player.stamina:.1f}/{player.max_stamina}", inline=True)
                embed.add_field(name="📍 Локация", value=station_data.get("name", "?"), inline=True)
                embed.add_field(name="💰 Никели", value=player.inventory.get('никели', 0), inline=True)

                from .main_menu import MainMenu
                await interaction.edit_original_response(embed=embed, view=MainMenu(player))
            else:
                await interaction.edit_original_response(
                    content="❌ Персонаж не найден. Введите /start.",
                    embed=None, view=None,
                )
        except Exception as e:
            logger.error(f"[MAP] back_to_menu: {e}", exc_info=True)

    def _get_current_page_from_message(self, interaction: discord.Interaction) -> int:
        try:
            msg = interaction.message
            if not msg or not msg.embeds:
                return 0
            embed = msg.embeds[0]
            title = embed.title or ""

            if "Карта 𝟒𝟒 𝐖𝐇𝐈𝐓𝐄 𝐂𝐔𝐑𝐓𝐀𝐈𝐍" in title:
                return 0

            line_order = _get_line_order()
            for idx, line_id in enumerate(line_order):
                line_data = LINES.get(line_id, {})
                line_name = line_data.get("name", LINE_NAMES.get(line_id, line_id))
                if line_name in title:
                    return idx + 1
        except Exception:
            pass
        return 0

    async def _render(self, interaction: discord.Interaction, page: int):
        from utils.logger import get_logger
        logger = get_logger()

        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.errors.NotFound:
            return
        except discord.errors.InteractionResponded:
            pass
        except Exception as e:
            logger.error(f"[MAP] defer: {e}")
            return

        try:
            from ..game_manager import game_manager
            player = game_manager.get_player(interaction.user.id)
        except Exception:
            player = None

        try:
            embed = build_embed_for_page(page, player)
        except Exception as e:
            logger.error(f"[MAP] build_embed: {e}", exc_info=True)
            return

        try:
            await interaction.edit_original_response(embed=embed)
        except discord.errors.NotFound:
            pass
        except Exception as e:
            logger.error(f"[MAP] edit: {e}", exc_info=True)


# ==================== СОВМЕСТИМОСТЬ ====================

def build_map_embed(player=None) -> discord.Embed:
    return build_overview_embed(player)


def build_map_view(player=None):
    return MapPaginationView()