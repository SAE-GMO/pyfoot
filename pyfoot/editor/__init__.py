"""Die Oberflaeche von PyFoot.

Die Oberflaeche ist eine Ergaenzung, kein Ersatz: Ohne ausdrueckliche
Aktivierung verhaelt sich PyFoot wie bisher, und jedes Programm laeuft
unveraendert von der Kommandozeile (Editor-Anforderungsdokument 2.1, F1).

Eingeschaltet wird sie mit:
    import pyfoot
    pyfoot.enable_ui()
"""

from __future__ import annotations

from . import codegen, source
from .menu import ContextMenu, Inspector, MenuEntry, TextPrompt
from .mode import EditMode
from .panel import Button, ControlPanel
from .sidebar import ClassRow, ClassSidebar

__all__ = [
    "Button",
    "ClassRow",
    "ClassSidebar",
    "ContextMenu",
    "ControlPanel",
    "EditMode",
    "Inspector",
    "MenuEntry",
    "TextPrompt",
    "codegen",
    "source",
]
