# -*- coding: utf-8 -*-
# func/views/faction_npc/__init__.py - Публичный API NPC-диалогов (0.4.8)

from .dialog_view import DialogView, build_npc_embed
from .dialog_trees import DIALOG_TREES
from .npc_list import NPCPickerView, build_npc_list_embed

__all__ = [
    "DialogView",
    "build_npc_embed",
    "DIALOG_TREES",
    "NPCPickerView",
    "build_npc_list_embed",
]