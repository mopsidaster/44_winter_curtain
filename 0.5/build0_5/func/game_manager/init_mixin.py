# -*- coding: utf-8 -*-
# func/game_manager/init_mixin.py - Инициализация GameManager (0.4.4.8)
#
# Рефакторинг без изменения логики.

from utils.logger import get_logger

logger = get_logger()


class GameManagerInitMixin:
    """
    Миксин инициализации GameManager.

    Содержит только __init__ со всеми флагами глобальных ивентов,
    зонами (frost/celebration/fire/workshop/breach) и игроками.
    """

    def __init__(self):
        self.players: dict = {}
        self.game_channel = None
        self.is_active = False
        self.global_buffs = []

        # Флаги активных глобальных ивентов
        self.trade_discount_active = False
        self.mutant_wave_active = False
        self.loot_boost_active = False
        self.flood_active = False
        self.radiation_spike_active = False
        self.hunt_bonus_active = False
        self.power_outage_active = False
        self.shop_sale_active = False
        self.x2_exp_active = False
        self.earthquake_active = False
        self.gas_leak_active = False
        self.station_celebration_active = False
        self.station_fire_active = False
        self.stalker_workshop_active = False
        self.mutant_breach_active = False

        # Зона заморозки
        self.frost_active = False
        self.frost_station = None
        self.frost_connections = []

        # Точки-триггеры ивентов
        self.celebration_station = None
        self.fire_station = None
        self.workshop_station = None
        self.breach_station = None

        logger.info("GameManager инициализирован (Билд 0.4.4.7)")