"""Tests fuer Bildlauf und Rueckmeldung (Editor-Anforderungen C7 und C8).

Beides geht auf Befunde des Auftraggebers vom 18.09.2026 zurueck:

    C7  Eine Welt, die groesser ist als das Fenster, laesst sich rollen.
        Vorher war nur die obere linke Ecke erreichbar.
    C8  Gelungenes wird gruen gemeldet. Vorher sah `Welt sichern` aus wie
        nichts -- und wurde mehrfach gedrueckt.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from pyfoot import Image, World, get_engine
from pyfoot.editor.panel import STATUS_COLORS, ControlPanel
from pyfoot.engine import Engine

CELL = 40


def ui_engine(width: int = 6, height: int = 6) -> Engine:
    """Eine Engine mit Oberflaeche und einer Welt der angegebenen Groesse."""
    engine = get_engine()
    engine.enable_ui()
    engine.step_duration = 0.0
    engine.set_world(World(width, height, cell_size=CELL))
    return engine


def grosse_welt() -> Engine:
    """Eine Welt, die deutlich groesser ist als das Fenster."""
    engine = ui_engine(40, 40)
    engine.resize_window((700, 500))
    return engine


def wheel(y: int = -1, x: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEWHEEL, {"x": x, "y": y, "flipped": False})


def press(position: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": position, "button": 1})


def drag(position: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": position, "rel": (0, 0), "buttons": (1, 0, 0)})


def release(position: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": position, "button": 1})


# ----------------------------------------------------------------------
# C7 -- Bildlauf
# ----------------------------------------------------------------------


def test_eine_kleine_welt_braucht_keine_leisten() -> None:
    engine = ui_engine()

    assert engine.scroll_limits() == (0, 0)
    assert engine.scrollbars() == {}


def test_eine_grosse_welt_bekommt_beide_leisten() -> None:
    engine = grosse_welt()

    limit_x, limit_y = engine.scroll_limits()
    assert limit_x > 0 and limit_y > 0
    bars = engine.scrollbars()
    assert "vertical" in bars and "horizontal" in bars
    # Die Leisten liegen am Rand des Weltausschnitts, nicht unter der
    # Klassenanzeige oder der Bedienleiste.
    view_width, view_height = engine.world_view()
    assert bars["vertical"].right == view_width
    assert bars["horizontal"].bottom == view_height


def test_die_verschiebung_bleibt_in_den_grenzen() -> None:
    engine = grosse_welt()
    limit_x, limit_y = engine.scroll_limits()

    engine.scroll_to(-50, 10_000)

    assert engine.scroll == (0, limit_y)
    engine.scroll_by(10_000, -10_000)
    assert engine.scroll == (limit_x, 0)


def test_die_welt_zeigt_den_verschobenen_ausschnitt() -> None:
    engine = grosse_welt()

    engine.scroll_to(120, 80)

    assert engine.world_origin() == (-120, -80)


def test_eine_kleine_welt_bleibt_mittig() -> None:
    """Anforderung C6 bleibt: Was passt, steht in der Mitte."""
    engine = ui_engine()
    engine.resize_window((900, 700))

    left, top = engine.world_origin()

    assert left > 0 and top > 0
    assert engine.scroll == (0, 0)


def test_das_mausrad_rollt_die_welt() -> None:
    engine = grosse_welt()

    engine._dispatch_event(wheel(y=-1))

    assert engine.scroll[1] == CELL
    engine._dispatch_event(wheel(y=1))
    assert engine.scroll[1] == 0


def test_mausrad_mit_umschalt_rollt_seitwaerts() -> None:
    engine = grosse_welt()

    pygame.key.set_mods(pygame.KMOD_LSHIFT)
    try:
        engine._dispatch_event(wheel(y=-1))
    finally:
        pygame.key.set_mods(0)

    assert engine.scroll == (CELL, 0)


def test_der_schieber_laesst_sich_ziehen() -> None:
    engine = grosse_welt()
    bars = engine.scrollbars()
    thumb = bars["vertical_thumb"]

    engine._dispatch_event(press(thumb.center))
    engine._dispatch_event(drag((thumb.centerx, bars["vertical"].bottom)))
    engine._dispatch_event(release((thumb.centerx, bars["vertical"].bottom)))

    assert engine.scroll[1] == engine.scroll_limits()[1], "Ganz nach unten gezogen."


def test_ein_klick_auf_die_leiste_springt_dorthin() -> None:
    engine = grosse_welt()
    track = engine.scrollbars()["horizontal"]

    engine._dispatch_event(press((track.right - 2, track.centery)))

    assert engine.scroll[0] == engine.scroll_limits()[0]


def test_ein_klick_auf_die_leiste_setzt_kein_objekt() -> None:
    """Sonst landete beim Rollen ein Objekt in der Welt."""
    from pyfoot import Actor

    class Stone(Actor):
        __slots__ = ()

        def __init__(self) -> None:
            super().__init__(image=Image.blank(4, 4))

    engine = grosse_welt()
    mode = engine.edit_mode
    assert mode is not None
    mode.enable()
    mode.select_class(Stone)
    track = engine.scrollbars()["vertical"]

    engine._dispatch_event(press((track.centerx, track.top + 30)))

    assert engine.world.number_of_objects() == 0


def test_das_feld_unter_der_maus_stimmt_nach_dem_rollen() -> None:
    engine = grosse_welt()
    mode = engine.edit_mode
    assert mode is not None

    engine.scroll_to(3 * CELL, 2 * CELL)

    assert mode.cell_at((0, 0)) == (3, 2)


def test_das_fenster_wird_nicht_groesser_als_der_bildschirm() -> None:
    """Sonst reichte eine 25-mal-25-Welt unter den Bildschirmrand."""
    engine = get_engine()
    engine.enable_ui()
    engine.set_world(World(60, 60, cell_size=CELL))

    breite, hoehe = engine._window_size()

    schirm = pygame.display.get_desktop_sizes()[0]
    assert breite < schirm[0] and hoehe < schirm[1]
    assert engine.scroll_limits() != (0, 0)


def test_ein_weltwechsel_beginnt_oben_links() -> None:
    engine = grosse_welt()
    engine.scroll_to(200, 200)

    engine.set_world(World(40, 40, cell_size=CELL))

    assert engine.scroll == (0, 0)


def test_die_leisten_lassen_sich_zeichnen() -> None:
    engine = grosse_welt()

    engine._render()

    assert engine.scrollbars()["vertical"].width == Engine.SCROLLBAR_SIZE


# ----------------------------------------------------------------------
# C8 -- gruene Rueckmeldung
# ----------------------------------------------------------------------


def test_eine_meldung_ist_zunaechst_schlicht() -> None:
    engine = ui_engine()

    engine.status = "PowerUp entfernt."

    assert engine.status_kind == "info"
    assert STATUS_COLORS["info"] != STATUS_COLORS["success"]


def test_gesicherte_welt_wird_gruen_gemeldet(tmp_path: Path) -> None:
    """Der Befund: Ohne Bestaetigung wurde dauernd weitergeklickt."""
    import importlib
    import sys

    from pyfoot.editor import codegen

    ordner = tmp_path / "view_project"
    ordner.mkdir()
    (ordner / "__init__.py").write_text("", encoding="utf-8")
    (ordner / "arena.py").write_text(
        "from pyfoot import World\n\n\nclass Arena(World):\n"
        "    __slots__ = ()\n\n    def __init__(self) -> None:\n"
        "        super().__init__(6, 6, cell_size=40)\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        cls = getattr(importlib.import_module("view_project.arena"), "Arena")
        engine = get_engine()
        engine.enable_ui()
        engine.set_world(cls())

        engine.request_save()

        assert engine.status_kind == "success", engine.status
        assert "gesichert" in engine.status
        assert STATUS_COLORS["success"] == (126, 214, 150), "Gruen."
        assert "prepare" in (ordner / "arena.py").read_text(encoding="utf-8")
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.split(".")[0] == "view_project"]:
            del sys.modules[name]
        codegen.set_class_folders()


def test_ein_fehler_wird_rot_gemeldet() -> None:
    engine = ui_engine()
    try:
        _ = 1 // 0
    except ZeroDivisionError as error:
        engine.report_error(error)

    assert engine.status_kind == "error"


def test_eine_warnung_bleibt_orange() -> None:
    engine = ui_engine()

    engine.set_status("Achtung: prepare() enthaelt eigenen Code.", "warning")

    assert engine.status_kind == "warning"
    assert STATUS_COLORS["warning"] != STATUS_COLORS["success"]


def test_die_leiste_zeichnet_die_meldung() -> None:
    engine = ui_engine()
    engine.set_status("Alles gesichert.", "success")
    panel = engine.panel
    assert panel is not None

    surface = pygame.Surface((ControlPanel.MIN_WIDTH, ControlPanel.HEIGHT))
    panel.render(surface)

    farbe = surface.get_at((14, ControlPanel.HEIGHT - 15))
    assert (farbe.r, farbe.g, farbe.b) != (0, 0, 0)
