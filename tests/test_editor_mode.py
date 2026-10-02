"""Tests fuer den Bearbeitungsmodus (Editor-Anforderungsdokument, Stufe E3).

Geprueft werden:
    A1  Objekte platzieren, mehrfach ohne erneute Auswahl
    A2  Objekte entfernen
    A3  Objekte verschieben
    C1  jede Funktion ist mit der Maus erreichbar
    C2  dieselben Funktionen sind ueber die Tastatur erreichbar
    F1  ohne Bearbeitungsmodus bleibt alles wie bisher
"""

from __future__ import annotations

import pygame

from pyfoot import Actor, Image, ScriptActor, World, get_engine
from pyfoot.editor.mode import EditMode, can_construct, placeable_classes
from pyfoot.editor.sidebar import ClassSidebar
from pyfoot.engine import Engine

CELL = 20


class Rock(Actor):
    """Ein setzbarer Akteur."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))


class Gem(Actor):
    """Ein zweiter setzbarer Akteur."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))


class Signpost(Actor):
    """Ein Akteur, der einen Wert braucht -- nicht setzbar."""

    __slots__ = ()

    def __init__(self, text: str) -> None:
        super().__init__(image=Image.blank(4, 4))


class Runner(ScriptActor):
    """Ein abstrakter Nachfahre bleibt aussen vor, dieser hier nicht."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))

    def init(self) -> None:
        self.move()


def prepared(width: int = 10, height: int = 8) -> tuple[Engine, World, EditMode]:
    """Baut eine Welt mit eingeschalteter Oberflaeche und Bearbeitungsmodus."""
    engine = get_engine()
    engine.enable_ui()
    engine.step_duration = 0.0
    world = World(width, height, cell_size=CELL)
    engine.set_world(world)
    mode = engine.edit_mode
    assert mode is not None
    mode.enable()
    mode.select_class(Rock)
    return engine, world, mode


def at(engine: Engine, x: int, y: int) -> tuple[int, int]:
    """Rechnet ein Feld in eine Fensterposition um."""
    left, top = engine.world_origin()
    return left + x * CELL + CELL // 2, top + y * CELL + CELL // 2


def down(engine: Engine, x: int, y: int, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": at(engine, x, y), "button": button}
    )


def motion(engine: Engine, x: int, y: int, held: bool = False) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION,
        {"pos": at(engine, x, y), "buttons": (1 if held else 0, 0, 0), "rel": (0, 0)},
    )


def up(engine: Engine, x: int, y: int) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEBUTTONUP, {"pos": at(engine, x, y), "button": 1}
    )


def key(code: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, {"key": code, "mod": 0, "unicode": ""})


# ----------------------------------------------------------------------
# Welche Klassen lassen sich setzen
# ----------------------------------------------------------------------


def test_klasse_ohne_werte_laesst_sich_setzen() -> None:
    assert can_construct(Rock) is True


def test_klasse_mit_pflichtwert_laesst_sich_nicht_setzen() -> None:
    assert can_construct(Signpost) is False


def test_abstrakte_klasse_laesst_sich_nicht_setzen() -> None:
    assert can_construct(ScriptActor) is False


def test_bausteine_von_pyfoot_erscheinen_nicht_in_der_liste() -> None:
    """PyFoot-eigene Klassen sind Bauteile, keine Spielfiguren."""
    classes = placeable_classes()

    assert all(not c.__module__.startswith("pyfoot") for c in classes)
    assert Rock in classes and Gem in classes
    assert Signpost not in classes


# ----------------------------------------------------------------------
# F1 -- ohne Bearbeitungsmodus bleibt alles wie bisher
# ----------------------------------------------------------------------


def test_ohne_bearbeitungsmodus_wird_kein_ereignis_verbraucht() -> None:
    engine, _, mode = prepared()
    mode.enable(False)

    assert mode.handle_event(down(engine, 2, 2)) is False


def test_ohne_bearbeitungsmodus_entsteht_nichts() -> None:
    engine, world, mode = prepared()
    mode.enable(False)

    mode.handle_event(down(engine, 2, 2))

    assert world.number_of_objects() == 0


# ----------------------------------------------------------------------
# A1 -- Objekte platzieren
# ----------------------------------------------------------------------


def test_klick_setzt_ein_objekt_der_gewaehlten_klasse() -> None:
    engine, world, mode = prepared()

    mode.handle_event(down(engine, 3, 4))

    assert world.number_of_objects() == 1
    placed: list[Actor] = world.objects_at(3, 4)
    assert isinstance(placed[0], Rock)


def test_mehrfaches_setzen_ohne_erneute_auswahl() -> None:
    """Der Kern von A1."""
    engine, world, mode = prepared()

    for x in range(4):
        mode.handle_event(down(engine, x, 1))

    assert world.number_of_objects() == 4
    assert mode.selected_class is Rock


def test_die_gewaehlte_klasse_bestimmt_das_objekt() -> None:
    engine, world, mode = prepared()
    mode.select_class(Gem)

    mode.handle_event(down(engine, 1, 1))

    assert isinstance(world.objects_at(1, 1)[0], Gem)


def test_ausserhalb_der_welt_entsteht_nichts() -> None:
    engine, world, mode = prepared()
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (-50, -50), "button": 1})

    assert mode.handle_event(event) is False
    assert world.number_of_objects() == 0


def test_setzen_ohne_ausgewaehlte_klasse_bewirkt_nichts() -> None:
    engine, world, mode = prepared()
    mode.select_class(None)

    mode.handle_event(down(engine, 2, 2))

    assert world.number_of_objects() == 0


def test_umschalt_setzt_auch_auf_ein_belegtes_feld() -> None:
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 2, 2))

    pygame.key.set_mods(pygame.KMOD_LSHIFT)
    try:
        mode.handle_event(down(engine, 2, 2))
    finally:
        pygame.key.set_mods(0)

    assert len(world.objects_at(2, 2)) == 2


# ----------------------------------------------------------------------
# A2 -- Objekte entfernen
# ----------------------------------------------------------------------


def test_rechtsklick_oeffnet_das_menue_des_objekts() -> None:
    """Seit E6 fuehrt der Rechtsklick zum Kontextmenue, wie in Greenfoot."""
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 2, 2))

    mode.handle_event(down(engine, 2, 2, button=3))

    menu = engine.menu
    assert menu is not None
    assert menu.title == "Rock"
    assert world.number_of_objects() == 1, "Der Rechtsklick allein loescht nicht."


def test_das_menue_entfernt_das_objekt() -> None:
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 2, 2))
    mode.handle_event(down(engine, 2, 2, button=3))

    menu = engine.menu
    assert menu is not None
    labels = [entry.label for entry in menu.entries]
    menu.choose(labels.index("Entfernen"))

    assert world.number_of_objects() == 0


def test_entf_taste_entfernt_das_ausgewaehlte_objekt() -> None:
    """Anforderung C2: derselbe Befehl ueber die Tastatur."""
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 2, 2))
    mode.select_at(2, 2)

    assert mode.handle_event(key(pygame.K_DELETE)) is True
    assert world.number_of_objects() == 0


def test_entfernen_ohne_auswahl_bewirkt_nichts() -> None:
    engine, _, mode = prepared()

    assert mode.remove_selected() is False


def test_nach_dem_entfernen_ist_nichts_mehr_ausgewaehlt() -> None:
    engine, _, mode = prepared()
    mode.handle_event(down(engine, 2, 2))
    mode.select_at(2, 2)
    mode.remove_selected()

    assert mode.selected_actor is None


# ----------------------------------------------------------------------
# A3 -- Objekte verschieben
# ----------------------------------------------------------------------


def test_ziehen_verschiebt_ein_objekt() -> None:
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 1, 1))  # setzen
    mode.handle_event(down(engine, 1, 1))  # auswaehlen und Ziehen beginnen

    mode.handle_event(motion(engine, 5, 3, held=True))
    mode.handle_event(up(engine, 5, 3))

    assert world.objects_at(1, 1) == []
    assert len(world.objects_at(5, 3)) == 1


def test_ohne_gedrueckte_taste_wird_nichts_verschoben() -> None:
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 1, 1))
    mode.handle_event(up(engine, 1, 1))

    mode.handle_event(motion(engine, 5, 3))

    assert len(world.objects_at(1, 1)) == 1


def test_ein_klick_auf_ein_objekt_waehlt_es_aus() -> None:
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 1, 1))

    mode.handle_event(down(engine, 1, 1))

    assert mode.selected_actor is world.objects_at(1, 1)[0]


def test_verschieben_ueber_den_rand_hinaus_wird_abgewiesen() -> None:
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 1, 1))
    mode.select_at(1, 1)

    assert mode.move_selected(99, 99) is False
    assert len(world.objects_at(1, 1)) == 1


# ----------------------------------------------------------------------
# C1 und C2 -- Klassenanzeige mit Maus und Tastatur
# ----------------------------------------------------------------------


def sidebar_of(engine: Engine) -> ClassSidebar:
    """Liefert die Klassenanzeige und stellt sicher, dass es sie gibt."""
    sidebar = engine.sidebar
    assert sidebar is not None
    return sidebar


def test_ziffern_waehlen_eine_klasse() -> None:
    engine, _, mode = prepared()
    classes = mode.classes

    mode.handle_event(key(pygame.K_2))

    assert mode.selected_class is classes[1]


def test_eine_ziffer_ohne_klasse_dahinter_aendert_nichts() -> None:
    engine, _, mode = prepared()
    mode.select_class(Gem)

    mode.handle_event(key(pygame.K_9))

    assert mode.selected_class is Gem or len(mode.classes) >= 9


def test_die_taste_b_schaltet_den_bearbeitungsmodus_um() -> None:
    engine, _, mode = prepared()
    sidebar = sidebar_of(engine)

    assert sidebar.handle_event(key(pygame.K_b), engine.sidebar_left()) is True
    assert mode.enabled is False

    sidebar.handle_event(key(pygame.K_b), engine.sidebar_left())
    assert mode.enabled is True


def test_klick_auf_bearbeiten_schaltet_ebenfalls_um() -> None:
    engine, _, mode = prepared()
    sidebar = sidebar_of(engine)
    rect = sidebar.edit_button
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": (engine.sidebar_left() + rect.centerx, rect.centery), "button": 1},
    )

    sidebar.handle_event(event, engine.sidebar_left())

    assert mode.enabled is False


def test_klick_auf_eine_klassenzeile_waehlt_sie_aus() -> None:
    # Eine hohe Welt, damit der Baum ueberhaupt Platz hat.
    engine, _, mode = prepared(height=24)
    sidebar = sidebar_of(engine)
    sidebar.render(pygame.Surface((ClassSidebar.WIDTH, engine._panel_top())))

    settable = [(row, rect) for row, rect in sidebar.rows if row.placeable]
    assert settable, "Die Klassenanzeige zeigt keine setzbare Klasse."

    row, rect = settable[-1]
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": (engine.sidebar_left() + rect.centerx, rect.centery), "button": 1},
    )
    sidebar.handle_event(event, engine.sidebar_left())

    assert mode.selected_class is row.cls


def test_klick_neben_die_klassenanzeige_wird_nicht_verbraucht() -> None:
    engine, _, _ = prepared()
    sidebar = sidebar_of(engine)
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (5, 5), "button": 1})

    assert sidebar.handle_event(event, engine.sidebar_left()) is False


def test_die_klassenanzeige_laesst_sich_ohne_bildschirm_zeichnen() -> None:
    """Auflage F2."""
    engine, _, _ = prepared()
    surface = pygame.Surface((ClassSidebar.WIDTH, engine._panel_top()))

    sidebar_of(engine).render(surface)


def test_die_welt_traegt_die_hervorhebungen() -> None:
    engine, world, mode = prepared()
    mode.handle_event(down(engine, 2, 2))
    mode.handle_event(motion(engine, 3, 3))
    surface = pygame.Surface((world.width * CELL, world.height * CELL))

    mode.render_overlay(surface)

    assert mode.hover == (3, 3)
