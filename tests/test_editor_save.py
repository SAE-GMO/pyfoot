"""Tests fuer das Sichern aus der Oberflaeche (Editor-Anforderungen A4c, A5b, A5c).

Geprueft werden die Befunde vom 12.09.2026:
    A5b  Startobjekt ist nur, was der Konstruktor ueber `START` einsetzt --
         nicht jedes Objekt, das zufaellig auf dem Startfeld liegt.
    A5c  Ein geloeschtes Startobjekt verschwindet auch aus dem Konstruktor.
    A4c  Eine von Hand geaenderte Weltdatei wird nicht stillschweigend
         ueberschrieben.

Gearbeitet wird mit einem kleinen Projekt in einem Testordner -- die Tests
schreiben Dateien.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest

from pyfoot import Actor, get_engine
from pyfoot.editor import codegen
from pyfoot.engine import Engine

STONE_SOURCE = """
from pyfoot import Actor, Image


class Stone(Actor):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))


class Rover(Actor):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))
"""

#: Wie `Level1PowerUpRow`: `START` liegt auf einem Feld, das `prepare` belegt,
#: aber der Konstruktor setzt selbst nichts dorthin.
ROW_SOURCE = """from __future__ import annotations

from pyfoot import World

from save_project.pieces import Stone


class Row(World):
    __slots__ = ()

    START = (0, 0)

    def __init__(self) -> None:
        super().__init__(6, 3, cell_size=10)
        self.prepare()

    def prepare(self) -> None:
        for x in range(6):
            self.add_object(Stone(), x, 0)
"""

#: Wie `Level0`: Der Konstruktor setzt ein Objekt auf `START`.
START_SOURCE = """from __future__ import annotations

from pyfoot import World

from save_project.pieces import Rover


class Start(World):
    __slots__ = ()

    START = (1, 1)

    def __init__(self) -> None:
        super().__init__(6, 3, cell_size=10)
        self.prepare()
        self.add_object(Rover(), *self.START)

    def prepare(self) -> None:
        pass  # wie bei `StartWorld`: zuerst der Aufbau, dann das Startobjekt
"""


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Path]:
    """Ein kleines Projekt mit angemeldetem Ordner fuer eigene Klassen."""
    folder = tmp_path / "save_project"
    folder.mkdir()
    (folder / "__init__.py").write_text("", encoding="utf-8")
    (folder / "pieces.py").write_text(STONE_SOURCE, encoding="utf-8")
    (folder / "row.py").write_text(ROW_SOURCE, encoding="utf-8")
    (folder / "start.py").write_text(START_SOURCE, encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    codegen.set_class_folders(actors=folder, worlds=folder)
    try:
        yield folder
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.split(".")[0] == "save_project"]:
            del sys.modules[name]


def shown(engine: Engine) -> list[tuple[str, int, int]]:
    actors: list[Actor] = engine.world.objects()
    return sorted((type(a).__name__, a.x, a.y) for a in actors)


def open_world(module: str, name: str) -> Engine:
    import importlib

    cls = getattr(importlib.import_module(f"save_project.{module}"), name)
    engine = get_engine()
    engine.enable_ui()
    engine.step_duration = 0.0
    engine.set_world(cls())
    return engine


def save(engine: Engine) -> None:
    """Sichert -- auch dann, wenn der erste Druck nur warnt."""
    engine.request_save()
    if engine.status.startswith("Achtung"):
        engine.request_save()


# ----------------------------------------------------------------------
# A5b -- Startobjekt
# ----------------------------------------------------------------------


def test_start_classes_liest_den_konstruktor(project: Path) -> None:
    from save_project.row import Row  # type: ignore[import-not-found]
    from save_project.start import Start  # type: ignore[import-not-found]

    assert codegen.start_classes(Start) == ["Rover"]
    assert codegen.start_classes(Row) is None


def test_objekt_auf_dem_startfeld_ist_kein_startobjekt(project: Path) -> None:
    """Der Befund: Das PowerUp auf (0, 0) verschwand beim Sichern."""
    engine = open_world("row", "Row")
    vorher = shown(engine)
    assert engine.start_actor is None

    save(engine)
    engine._perform_reset()

    assert shown(engine) == vorher
    assert "START = (0, 0)" in (project / "row.py").read_text(encoding="utf-8")


def test_startobjekt_des_konstruktors_wird_erkannt(project: Path) -> None:
    engine = open_world("start", "Start")
    actor = engine.start_actor
    assert actor is not None
    assert type(actor).__name__ == "Rover"


# ----------------------------------------------------------------------
# A5c -- geloeschtes Startobjekt
# ----------------------------------------------------------------------


def test_geloeschtes_startobjekt_verschwindet_aus_dem_konstruktor(project: Path) -> None:
    engine = open_world("start", "Start")
    actor = engine.start_actor
    assert actor is not None
    engine.remove_actor(actor)

    save(engine)

    text = (project / "start.py").read_text(encoding="utf-8")
    assert "*self.START" not in text
    assert "import Rover" not in text, "Die Einfuhr wird nicht mehr gebraucht."
    assert "START = (1, 1)" in text
    assert "Rover vom Startfeld entfernt" in engine.status

    engine._perform_reset()
    assert shown(engine) == []


def test_verschobenes_startobjekt_schreibt_start(project: Path) -> None:
    """Die bisherige Anforderung A5 bleibt: Verschieben aendert `START`."""
    engine = open_world("start", "Start")
    actor = engine.start_actor
    assert actor is not None
    mode = engine.edit_mode
    assert mode is not None
    mode.select_at(1, 1)
    mode.move_selected(4, 2)

    save(engine)

    text = (project / "start.py").read_text(encoding="utf-8")
    assert "START = (4, 2)" in text
    assert "self.add_object(Rover(), *self.START)" in text
    engine._perform_reset()
    assert shown(engine) == [("Rover", 4, 2)]


def test_einfuhr_bleibt_wenn_die_klasse_wieder_gebraucht_wird(project: Path) -> None:
    """Startobjekt geloescht, aber ein anderes Objekt derselben Klasse gesetzt."""
    engine = open_world("start", "Start")
    actor = engine.start_actor
    assert actor is not None
    engine.remove_actor(actor)
    engine.world.add_object(type(actor)(), 3, 2)

    save(engine)

    text = (project / "start.py").read_text(encoding="utf-8")
    assert "*self.START" not in text
    assert "from save_project.pieces import Rover" in text
    assert "self.add_object(Rover(), 3, 2)" in text
    engine._perform_reset()
    assert shown(engine) == [("Rover", 3, 2)]


def test_codegen_ohne_startakteur_entfernt_die_anweisung(tmp_path: Path) -> None:
    """Dieselbe Regel unmittelbar an `save_world`."""
    from pyfoot import World

    path = tmp_path / "start_copy.py"
    path.write_text(
        START_SOURCE.replace("from save_project.pieces import Rover", "from pyfoot import Actor as Rover"),
        encoding="utf-8",
    )

    class Start(World):
        __slots__ = ()
        START = (1, 1)

        def __init__(self) -> None:
            super().__init__(6, 3, cell_size=10)

    report = codegen.save_world(Start(), None, path=path)

    assert report.removed_start == ("Rover",)
    assert "*self.START" not in path.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# A4c -- von Hand geaenderte Weltdatei
# ----------------------------------------------------------------------


def test_handaenderung_wird_nicht_stillschweigend_ueberschrieben(project: Path) -> None:
    engine = open_world("row", "Row")
    datei = project / "row.py"
    datei.write_text(
        datei.read_text(encoding="utf-8").replace(
            "self.add_object(Stone(), x, 0)",
            "self.add_object(Stone(), x, 0)\n        self.add_object(Stone(), 5, 2)",
        ),
        encoding="utf-8",
    )
    von_hand = datei.read_text(encoding="utf-8")

    engine.request_save()

    assert engine.status.startswith("Achtung: row.py wurde von Hand geändert")
    assert datei.read_text(encoding="utf-8") == von_hand


def test_zuruecksetzen_uebernimmt_die_handaenderung(project: Path) -> None:
    engine = open_world("row", "Row")
    datei = project / "row.py"
    datei.write_text(
        datei.read_text(encoding="utf-8").replace("range(6)", "range(3)"), encoding="utf-8"
    )

    engine._perform_reset()

    assert shown(engine) == [("Stone", 0, 0), ("Stone", 1, 0), ("Stone", 2, 0)]
    engine.request_save()
    assert not engine.status.startswith("Achtung: row.py"), "Nach R ist sie uebernommen."


def test_eigenes_sichern_gilt_nicht_als_handaenderung(project: Path) -> None:
    engine = open_world("row", "Row")

    save(engine)
    vorhanden: list[Actor] = engine.world.objects()
    klasse: type = type(vorhanden[0])
    engine.world.add_object(klasse(), 2, 2)
    engine.request_save()

    assert not engine.status.startswith("Achtung"), engine.status
