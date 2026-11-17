# -*- coding: utf-8 -*-
# func/views/trade/__init__.py - Пакет торговли (0.4.8.8)
#
# ИСТОРИЯ:
#   0.4.4.6 — рефакторинг, разбит на модули.
#   0.4.8.8 — переход на 2 страницы (удален page3).

from ._helpers import (
    TOTAL_TRADE_PAGES,
    _build_trade_page_embed,
    _build_workshop_embed,
    _safe_defer,
    _safe_edit,
    _safe_followup,
)
from .pagination import _TradePaginationMixin
from .page1 import TradePage1Menu
from .page2 import TradePage2Menu
from .factory import build_trade_view, TradeMenu
from .workshop import WorkshopMenu

__all__ = [
    "TOTAL_TRADE_PAGES",
    "_build_trade_page_embed",
    "_build_workshop_embed",
    "_safe_defer",
    "_safe_edit",
    "_safe_followup",
    "_TradePaginationMixin",
    "TradePage1Menu",
    "TradePage2Menu",
    "build_trade_view",
    "TradeMenu",
    "WorkshopMenu",
]