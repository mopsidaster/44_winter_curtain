# -*- coding: utf-8 -*-
# func/views/trade/factory.py - Фабрика (0.4.8.8)

from .page1 import TradePage1Menu
from .page2 import TradePage2Menu


def build_trade_view(player, page: int = 1):
    """Возвращает view для указанной страницы."""
    if page == 1:
        return TradePage1Menu(player)
    else:
        return TradePage2Menu(player)


class TradeMenu:
    """Обёртка-фабрика."""
    def __new__(cls, player, page: int = 1):
        return build_trade_view(player, page)