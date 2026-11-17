# -*- coding: utf-8 -*-
# func/__init__.py
import logging
from .game_manager import game_manager
from .player import Player
from .commands import setup_commands
from .social_commands import setup_social_commands
from .global_events import run_global_events
from .map_data import MAP_DATA, LINES

logger = logging.getLogger('metro_bot.func')
logger.info("🔄 Загрузка модуля func начата")

from .station_utils import has_station_type, is_trade_station, is_start_station

logger.info("✅ Модуль func загружен")
logger.info(f"   has_station_type: {has_station_type is not None}")
logger.info(f"   is_trade_station: {is_trade_station is not None}")
logger.info(f"   is_start_station: {is_start_station is not None}")