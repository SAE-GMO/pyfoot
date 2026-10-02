"""Tests fuer Maus- und Tastatureingabe (Anforderungsdokument 4.10.5).

Geprueft werden G5 und G6: Die Eingabe ist vorhanden, typisiert und
verhaelt sich nachvollziehbar. Dass sie im Kurs nicht verwendet wird (G7),
prueft das Basisprojekt in seinen eigenen Tests.
"""

from __future__ import annotations

import pygame

from pyfoot import Actor, Image, World, get_engine
from pyfoot.input import InputState, MouseInfo


class Probe(Actor):
    """Ein Akteur ohne eigenes Verhalten, nur als Ziel fuer Mausabfragen."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))


def click_event(x: int, y: int, button: int = 1) -> pygame.event.Event:
    """Baut ein Ereignis fuer einen losgelassenen Mausknopf."""
    return pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": (x, y), "button": button})


def key_event(key: int) -> pygame.event.Event:
    """Baut ein Ereignis fuer einen Tastendruck."""
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": ""})


# ----------------------------------------------------------------------
# Tastatur
# ----------------------------------------------------------------------


def test_gedrueckte_taste_wird_gemeldet() -> None:
    state = InputState()
    state.handle(key_event(pygame.K_LEFT))

    assert state.get_key() == "left"


def test_taste_wird_beim_abholen_verbraucht() -> None:
    state = InputState()
    state.handle(key_event(pygame.K_a))

    assert state.get_key() == "a"
    assert state.get_key() is None


def test_eingabetaste_heisst_enter() -> None:
    """Im Unterricht heisst die Taste 'enter', bei pygame 'return'."""
    state = InputState()
    state.handle(key_event(pygame.K_RETURN))

    assert state.get_key() == "enter"


def test_tasten_gelten_nur_fuer_einen_durchlauf() -> None:
    state = InputState()
    state.handle(key_event(pygame.K_b))
    state.begin_cycle()

    assert state.get_key() is None


# ----------------------------------------------------------------------
# Maus
# ----------------------------------------------------------------------


def test_klick_wird_in_feldkoordinaten_umgerechnet() -> None:
    state = InputState(cell_size=20)
    state.handle(click_event(45, 25))

    info = state.last_click()
    assert info is not None
    assert (info.x, info.y) == (2, 1)
    assert (info.pixel_x, info.pixel_y) == (45, 25)


def test_klick_auf_einen_akteur_wird_erkannt() -> None:
    world = World(10, 10, cell_size=20)
    probe = Probe()
    world.add_object(probe, 2, 1)

    state = InputState(cell_size=20)
    state.handle(click_event(45, 25))

    assert state.mouse_clicked(probe) is True


def test_klick_neben_dem_akteur_zaehlt_nicht() -> None:
    world = World(10, 10, cell_size=20)
    probe = Probe()
    world.add_object(probe, 5, 5)

    state = InputState(cell_size=20)
    state.handle(click_event(45, 25))

    assert state.mouse_clicked(probe) is False
    assert state.mouse_clicked() is True


def test_klick_gilt_nur_fuer_einen_durchlauf() -> None:
    state = InputState(cell_size=20)
    state.handle(click_event(45, 25))
    state.begin_cycle()

    assert state.mouse_clicked() is False


def test_ziehen_und_bewegen_werden_unterschieden() -> None:
    state = InputState(cell_size=20)
    state.handle(
        pygame.event.Event(pygame.MOUSEMOTION, {"pos": (10, 10), "buttons": (0, 0, 0)})
    )
    assert state.mouse_moved() is True
    assert state.mouse_dragged() is False

    state.begin_cycle()
    state.handle(
        pygame.event.Event(pygame.MOUSEMOTION, {"pos": (30, 10), "buttons": (1, 0, 0)})
    )
    assert state.mouse_dragged() is True
    assert state.mouse_moved() is False


def test_mausinfo_ist_lesbar() -> None:
    info = MouseInfo(1, 2, 30, 50, button=3, clicks=2)

    assert (info.x, info.y, info.button, info.clicks) == (1, 2, 3, 2)
    assert "MouseInfo" in repr(info)


# ----------------------------------------------------------------------
# Anbindung an die Laufzeitsteuerung
# ----------------------------------------------------------------------


def test_engine_stellt_den_eingabezustand_bereit() -> None:
    engine = get_engine()

    assert isinstance(engine.input, InputState)


def test_feldgroesse_wird_von_der_welt_uebernommen() -> None:
    engine = get_engine()
    engine.set_world(World(5, 5, cell_size=32))

    assert engine.input.cell_size == 32


def test_der_randstreifen_wird_nicht_mitgezaehlt() -> None:
    """Steht die Welt mittig im Fenster, muss der Rand herausgerechnet werden."""
    state = InputState(cell_size=20)
    state.origin = (60, 0)
    state.handle(click_event(105, 25))

    info = state.last_click()
    assert info is not None
    assert (info.x, info.y) == (2, 1)


def test_die_welt_steht_mittig_neben_der_klassenanzeige() -> None:
    from pyfoot.editor.sidebar import ClassSidebar

    engine = get_engine()
    engine.enable_ui()
    engine.set_world(World(8, 8, cell_size=20))

    width, _ = engine._window_size()
    available = width - ClassSidebar.WIDTH
    assert engine.world_origin() == ((available - 160) // 2, 0)
