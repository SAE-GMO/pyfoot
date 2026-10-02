"""Tests fuer die Bedienleiste (Editor-Anforderungsdokument, Stufen E1 und E2).

Geprueft werden:
    F1  Ohne Einschalten verhaelt sich PyFoot wie bisher.
    C1  Jede Funktion ist als Schaltflaeche mit der Maus erreichbar.
    C2  Dieselben Funktionen sind gleichrangig ueber die Tastatur erreichbar.
    C3  Anhalten und Einzelschritt greifen in eine laufende `init` ein.
    C4  Im Fenster ist erkennbar, welches Bedienelement gerade greift.
    E1  Anhalten, Fortsetzen, Zuruecksetzen, Geschwindigkeit.
    E2  Einzelschritt: je Druck genau eine Aktion.
"""

from __future__ import annotations

from typing import Callable, Iterator

import pygame
import pytest

from pyfoot import Image, ScriptActor, World, get_engine
from pyfoot.editor.panel import ControlPanel
from pyfoot.engine import Engine

CELL = 10


class Walker(ScriptActor):
    """Faehrt eine feste Anzahl Felder geradeaus."""

    __slots__ = ("steps",)

    def __init__(self, steps: int = 3) -> None:
        super().__init__(image=Image.blank(4, 4))
        self.steps = steps

    def init(self) -> None:
        for _ in range(self.steps):
            self.move()


class WalkerWorld(World):
    """Eine Welt, die ihren Akteur im Konstruktor einsetzt.

    So arbeiten auch die Kurswelten: Alles, was in ihnen steht, entsteht beim
    Bauen. `Zuruecksetzen` ruft den Konstruktor erneut auf -- die Welt ist
    danach dieselbe, ihre Akteure sind aber **neue Objekte**.
    """

    __slots__ = ()

    #: Wie viele Felder der eingesetzte Walker faehrt.
    STEPS: int = 3

    def __init__(self) -> None:
        super().__init__(20, 5, cell_size=CELL)
        self.add_object(Walker(steps=self.STEPS), 0, 0)


def walker_of(world: World) -> Walker:
    """Holt den Akteur aus der Welt -- nach einem Zuruecksetzen ein neuer."""
    walkers: list[Walker] = world.objects(Walker)
    assert walkers, "In der Welt steht kein Walker."
    return walkers[0]


def prepared_world(walker: Walker | None = None) -> tuple[Engine, World, Walker]:
    """Baut eine Welt mit eingeschalteter Oberflaeche auf.

    Der Akteur wird von aussen gesetzt. Diese Welt laesst sich zwar ohne
    Werte bauen, waere danach aber leer -- fuer Tests rund um das
    Zuruecksetzen ist deshalb `prepared_level` gedacht.
    """
    engine = get_engine()
    engine.enable_ui()
    engine.step_duration = 0.0
    world = World(20, 5, cell_size=CELL)
    actor = walker if walker is not None else Walker()
    world.add_object(actor, 0, 0)
    engine.set_world(world)
    return engine, world, actor


def prepared_level(steps: int = 3) -> tuple[Engine, World]:
    """Baut eine Welt, die ihren Akteur selbst mitbringt."""
    engine = get_engine()
    engine.enable_ui()
    engine.step_duration = 0.0

    class Level(WalkerWorld):
        __slots__ = ()
        STEPS = steps

    engine.set_world(Level())
    world = engine.world
    return engine, world


def panel_of(engine: Engine) -> ControlPanel:
    """Liefert die Bedienleiste und stellt sicher, dass es sie gibt."""
    panel = engine.panel
    assert panel is not None, "Die Bedienleiste fehlt, obwohl sie eingeschaltet ist."
    return panel


def press(panel: ControlPanel, key: int, offset_y: int = 0) -> bool:
    """Stellt einen Tastendruck nach."""
    event = pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": ""})
    return panel.handle_event(event, offset_y)


def click(panel: ControlPanel, x: int, y: int, offset_y: int) -> bool:
    """Stellt einen Mausklick auf das Fenster nach."""
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (x, y + offset_y), "button": 1}
    )
    return panel.handle_event(event, offset_y)


def click_button(panel: ControlPanel, action: str, offset_y: int) -> bool:
    """Klickt mitten auf die Schaltflaeche einer Funktion."""
    rect = panel.button(action).rect
    return click(panel, rect.centerx, rect.centery, offset_y)


# ----------------------------------------------------------------------
# F1 -- die Oberflaeche ist abschaltbar
# ----------------------------------------------------------------------


def test_ohne_einschalten_gibt_es_keine_bedienleiste() -> None:
    engine = get_engine()
    engine.set_world(World(8, 8, cell_size=CELL))

    assert engine.ui_enabled is False
    assert engine.panel is None
    assert engine.is_paused() is False


def test_ohne_oberflaeche_bleibt_das_fenster_so_gross_wie_die_welt() -> None:
    engine = get_engine()
    engine.set_world(World(8, 6, cell_size=CELL))

    assert engine._window_size() == (80, 60)


def test_mit_oberflaeche_waechst_das_fenster_um_die_leiste() -> None:
    engine, _, _ = prepared_world()
    width, height = engine._window_size()

    assert height == 5 * CELL + ControlPanel.HEIGHT
    assert width >= ControlPanel.MIN_WIDTH


def test_die_oberflaeche_laesst_sich_wieder_abschalten() -> None:
    engine, _, _ = prepared_world()
    engine.enable_ui(False)

    assert engine.panel is None
    assert engine.is_paused() is False


def test_mit_oberflaeche_wird_wie_in_greenfoot_angehalten_gestartet() -> None:
    engine, _, _ = prepared_world()

    assert engine.is_paused() is True


# ----------------------------------------------------------------------
# C1 und C2 -- Maus und Tastatur gleichrangig
# ----------------------------------------------------------------------


def test_jede_funktion_hat_eine_schaltflaeche() -> None:
    engine, _, _ = prepared_world()
    actions = {button.action for button in panel_of(engine).buttons}

    assert actions == {"play", "cycle", "step", "reset"}


def test_jede_schaltflaeche_ist_auch_ueber_die_tastatur_erreichbar() -> None:
    """Anforderung C2: keine Funktion darf nur auf einem Weg erreichbar sein."""
    engine, _, _ = prepared_world()
    for button in panel_of(engine).buttons:
        assert button.keys, f"Fuer '{button.action}' fehlt eine Taste."
        assert button.key_hint, f"Fuer '{button.action}' fehlt der Tastenhinweis."


def test_schaltflaechen_ueberlappen_sich_nicht() -> None:
    engine, _, _ = prepared_world()
    buttons = panel_of(engine).buttons
    for index, button in enumerate(buttons):
        for other in buttons[index + 1 :]:
            assert not button.rect.colliderect(other.rect)


def test_klick_auf_start_setzt_fort_und_haelt_wieder_an() -> None:
    engine, world, _ = prepared_world()
    panel = panel_of(engine)
    offset = world.height * CELL

    assert click_button(panel, "play", offset) is True
    assert engine.is_paused() is False

    click_button(panel, "play", offset)
    assert engine.is_paused() is True


def test_leertaste_bewirkt_dasselbe_wie_die_schaltflaeche() -> None:
    engine, _, _ = prepared_world()
    panel = panel_of(engine)

    assert press(panel, pygame.K_SPACE) is True
    assert engine.is_paused() is False


def test_klick_neben_die_leiste_wird_nicht_verbraucht() -> None:
    """Klicks in die Welt gehoeren dem Schuelercode, nicht der Leiste."""
    engine, world, _ = prepared_world()
    panel = panel_of(engine)
    offset = world.height * CELL
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (30, 20), "button": 1})

    assert panel.handle_event(event, offset) is False


def test_unbelegte_taste_wird_nicht_verbraucht() -> None:
    engine, _, _ = prepared_world()

    assert press(panel_of(engine), pygame.K_q) is False


# ----------------------------------------------------------------------
# E1 -- Geschwindigkeit
# ----------------------------------------------------------------------


def test_plus_und_minus_aendern_die_geschwindigkeit() -> None:
    engine, _, _ = prepared_world()
    panel = panel_of(engine)
    panel.set_speed_index(4)

    press(panel, pygame.K_PLUS)
    assert panel.speed_index() == 5

    press(panel, pygame.K_MINUS)
    assert panel.speed_index() == 4


def test_die_geschwindigkeit_bleibt_in_ihren_grenzen() -> None:
    engine, _, _ = prepared_world()
    panel = panel_of(engine)

    panel.set_speed_index(-5)
    assert panel.speed_index() == 0
    assert engine.step_duration == max(ControlPanel.SPEED_STEPS)

    panel.set_speed_index(999)
    assert panel.speed_index() == len(ControlPanel.SPEED_STEPS) - 1


def test_ziehen_am_regler_stellt_die_geschwindigkeit_ein() -> None:
    engine, world, _ = prepared_world()
    panel = panel_of(engine)
    offset = world.height * CELL
    slider = panel.slider

    click(panel, slider.left + 2, slider.centery, offset)
    assert panel.speed_index() == 0

    click(panel, slider.right - 2, slider.centery, offset)
    assert panel.speed_index() == len(ControlPanel.SPEED_STEPS) - 1


# ----------------------------------------------------------------------
# C4 -- erkennbar, was gerade greift
# ----------------------------------------------------------------------


def test_durchlauf_und_schritt_greifen_nur_im_angehaltenen_zustand() -> None:
    engine, _, _ = prepared_world()
    panel = panel_of(engine)

    assert panel.is_enabled("cycle") is True
    assert panel.is_enabled("step") is True

    engine.resume()
    assert panel.is_enabled("cycle") is False
    assert panel.is_enabled("step") is False


def test_die_beschriftung_zeigt_den_zustand() -> None:
    engine, _, _ = prepared_world()
    panel = panel_of(engine)

    assert panel.label_for("play") == "Start"
    engine.resume()
    assert panel.label_for("play") == "Pause"


def test_abgeschaltete_schaltflaeche_loest_nichts_aus() -> None:
    engine, world, _ = prepared_world()
    panel = panel_of(engine)
    engine.resume()

    click_button(panel, "cycle", world.height * CELL)
    assert engine._cycle_requested is False


def test_die_leiste_laesst_sich_ohne_bildschirm_zeichnen() -> None:
    """Auflage F2: Die Pruefung laeuft mit dem Treiber 'dummy'."""
    engine, _, _ = prepared_world()
    surface = pygame.Surface((ControlPanel.MIN_WIDTH, ControlPanel.HEIGHT))

    panel_of(engine).render(surface)


# ----------------------------------------------------------------------
# C3 und E2 -- Anhalten und Einzelschritt greifen in die laufende `init`
# ----------------------------------------------------------------------


def drive(
    monkeypatch: pytest.MonkeyPatch, engine: Engine, presses: list[str]
) -> None:
    """Laesst die Simulation laufen und stellt dabei Tastendruecke nach.

    Statt echter Fensterereignisse liefert die Ereignisschleife der Reihe
    nach die uebergebenen Bedienschritte.

    Danach wird das Fenster geschlossen -- allerdings erst, wenn nichts mehr
    passieren kann: Eine laufende Anweisungsfolge darf zu Ende laufen, eine
    angehaltene wird abgebrochen. Sonst wuerde der Abbruch die Messung
    verfaelschen oder der Test bliebe haengen.
    """
    remaining: Iterator[str] = iter(presses)
    actions: dict[str, Callable[[Engine], None]] = {
        "cycle": Engine.request_cycle,
        "step": Engine.request_step,
        "reset": Engine.request_reset,
        "play": Engine.toggle_pause,
    }

    def fake_pump(self: Engine) -> None:
        try:
            action = next(remaining)
        except StopIteration:
            if self._paused or not self._in_act_cycle:
                self._running = False
            return
        actions[action](self)

    monkeypatch.setattr(Engine, "_pump_events", fake_pump)
    engine.run()


def test_jeder_druck_fuehrt_genau_eine_aktion_aus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anforderung E2, der Kern des Einzelschritts."""
    engine, _, walker = prepared_world(Walker(steps=5))

    # 'Durchlauf' startet die Anweisungsfolge und fuehrt die erste Aktion aus,
    # jeder weitere 'Schritt' genau eine weitere.
    drive(monkeypatch, engine, ["cycle", "step", "step"])

    assert walker.x == 3


def test_ohne_schritt_geht_es_nicht_weiter(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, _, walker = prepared_world(Walker(steps=5))

    drive(monkeypatch, engine, ["cycle"])

    assert walker.x == 1, "Die Anweisungsfolge haette nach der ersten Aktion anhalten muessen."


def test_fortsetzen_laesst_die_anweisungsfolge_durchlaufen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, _, walker = prepared_world(Walker(steps=4))

    drive(monkeypatch, engine, ["cycle", "play"])

    assert walker.x == 4


def test_ohne_oberflaeche_laeuft_alles_wie_bisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gegenprobe zu F1: ohne Leiste kein Anhalten, kein Warten."""
    engine = get_engine()
    engine.step_duration = 0.0
    world = World(20, 5, cell_size=CELL)
    walker = Walker(steps=4)
    world.add_object(walker, 0, 0)
    engine.set_world(world)

    drive(monkeypatch, engine, ["cycle"])

    assert walker.x == 4


# ----------------------------------------------------------------------
# E1 -- Zuruecksetzen
# ----------------------------------------------------------------------


def test_zuruecksetzen_ruft_den_konstruktor_erneut_auf() -> None:
    """Die Welt entsteht neu, statt nur die Akteure zurueckzuschieben.

    Damit ist die Ausgangslage wirklich die, die im Quelltext steht -- und
    eine zufaellige Welt wird neu gewuerfelt.
    """
    engine, world = prepared_level(steps=3)
    walker = walker_of(world)

    world._act_cycle()
    assert (walker.x, walker.init_done) == (3, True)

    engine.reset()

    assert engine.world is not world, "Es muss eine frische Welt sein."
    frisch = walker_of(engine.world)
    assert frisch is not walker, "Auch der Akteur entsteht neu."
    assert (frisch.x, frisch.y) == (0, 0)
    assert frisch.init_done is False, "Die Anweisungsfolge muss erneut laufen duerfen."


def test_zuruecksetzen_entfernt_spaeter_hinzugekommene_akteure() -> None:
    engine, world = prepared_level()
    world.add_object(Walker(), 7, 2)

    assert world.number_of_objects() == 2
    engine.reset()

    assert engine.world.number_of_objects() == 1


def test_zuruecksetzen_holt_entfernte_akteure_zurueck() -> None:
    engine, world = prepared_level()
    world.remove_object(walker_of(world))
    assert world.number_of_objects() == 0

    engine.reset()

    assert engine.world.number_of_objects() == 1


def test_zuruecksetzen_loescht_angezeigte_texte() -> None:
    engine, world = prepared_level()
    world.show_text("Geschafft", 2, 2)

    engine.reset()

    assert engine.world.text_at(2, 2) is None


def test_ohne_baubare_welt_greift_die_momentaufnahme() -> None:
    """Braucht der Konstruktor Werte, laesst sich die Welt nicht nachbauen.

    Dann bleibt es beim bisherigen Weg: Die Akteure gehen auf ihre
    Startfelder zurueck, die Welt selbst bleibt dieselbe.
    """

    class BraucthWerte(World):
        __slots__ = ()

        def __init__(self, breite: int) -> None:
            super().__init__(breite, 5, cell_size=CELL)

    engine = get_engine()
    engine.enable_ui()
    engine.step_duration = 0.0
    welt = BraucthWerte(20)
    walker = Walker(steps=3)
    welt.add_object(walker, 0, 0)
    engine.set_world(welt)

    welt._act_cycle()
    assert walker.x == 3

    engine.reset()

    assert engine.world is welt, "Ohne Bauanleitung bleibt die Welt dieselbe."
    assert walker.x == 0


def test_eine_weltfabrik_baut_die_welt_vollstaendig_neu() -> None:
    engine, world, _ = prepared_world()
    engine.world_factory = lambda: World(20, 5, cell_size=CELL)

    engine.reset()

    assert engine.world is not world
    assert engine.world.number_of_objects() == 0


def test_zuruecksetzen_bricht_die_laufende_anweisungsfolge_ab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anforderung C3: Der Eingriff wirkt mitten in `init`."""
    engine, _ = prepared_level(steps=50)

    drive(monkeypatch, engine, ["cycle", "step", "reset"])

    walker = walker_of(engine.world)
    assert walker.x == 0, "Nach dem Zuruecksetzen steht der Akteur wieder am Start."
    assert walker.init_done is False


# ----------------------------------------------------------------------
# Die Titelzeile nennt die angezeigte Welt
# ----------------------------------------------------------------------


def test_die_titelzeile_nennt_die_welt() -> None:
    """Sonst ist nach einem Weltwechsel nicht erkennbar, wo man ist."""
    engine, _, _ = prepared_world()

    assert engine.caption().endswith("— World")


def test_die_titelzeile_nennt_die_eigene_weltklasse() -> None:
    class Testwelt(World):
        __slots__ = ()

    engine = get_engine()
    engine.set_world(Testwelt(6, 6, cell_size=CELL))

    assert engine.caption() == "PyFoot — Testwelt"


def test_der_eigene_titel_bleibt_davor_stehen() -> None:
    engine, _, _ = prepared_world()
    engine.title = "Informatik GK"

    assert engine.caption() == "Informatik GK — World"
    assert engine.title == "Informatik GK", "Der Weltname gehoert nicht in den Titel."


def test_ohne_welt_steht_nur_der_titel() -> None:
    assert get_engine().caption() == "PyFoot"


def test_die_titelzeile_folgt_einem_weltwechsel() -> None:
    class Ersteswelt(World):
        __slots__ = ()

    class Zweiteswelt(World):
        __slots__ = ()

    engine = get_engine()
    engine.set_world(Ersteswelt(6, 6, cell_size=CELL))
    assert engine.caption().endswith("— Ersteswelt")

    engine.set_world(Zweiteswelt(6, 6, cell_size=CELL))
    assert engine.caption().endswith("— Zweiteswelt")


def test_auch_ohne_oberflaeche_steht_die_welt_im_titel() -> None:
    """Die Angabe hilft auch auf der Kommandozeile -- welche Welt laeuft da?"""
    engine = get_engine()
    engine.set_world(World(6, 6, cell_size=CELL))

    assert engine.ui_enabled is False
    assert engine.caption() == "PyFoot — World"


# ----------------------------------------------------------------------
# Das Fenster laesst sich in der Groesse aendern
# ----------------------------------------------------------------------


def test_das_fenster_ist_veraenderbar() -> None:
    """Ohne dieses Merkmal gibt es weder Ziehen noch Maximieren."""
    engine, _, _ = prepared_world()

    assert engine._screen is not None
    assert engine._screen.get_flags() & pygame.RESIZABLE


def test_eine_neue_groesse_wird_uebernommen() -> None:
    engine, _, _ = prepared_world()

    engine.resize_window((900, 700))

    assert engine._screen is not None
    assert engine._screen.get_size() == (900, 700)


def test_das_fenster_wird_nicht_unbrauchbar_klein() -> None:
    engine, _, _ = prepared_world()

    engine.resize_window((50, 30))

    assert engine._screen is not None
    assert engine._screen.get_size() == Engine.MIN_WINDOW_SIZE


def test_die_bedienleiste_haengt_am_unteren_rand() -> None:
    """Sonst rutschte sie beim Vergroessern mitten in die Flaeche."""
    engine, _, _ = prepared_world()

    engine.resize_window((900, 700))

    assert engine._panel_top() == 700 - ControlPanel.HEIGHT


def test_die_klassenanzeige_haengt_am_rechten_rand() -> None:
    from pyfoot.editor.sidebar import ClassSidebar

    engine, _, _ = prepared_world()

    engine.resize_window((900, 700))

    assert engine.sidebar_left() == 900 - ClassSidebar.WIDTH


def test_die_welt_steht_mittig_in_der_freien_flaeche() -> None:
    from pyfoot.editor.sidebar import ClassSidebar

    engine, world, _ = prepared_world()

    engine.resize_window((900, 700))

    breite, hoehe = engine.world_view()
    assert (breite, hoehe) == (900 - ClassSidebar.WIDTH, 700 - ControlPanel.HEIGHT)
    links, oben = engine.world_origin()
    assert links == (breite - world.width * CELL) // 2
    assert oben == (hoehe - world.height * CELL) // 2


def test_eine_zu_grosse_welt_beginnt_am_rand() -> None:
    """Beschnitten, aber die obere linke Ecke bleibt sichtbar."""
    engine = get_engine()
    engine.enable_ui()
    engine.set_world(World(60, 60, cell_size=CELL))

    engine.resize_window((500, 400))

    assert engine.world_origin() == (0, 0)


def test_das_zeichnen_uebersteht_ein_zu_kleines_fenster() -> None:
    """Frueher waere hier eine Teilflaeche ausserhalb des Fensters entstanden."""
    engine = get_engine()
    engine.enable_ui()
    engine.set_world(World(60, 60, cell_size=CELL))
    engine.resize_window((500, 400))

    engine._render()


def test_die_eigene_groesse_ueberlebt_einen_weltwechsel() -> None:
    """Sonst spraenge das Fenster bei jedem Wechsel auf die Weltgroesse."""
    engine, _, _ = prepared_world()
    engine.resize_window((900, 700))

    engine.set_world(World(4, 4, cell_size=CELL))

    assert engine._screen is not None
    assert engine._screen.get_size() == (900, 700)


def test_ohne_eigene_groesse_richtet_sich_das_fenster_nach_der_welt() -> None:
    engine, _, _ = prepared_world()

    assert engine._screen is not None
    assert engine._screen.get_size() == engine._window_size()
