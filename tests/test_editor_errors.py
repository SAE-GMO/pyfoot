"""Tests fuer Fehlerfenster und Neueinbinden (Editor-Anforderungsdokument H1 bis H8).

Geprueft werden:
    H1  Ein Fehler beendet das Programm nicht; das Fehlerfenster zeigt ihn.
    H2  Jeder Fehler wird gleich behandelt, gleich wo er entsteht.
    H3  Gezeigt wird die Zeile im eigenen Code, nicht die in der Bibliothek.
    H4  Haeufige Python-Fehler bekommen einen Satz auf Deutsch.
    H5  Dieselbe Meldung erscheint auf der Konsole.
    H6  Beendet ein Fehler das Programm, folgt eine Zusammenfassung.
    H7  Zuruecksetzen bindet geaenderte eigene Dateien neu ein.
    H8  `add_object` meldet ein Feld ausserhalb der Welt.
    F1  Ohne Oberflaeche wird der Fehler weitergereicht wie bisher.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Callable, Iterator

import pygame
import pytest

from pyfoot import Actor, Image, ScriptActor, World, get_engine
from pyfoot.editor import codegen, errors
from pyfoot.editor.errors import ErrorPanel, ErrorReport, describe, hint_for
from pyfoot.editor.menu import ContextMenu, MenuEntry
from pyfoot.editor.reload import current_class
from pyfoot.editor.sidebar import class_tree
from pyfoot.engine import Engine

CELL = 10


# ----------------------------------------------------------------------
# Hilfsmittel
# ----------------------------------------------------------------------


class Crasher(Actor):
    """Scheitert in jedem Durchlauf."""

    __slots__ = ("calls",)

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))
        self.calls = 0

    def act(self) -> None:
        self.calls += 1
        _ = 1 // 0

    def explode(self) -> None:
        """Wird ueber das Kontextmenue aufgerufen."""
        raise IndexError("list index out of range")

    def answer(self) -> int:
        return 42


class StumblingWalker(ScriptActor):
    """Faehrt ein Feld und scheitert dann."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))

    def init(self) -> None:
        self.move()
        raise NameError("name 'mvoe' is not defined")


def ui_engine() -> Engine:
    """Eine Engine mit eingeschalteter Oberflaeche und ohne Wartezeit."""
    engine = get_engine()
    engine.enable_ui()
    engine.step_duration = 0.0
    return engine


def drive(
    monkeypatch: pytest.MonkeyPatch,
    engine: Engine,
    steps: list[Callable[[Engine], None]],
) -> None:
    """Laesst die Simulation laufen und stellt dabei Bedienschritte nach.

    Sind die Schritte aufgebraucht, wird das Fenster geschlossen, sobald
    nichts mehr laeuft -- sonst bliebe der Test haengen.
    """
    remaining: Iterator[Callable[[Engine], None]] = iter(steps)

    def fake_pump(self: Engine) -> None:
        try:
            step = next(remaining)
        except StopIteration:
            if self._paused or not self._in_act_cycle:
                self._running = False
            return
        step(self)

    monkeypatch.setattr(Engine, "_pump_events", fake_pump)
    engine.run()


def key(code: int) -> pygame.event.Event:
    """Ein Tastendruck."""
    return pygame.event.Event(pygame.KEYDOWN, {"key": code, "mod": 0, "unicode": ""})


def panel_of(engine: Engine) -> ErrorPanel:
    """Liefert das Fehlerfenster und stellt sicher, dass es offen ist."""
    panel = engine.error_panel
    assert panel is not None, "Das Fehlerfenster haette offen sein muessen."
    return panel


# ----------------------------------------------------------------------
# H1, H2, F1 -- der Durchlauf
# ----------------------------------------------------------------------


def test_fehler_im_durchlauf_beendet_das_programm_nicht(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ui_engine()
    world = World(8, 4, cell_size=CELL)
    crasher = Crasher()
    world.add_object(crasher, 1, 1)
    engine.set_world(world)

    drive(monkeypatch, engine, [Engine.resume])

    report = panel_of(engine).report
    assert report.name == "ZeroDivisionError"
    assert engine.is_paused(), "Nach einem Fehler muss die Ausfuehrung anhalten."
    assert crasher.calls == 1, "Der Fehler darf sich nicht in jedem Durchlauf wiederholen."


def test_ohne_oberflaeche_wird_der_fehler_weitergereicht(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auflage F1: Ohne Oberflaeche aendert sich nichts."""
    engine = get_engine()
    engine.step_duration = 0.0
    world = World(8, 4, cell_size=CELL)
    world.add_object(Crasher(), 1, 1)
    engine.set_world(world)
    monkeypatch.setattr(Engine, "_pump_events", lambda self: None)

    with pytest.raises(ZeroDivisionError):
        engine.run()
    assert engine.error_panel is None


def test_das_raumschiff_bleibt_auf_dem_letzten_feld_stehen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ui_engine()
    world = World(8, 4, cell_size=CELL)
    walker = StumblingWalker()
    world.add_object(walker, 0, 0)
    engine.set_world(world)

    drive(monkeypatch, engine, [Engine.resume])

    assert panel_of(engine).report.name == "NameError"
    assert (walker.x, walker.y) == (1, 0)


def test_fehler_im_einzelschritt_erscheint_im_fehlerfenster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ui_engine()
    world = World(8, 4, cell_size=CELL)
    world.add_object(StumblingWalker(), 0, 0)
    engine.set_world(world)

    drive(monkeypatch, engine, [Engine.request_cycle, Engine.request_step])

    assert panel_of(engine).report.name == "NameError"


class FragileLevel(World):
    """Laesst sich genau einmal bauen -- danach scheitert der Konstruktor."""

    __slots__ = ()

    built = 0

    def __init__(self) -> None:
        super().__init__(8, 4, cell_size=CELL)
        FragileLevel.built += 1
        if FragileLevel.built > 1:
            raise KeyError("zweiter Aufbau")


def test_fehler_beim_zuruecksetzen_behaelt_die_welt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FragileLevel.built = 0
    engine = ui_engine()
    engine.set_world(FragileLevel())
    world = engine.world

    drive(monkeypatch, engine, [Engine.request_reset])

    assert panel_of(engine).report.name == "KeyError"
    assert engine.world is world
    assert not engine._reset_requested, "Sonst kaeme derselbe Fehler ohne Ende wieder."


def test_zuruecksetzen_schliesst_das_fehlerfenster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ui_engine()
    world = World(8, 4, cell_size=CELL)
    world.add_object(StumblingWalker(), 0, 0)
    engine.set_world(world)

    drive(monkeypatch, engine, [Engine.resume])
    panel = panel_of(engine)
    assert panel.choose("reset") is True

    drive(monkeypatch, engine, [])

    assert engine.error_panel is None


# ----------------------------------------------------------------------
# H2 -- Aktionen der Oberflaeche
# ----------------------------------------------------------------------


def test_fehler_beim_methodenaufruf_erscheint_im_fehlerfenster() -> None:
    engine = ui_engine()
    world = World(8, 4, cell_size=CELL)
    crasher = Crasher()
    world.add_object(crasher, 1, 1)
    engine.set_world(world)

    engine.call_member(crasher, "explode")

    assert panel_of(engine).report.name == "IndexError"
    assert "list index out of range" in engine.status


def test_erfolgreicher_methodenaufruf_steht_in_der_statuszeile() -> None:
    engine = ui_engine()
    world = World(8, 4, cell_size=CELL)
    crasher = Crasher()
    world.add_object(crasher, 1, 1)
    engine.set_world(world)

    engine.call_member(crasher, "answer")

    assert engine.error_panel is None
    assert engine.status == "answer() = 42"


def test_fehler_in_einer_menueaktion_wird_abgefangen() -> None:
    """Die Schutzschicht um die Ereignisverarbeitung faengt alles ab."""
    engine = ui_engine()
    engine.set_world(World(8, 4, cell_size=CELL))

    def scheitern() -> None:
        raise TypeError("unsupported operand type(s) for +: 'int' and 'str'")

    engine.open_menu(ContextMenu("Probe", [MenuEntry("scheitern", scheitern)], (0, 0)))
    pygame.event.clear()
    pygame.event.post(key(pygame.K_1))
    engine._pump_events()

    assert panel_of(engine).report.name == "TypeError"
    assert engine.menu is None


class Picky(Actor):
    """Lehnt unpassende Werte in seiner Eigenschaft ab."""

    __slots__ = ("_chance",)

    def __init__(self, chance: float = 0.5) -> None:
        super().__init__(image=Image.blank(4, 4))
        self._chance = chance

    @property
    def chance(self) -> float:
        return self._chance

    @chance.setter
    def chance(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError("Die Wahrscheinlichkeit muss zwischen 0.0 und 1.0 liegen.")
        self._chance = value


def test_abgelehnter_wert_erscheint_im_fehlerfenster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ui_engine()
    world = World(8, 4, cell_size=CELL)
    picky = Picky()
    world.add_object(picky, 1, 1)
    engine.set_world(world)
    monkeypatch.setattr(
        "pyfoot.editor.menu.editable_attributes", lambda target: {"chance"}
    )

    engine.set_attribute(picky, "chance", "2.0")

    assert panel_of(engine).report.name == "ValueError"
    assert picky.chance == 0.5


def test_ein_offenes_fehlerfenster_bekommt_alle_eingaben() -> None:
    engine = ui_engine()
    world = World(8, 4, cell_size=CELL)
    world.add_object(Crasher(), 1, 1)
    engine.set_world(world)
    try:
        _ = 1 // 0
    except ZeroDivisionError as error:
        engine.report_error(error)

    pygame.event.clear()
    pygame.event.post(key(pygame.K_SPACE))
    engine._pump_events()

    assert engine.is_paused(), "Die Leertaste darf hinter dem Fehlerfenster nicht starten."
    assert engine.error_panel is not None


def test_report_error_ohne_oberflaeche_reicht_weiter() -> None:
    engine = get_engine()
    with pytest.raises(ZeroDivisionError):
        try:
            _ = 1 // 0
        except ZeroDivisionError as error:
            engine.report_error(error)


# ----------------------------------------------------------------------
# Das Fehlerfenster selbst
# ----------------------------------------------------------------------


def sample_report(with_file: bool = True) -> ErrorReport:
    return ErrorReport(
        title="Fehler mitten im Lauf",
        name="SpaceshipError",
        message="Ship wollte von (8, 5) nach (9, 5) fliegen, aber dort endet die Welt.",
        hint="",
        file=Path(__file__) if with_file else None,
        line=12 if with_file else None,
        code="self.move()" if with_file else "",
    )


def open_panel(with_file: bool = True) -> tuple[ErrorPanel, list[str]]:
    calls: list[str] = []
    panel = ErrorPanel(
        sample_report(with_file),
        on_open=lambda: calls.append("open"),
        on_reset=lambda: calls.append("reset"),
    )
    panel.center_in(640, 480)
    return panel, calls


def test_fehlerfenster_esc_schliesst() -> None:
    panel, calls = open_panel()
    assert panel.handle_event(key(pygame.K_ESCAPE)) == (True, True)
    assert calls == []


def test_fehlerfenster_r_setzt_zurueck_und_schliesst() -> None:
    panel, calls = open_panel()
    assert panel.handle_event(key(pygame.K_r)) == (True, True)
    assert calls == ["reset"]


def test_fehlerfenster_e_oeffnet_die_stelle_und_bleibt_offen() -> None:
    panel, calls = open_panel()
    assert panel.handle_event(key(pygame.K_e)) == (True, False)
    assert calls == ["open"]


def test_ohne_fundstelle_oeffnet_e_nichts() -> None:
    panel, calls = open_panel(with_file=False)
    panel.handle_event(key(pygame.K_e))
    assert calls == []
    assert not panel.can_open()


def test_fehlerfenster_mit_der_maus() -> None:
    """Anforderung C1: Jeder Befehl ist auch mit der Maus erreichbar."""
    panel, calls = open_panel()
    for action in ("open", "reset"):
        rect = panel.button_rect(action)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": rect.center, "button": 1}
        )
        panel.handle_event(event)
    rect = panel.button_rect("close")
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": rect.center, "button": 1})
    assert panel.handle_event(event) == (True, True)
    assert calls == ["open", "reset"]


def test_andere_tasten_werden_verschluckt() -> None:
    panel, _ = open_panel()
    assert panel.handle_event(key(pygame.K_SPACE)) == (True, False)


def test_fehlerfenster_laesst_sich_zeichnen() -> None:
    panel, _ = open_panel()
    surface = pygame.Surface((640, 480))
    panel.render(surface)
    assert panel.rect.width <= 640


def test_schmales_fenster_bricht_den_text_um() -> None:
    panel, _ = open_panel()
    panel.center_in(300, 480)
    assert panel.rect.width <= 300


def test_zur_zeile_oeffnet_den_editor(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = ui_engine()
    engine.set_world(World(8, 4, cell_size=CELL))
    aufgerufen: list[tuple[Path, int]] = []

    def fake_open(path: Path, line: int = 1) -> str:
        aufgerufen.append((path, line))
        return "geoeffnet"

    monkeypatch.setattr("pyfoot.editor.source.open_in_editor", fake_open)
    engine.open_error_location(sample_report())

    assert aufgerufen == [(Path(__file__), 12)]
    assert engine.status == "geoeffnet"


# ----------------------------------------------------------------------
# H3, H4 -- die Beschreibung
# ----------------------------------------------------------------------


def test_eigener_satz_fuer_unboundlocalerror() -> None:
    assert hint_for(UnboundLocalError("x")) == errors.HINTS[UnboundLocalError]
    assert hint_for(UnboundLocalError("x")) != errors.HINTS[NameError]


def test_eigene_fehlerklasse_ohne_satz() -> None:
    class ShipError(RuntimeError):
        pass

    assert hint_for(ShipError("Hilfe")) == ""


def test_unterklasse_erbt_den_satz() -> None:
    class ProbabilityError(ValueError):
        pass

    assert hint_for(ProbabilityError("zu gross")) == errors.HINTS[ValueError]


@pytest.fixture
def own_code(tmp_path: Path) -> Iterator[Path]:
    """Legt eigenen Code und eine Bibliothek in getrennten Ordnern an."""
    own = tmp_path / "own_code_pkg"
    library = tmp_path / "library_pkg"
    for folder in (own, library):
        folder.mkdir()
        (folder / "__init__.py").write_text("", encoding="utf-8")
    (library / "rules.py").write_text(
        textwrap.dedent(
            """
            def check(distance: int) -> None:
                if distance > 3:
                    raise RuntimeError("zu weit")
            """
        ),
        encoding="utf-8",
    )
    (own / "pilot.py").write_text(
        textwrap.dedent(
            """
            from library_pkg.rules import check


            def fly() -> None:
                check(1)
                check(9)
            """
        ),
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        yield own
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.split(".")[0] in ("own_code_pkg", "library_pkg")]:
            del sys.modules[name]


def test_gezeigt_wird_die_zeile_im_eigenen_code(own_code: Path) -> None:
    codegen.set_class_folders(actors=own_code)
    from own_code_pkg.pilot import fly  # type: ignore[import-not-found]

    with pytest.raises(RuntimeError) as caught:
        fly()
    report = describe(caught.value)

    assert report.file == (own_code / "pilot.py").resolve()
    assert report.line == 7
    assert report.code == "check(9)"
    assert report.title == "Fehler mitten im Lauf"


def test_ohne_eigene_ordner_die_letzte_zeile_ausserhalb_von_pyfoot(own_code: Path) -> None:
    from own_code_pkg.pilot import fly

    with pytest.raises(RuntimeError) as caught:
        fly()
    report = describe(caught.value)

    assert report.file is not None
    assert report.file.name == "rules.py"


def test_syntaxfehler_nennt_datei_und_zeile(tmp_path: Path) -> None:
    broken = tmp_path / "broken_ship.py"
    broken.write_text("x = 1\nclass Broken(:\n    pass\n", encoding="utf-8")

    with pytest.raises(SyntaxError) as caught:
        compile(broken.read_text(encoding="utf-8"), str(broken), "exec")
    report = describe(caught.value)

    assert report.title == "Fehler vor dem Start"
    assert report.file == broken.resolve()
    assert report.line == 2
    assert report.hint == errors.HINTS[SyntaxError]


def test_zusammenfassung_fuer_die_konsole() -> None:
    """H5: Die Stelle steht als datei:zeile -- VS Code macht daraus einen Verweis."""
    text = errors.summary_text(sample_report())
    assert "Fehler mitten im Lauf: SpaceshipError" in text
    assert f":{12}" in text
    assert "    self.move()" in text


def test_report_error_schreibt_auf_die_konsole(capsys: pytest.CaptureFixture[str]) -> None:
    engine = ui_engine()
    engine.set_world(World(8, 4, cell_size=CELL))
    try:
        _ = 1 // 0
    except ZeroDivisionError as error:
        engine.report_error(error)

    ausgabe = capsys.readouterr().err
    assert "Traceback" in ausgabe
    assert "Fehler mitten im Lauf: ZeroDivisionError" in ausgabe
    assert "Hinweis: Es wurde durch 0 geteilt." in ausgabe


def test_fehlerausgabe_beim_programmende(capsys: pytest.CaptureFixture[str]) -> None:
    """H6: Die gewohnte Ausgabe bleibt, darunter folgt die Zusammenfassung."""
    errors.install_error_hook()
    errors.install_error_hook()  # zweimal darf nichts verdoppeln
    try:
        raise NameError("name 'mvoe' is not defined")
    except NameError as error:
        sys.excepthook(type(error), error, error.__traceback__)

    ausgabe = capsys.readouterr().err
    assert ausgabe.index("Traceback") < ausgabe.index("Fehler mitten im Lauf")
    assert ausgabe.count("Fehler mitten im Lauf") == 1


# ----------------------------------------------------------------------
# H8 -- add_object
# ----------------------------------------------------------------------


@pytest.mark.parametrize("field", [(-1, 0), (0, -1), (8, 0), (0, 4)])
def test_add_object_ausserhalb_der_welt(field: tuple[int, int]) -> None:
    world = World(8, 4, cell_size=CELL)
    with pytest.raises(ValueError, match="ausserhalb der Welt"):
        world.add_object(Crasher(), *field)
    assert world.number_of_objects() == 0


def test_add_object_am_rand_ist_erlaubt() -> None:
    world = World(8, 4, cell_size=CELL)
    world.add_object(Crasher(), 7, 3)
    assert world.number_of_objects() == 1


# ----------------------------------------------------------------------
# H7 -- geaenderte Dateien neu einbinden
# ----------------------------------------------------------------------

SHIP_SOURCE = """
from pyfoot import Image, ScriptActor


class ProbeShip(ScriptActor):
    __slots__ = ()

    SPEED = {speed}

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))

    def init(self) -> None:
        pass
"""

LEVEL_SOURCE = """
from pyfoot import World

from probe_project.probe_ship import ProbeShip


class ProbeLevel(World):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(8, 4, cell_size=10)
        {body}
"""


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Path]:
    """Ein kleines Projekt mit eigenem Ordner fuer Klassen."""
    folder = tmp_path / "probe_project"
    folder.mkdir()
    (folder / "__init__.py").write_text("", encoding="utf-8")
    write_ship(folder, 1)
    write_level(folder, "self.add_object(ProbeShip(), 0, 0)")
    sys.path.insert(0, str(tmp_path))
    codegen.set_class_folders(actors=folder, worlds=folder)
    try:
        yield folder
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.split(".")[0] == "probe_project"]:
            del sys.modules[name]


def write_ship(folder: Path, speed: int) -> None:
    (folder / "probe_ship.py").write_text(SHIP_SOURCE.format(speed=speed), encoding="utf-8")


def write_level(folder: Path, body: str) -> None:
    (folder / "probe_level.py").write_text(LEVEL_SOURCE.format(body=body), encoding="utf-8")


def started(project: Path) -> Engine:
    """Startet die Probewelt mit Oberflaeche."""
    from probe_project.probe_level import ProbeLevel  # type: ignore[import-not-found]

    engine = ui_engine()
    engine.set_world(ProbeLevel())
    return engine


def ship_in(engine: Engine) -> Actor:
    actors: list[Actor] = engine.world.objects()
    ships = [a for a in actors if type(a).__name__ == "ProbeShip"]
    assert len(ships) == 1
    return ships[0]


def tree_count(name: str) -> int:
    return [row.cls.__name__ for row in class_tree()].count(name)


def test_ohne_aenderung_bleibt_die_klasse_dieselbe(project: Path) -> None:
    engine = started(project)
    alt = type(ship_in(engine))

    engine._perform_reset()

    assert type(ship_in(engine)) is alt
    assert "Neu eingebunden" not in engine.status


def test_zuruecksetzen_uebernimmt_die_geaenderte_datei(project: Path) -> None:
    """Der Kern von H7 -- vorher flog das Schiff mit dem alten Code."""
    engine = started(project)
    alt = type(ship_in(engine))

    write_ship(project, 22)
    engine._perform_reset()

    neu = type(ship_in(engine))
    assert neu is not alt
    assert getattr(neu, "SPEED") == 22
    assert engine.status.startswith("Neu eingebunden: probe_ship.py")
    assert engine.error_panel is None


def test_nach_dem_neueinbinden_keine_doppelten_klassen(project: Path) -> None:
    engine = started(project)
    alte_klasse = type(ship_in(engine))  # haelt die alte Klasse am Leben

    write_ship(project, 5)
    engine._perform_reset()

    assert alte_klasse is not type(ship_in(engine))
    assert tree_count("ProbeShip") == 1
    assert tree_count("ProbeLevel") == 1


def test_auswahl_im_bearbeitungsmodus_zeigt_auf_die_neue_klasse(project: Path) -> None:
    engine = started(project)
    mode = engine.edit_mode
    assert mode is not None
    mode.enable()
    ship_class = [c for c in mode.classes if c.__name__ == "ProbeShip"][0]
    mode.select_class(ship_class)

    write_ship(project, 3)
    engine._perform_reset()

    assert mode.selected_class is type(ship_in(engine))


def test_syntaxfehler_beim_neueinbinden_behaelt_den_alten_stand(project: Path) -> None:
    engine = started(project)
    welt = engine.world
    paket = sys.modules["probe_project.probe_ship"]

    (project / "probe_ship.py").write_text("class Broken(:\n    pass\n", encoding="utf-8")
    engine._perform_reset()

    report = panel_of(engine).report
    assert report.name == "SyntaxError"
    assert report.file == (project / "probe_ship.py").resolve()
    assert engine.world is welt
    assert sys.modules["probe_project.probe_ship"] is paket
    assert tree_count("ProbeShip") == 1


def test_nach_der_reparatur_klappt_es_wieder(project: Path) -> None:
    engine = started(project)
    (project / "probe_ship.py").write_text("class Broken(:\n    pass\n", encoding="utf-8")
    engine._perform_reset()
    assert engine.error_panel is not None

    write_ship(project, 7)
    engine._perform_reset()

    assert engine.error_panel is None
    assert getattr(type(ship_in(engine)), "SPEED") == 7


def test_fehler_im_konstruktor_nach_dem_neueinbinden(project: Path) -> None:
    engine = started(project)
    welt = engine.world

    write_level(project, "self.add_object(ProbeShip(), 0, 0)\n        undefined_name")
    engine._perform_reset()

    report = panel_of(engine).report
    assert report.name == "NameError"
    assert report.file == (project / "probe_level.py").resolve()
    assert engine.world is welt
    assert tree_count("ProbeLevel") == 1


def test_welt_anzeigen_uebernimmt_geaenderte_dateien(project: Path) -> None:
    engine = started(project)
    level = type(engine.world)

    write_ship(project, 9)
    engine.switch_world(level)

    assert getattr(type(ship_in(engine)), "SPEED") == 9
    assert type(engine.world) is not level


def test_aktuelle_klasse_bei_klasse_in_einer_funktion() -> None:
    class Local:
        pass

    assert current_class(Local) is Local
