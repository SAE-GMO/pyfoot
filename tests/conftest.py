"""Gemeinsame Testvorbereitung.

Die Tests laufen ohne sichtbares Fenster. Dazu wird der pygame-Grafiktreiber
auf 'dummy' gesetzt, bevor pygame das erste Mal importiert wird.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from pyfoot.engine import Engine  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_engine() -> None:
    """Sorgt dafuer, dass jeder Test mit einer frischen Engine startet.

    Zurueckgesetzt werden auch die angemeldeten Ordner fuer eigene Klassen:
    Sie sind eine Einstellung des ganzen Programms, und ein Test, der sie
    setzt, duerfte den naechsten nicht beeinflussen.
    """
    from pyfoot.editor import codegen

    codegen._actor_folder = None
    codegen._world_folder = None
    Engine._reset_for_tests()
