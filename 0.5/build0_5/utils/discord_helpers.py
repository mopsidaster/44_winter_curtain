# -*- coding: utf-8 -*-
# utils/discord_helpers.py - Безопасные обёртки над Discord interaction (0.4.4.8)
#
# Единые safe-хелперы для всех views/команд:
#   • safe_defer   — defer без падения на NotFound/InteractionResponded
#   • safe_edit    — edit_original_response с логированием
#   • safe_followup— followup.send с логированием
#
# Раньше эти три функции копировались по каждому пакету (trade, combat_views,
# weapon_shop, equipment, commands). Теперь — единый источник правды.

import discord
from utils.logger import get_logger

logger = get_logger()


async def safe_defer(interaction: discord.Interaction) -> bool:
    """
    Безопасно сделать defer. Возвращает True, если можно продолжать работу
    (в т.ч. если interaction уже был отвечен ранее).

    Ловит:
      • NotFound          — interaction истёк (3 сек). Логируем и возвращаем False.
      • InteractionResponded — уже отвечен. Возвращаем True (можно продолжать).
      • Прочее            — логируем и возвращаем False.
    """
    try:
        if interaction.response.is_done():
            return True
        await interaction.response.defer()
        return True
    except discord.errors.NotFound:
        logger.warning("⚠️ Interaction истёк (NotFound) — defer пропущен")
        return False
    except discord.errors.InteractionResponded:
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка defer: {e}")
        return False


async def safe_edit(
        interaction: discord.Interaction,
        *,
        embed=None,
        view=None,
        content=None,
) -> bool:
    """
    Безопасно отредактировать исходное сообщение (edit_original_response).

    Поддерживает передачу embed/view/content. Любые из них могут быть None.
    """
    try:
        kwargs = {}
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view
        if content is not None:
            kwargs["content"] = content

        await interaction.edit_original_response(**kwargs)
        return True
    except discord.errors.NotFound:
        logger.warning("⚠️ Interaction истёк (NotFound) — edit пропущен")
        return False
    except discord.errors.HTTPException as e:
        logger.error(f"❌ HTTP ошибка edit: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка edit: {e}")
        return False


async def safe_followup(interaction: discord.Interaction, **kwargs) -> bool:
    """
    Безопасно отправить followup-сообщение.

    Все kwargs передаются в followup.send() как есть.
    """
    try:
        await interaction.followup.send(**kwargs)
        return True
    except discord.errors.NotFound:
        logger.warning("⚠️ Interaction истёк (NotFound) — followup пропущен")
        return False
    except discord.errors.HTTPException as e:
        logger.error(f"❌ HTTP ошибка followup: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка followup: {e}")
        return False