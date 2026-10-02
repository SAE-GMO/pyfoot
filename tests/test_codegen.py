"""Tests fuer die Quelltexterzeugung (Editor-Anforderungsdokument A4, A5).

Diese Tests sind die wichtigsten des Vorhabens: Die Quelltexterzeugung
veraendert Dateien der Nutzer. Auflage F2 verlangt deshalb ausdruecklich, sie
vollstaendig zu pruefen -- und zwar ohne Fenster, was hier auch geschieht.

Geprueft werden:
    A4  prepare() erzeugen, ersetzen, nichts anderes anruehren
    A5  ein Akteur auf dem Startfeld wird als START geschrieben
    E3  der erzeugte Code sieht aus wie von Hand geschrieben
    F3  keine Datei geht verloren
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pyfoot import Actor, Image, World
from pyfoot.editor.codegen import (
    BACKUP_SUFFIX,
    Placement,
    SaveError,
    can_save,
    collect_placements,
    render_prepare,
    save_world,
)


class Stone(Actor):
    """Ein Akteur ohne Werte im Konstruktor."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))


class Crystal(Actor):
    """Ein Akteur, der seinen Wert selbst in den Quelltext schreibt."""

    __slots__ = ("value",)

    def __init__(self, value: float = 0.5) -> None:
        super().__init__(image=Image.blank(4, 4))
        self.value = value

    def construction_code(self) -> str:
        return f"Crystal({self.value})"


class Label(Actor):
    """Ein Akteur, der zwingend einen Wert braucht -- nicht erzeugbar."""

    __slots__ = ()

    def __init__(self, text: str) -> None:
        super().__init__(image=Image.blank(4, 4))


# ----------------------------------------------------------------------
# Vorlagen fuer die Quelldateien der Tests
# ----------------------------------------------------------------------

PLAIN_SOURCE = '''"""Eine Beispieldatei."""

from __future__ import annotations

from pyfoot import World


class Arena(World):
    """Eine Welt mit Aufbau."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(8, 8, 10)
        self.prepare()

    def prepare(self) -> None:
        """Von Hand geschrieben."""
        self.add_object(Stone(), 1, 1)

    def helper(self) -> int:
        """Diese Methode darf nicht verloren gehen."""
        return 42
'''

LOOP_SOURCE = '''"""Eine Beispieldatei mit Schleife im Aufbau."""

from __future__ import annotations

from pyfoot import World


class Arena(World):
    """Eine Welt mit Aufbau."""

    __slots__ = ()

    START = (0, 0)

    def __init__(self) -> None:
        super().__init__(8, 8, 10)
        self.prepare()

    def prepare(self) -> None:
        for x in range(8):
            self.add_object(Stone(), x, 0)
'''

WITHOUT_PREPARE = '''"""Eine Beispieldatei ohne Aufbau."""

from __future__ import annotations

from pyfoot import World


class Arena(World):
    """Eine Welt ohne Aufbau."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(8, 8, 10)
'''


def write_source(tmp_path: Path, text: str) -> Path:
    """Legt eine Quelldatei fuer den Test an."""
    path = tmp_path / "arena.py"
    path.write_text(text, encoding="utf-8")
    return path


class Arena(World):
    """Die Welt, die in den Tests gesichert wird."""

    __slots__ = ()

    START = (0, 0)

    def __init__(self) -> None:
        super().__init__(8, 8, 10)


def filled_world(*actors: tuple[Actor, int, int]) -> Arena:
    """Baut eine Welt mit den uebergebenen Akteuren."""
    world = Arena()
    for actor, x, y in actors:
        world.add_object(actor, x, y)
    return world


# ----------------------------------------------------------------------
# Welche Akteure lassen sich sichern
# ----------------------------------------------------------------------


def test_akteur_ohne_werte_laesst_sich_sichern() -> None:
    assert can_save(Stone()) is True


def test_akteur_mit_eigenem_quelltext_laesst_sich_sichern() -> None:
    assert can_save(Crystal(0.25)) is True


def test_akteur_mit_pflichtwert_wird_uebergangen() -> None:
    assert can_save(Label("Hallo")) is False


def test_uebergangene_akteure_werden_gemeldet() -> None:
    world = filled_world((Stone(), 1, 1), (Label("Hinweis"), 2, 2))

    placements, skipped = collect_placements(world)

    assert [p.code for p in placements] == ["Stone()"]
    assert skipped == ["Label"]


def test_eigene_werte_bleiben_erhalten() -> None:
    world = filled_world((Crystal(0.9), 3, 4))

    placements, _ = collect_placements(world)

    assert placements == [Placement("Crystal(0.9)", 3, 4)]


def test_der_startakteur_wird_ausgelassen() -> None:
    ship = Stone()
    world = filled_world((ship, 0, 0), (Stone(), 5, 5))

    placements, _ = collect_placements(world, skip=ship)

    assert [(p.x, p.y) for p in placements] == [(5, 5)]


# ----------------------------------------------------------------------
# E3 -- der erzeugte Code sieht aus wie von Hand geschrieben
# ----------------------------------------------------------------------


def test_erzeugter_code_ist_typisiert_und_kommentiert() -> None:
    text = render_prepare([Placement("Stone()", 1, 2)])

    assert "def prepare(self) -> None:" in text
    assert "Von der Oberflaeche erzeugt" in text
    assert "self.add_object(Stone(), 1, 2)" in text


def test_erzeugter_code_ist_gueltiges_python() -> None:
    text = render_prepare([Placement("Stone()", 1, 2)], indent="    ")

    ast.parse("class X:\n" + text)


def test_leerer_aufbau_bleibt_uebersetzbar() -> None:
    """Ohne Objekte traegt allein der Docstring den Rumpf."""
    ast.parse("class X:\n" + render_prepare([]))


# ----------------------------------------------------------------------
# A4 -- sichern
# ----------------------------------------------------------------------


def test_vorhandene_methode_wird_ersetzt_nicht_verdoppelt(tmp_path: Path) -> None:
    path = write_source(tmp_path, PLAIN_SOURCE)
    world = filled_world((Stone(), 2, 3), (Stone(), 4, 5))

    save_world(world, path=path)

    text = path.read_text(encoding="utf-8")
    assert text.count("def prepare") == 1
    assert "self.add_object(Stone(), 2, 3)" in text
    assert "self.add_object(Stone(), 4, 5)" in text
    assert "Von Hand geschrieben" not in text


def test_alles_ausserhalb_bleibt_unangetastet(tmp_path: Path) -> None:
    """Die zentrale Auflage aus A4."""
    path = write_source(tmp_path, PLAIN_SOURCE)

    save_world(filled_world((Stone(), 1, 1)), path=path)

    text = path.read_text(encoding="utf-8")
    assert "def helper(self) -> int:" in text
    assert "return 42" in text
    assert "Diese Methode darf nicht verloren gehen." in text
    assert '"""Eine Beispieldatei."""' in text


def test_fehlende_methode_wird_angelegt(tmp_path: Path) -> None:
    path = write_source(tmp_path, WITHOUT_PREPARE)

    report = save_world(filled_world((Stone(), 6, 6)), path=path)

    text = path.read_text(encoding="utf-8")
    assert "def prepare(self) -> None:" in text
    assert report.replaced_lines == 0
    ast.parse(text)


def test_die_datei_bleibt_uebersetzbar(tmp_path: Path) -> None:
    path = write_source(tmp_path, PLAIN_SOURCE)

    save_world(filled_world((Stone(), 1, 1), (Crystal(0.3), 2, 2)), path=path)

    ast.parse(path.read_text(encoding="utf-8"))


def test_fehlende_einfuhr_wird_ergaenzt(tmp_path: Path) -> None:
    path = write_source(tmp_path, PLAIN_SOURCE)

    report = save_world(filled_world((Crystal(0.5), 1, 1)), path=path)

    text = path.read_text(encoding="utf-8")
    assert "Crystal" in report.added_imports
    assert f"from {Crystal.__module__} import Crystal" in text
    ast.parse(text)


def test_bekannte_namen_werden_nicht_doppelt_eingefuehrt(tmp_path: Path) -> None:
    source = PLAIN_SOURCE.replace(
        "from pyfoot import World",
        f"from pyfoot import World\nfrom {Stone.__module__} import Stone",
    )
    path = write_source(tmp_path, source)

    report = save_world(filled_world((Stone(), 1, 1)), path=path)

    assert report.added_imports == ()
    assert path.read_text(encoding="utf-8").count("import Stone") == 1


def test_einfuhren_aus_einem_modul_stehen_in_einer_zeile(tmp_path: Path) -> None:
    """Sonst saehe der erzeugte Code nicht aus wie von Hand geschrieben (E3)."""
    path = write_source(tmp_path, PLAIN_SOURCE)

    save_world(filled_world((Stone(), 1, 1), (Crystal(0.5), 2, 2)), path=path)

    text = path.read_text(encoding="utf-8")
    assert f"from {Stone.__module__} import Crystal, Stone" in text


def test_der_bericht_nennt_die_zahl_der_objekte(tmp_path: Path) -> None:
    path = write_source(tmp_path, PLAIN_SOURCE)

    report = save_world(filled_world((Stone(), 1, 1), (Stone(), 2, 2)), path=path)

    assert report.objects == 2
    assert "2 Objekt(e)" in report.summary()


# ----------------------------------------------------------------------
# A5 -- Startfeld
# ----------------------------------------------------------------------


def test_der_startakteur_wird_als_start_geschrieben(tmp_path: Path) -> None:
    path = write_source(tmp_path, LOOP_SOURCE)
    ship = Stone()
    world = filled_world((ship, 0, 0), (Stone(), 4, 4))
    ship.set_location(2, 6)

    report = save_world(world, start_actor=ship, path=path)

    text = path.read_text(encoding="utf-8")
    assert "START = (2, 6)" in text
    assert report.start == (2, 6)
    # Der Startakteur darf nicht zusaetzlich gesetzt werden.
    assert "self.add_object(Stone(), 2, 6)" not in text


def test_start_wird_angelegt_wenn_es_fehlt(tmp_path: Path) -> None:
    path = write_source(tmp_path, PLAIN_SOURCE)
    ship = Stone()
    world = filled_world((ship, 3, 7))

    save_world(world, start_actor=ship, path=path)

    text = path.read_text(encoding="utf-8")
    assert "START = (3, 7)" in text
    ast.parse(text)


def test_typangabe_und_kommentar_bei_start_bleiben_erhalten(tmp_path: Path) -> None:
    source = LOOP_SOURCE.replace(
        "    START = (0, 0)", "    START: tuple[int, int] = (0, 0)  # Startfeld"
    )
    path = write_source(tmp_path, source)
    ship = Stone()
    world = filled_world((ship, 5, 1))

    save_world(world, start_actor=ship, path=path)

    text = path.read_text(encoding="utf-8")
    assert "START: tuple[int, int] = (5, 1)  # Startfeld" in text


def test_ohne_startakteur_bleibt_start_unveraendert(tmp_path: Path) -> None:
    path = write_source(tmp_path, LOOP_SOURCE)

    save_world(filled_world((Stone(), 1, 1)), path=path)

    assert "START = (0, 0)" in path.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Hinweis auf verlorene Struktur
# ----------------------------------------------------------------------


def test_eine_schleife_im_aufbau_wird_gemeldet(tmp_path: Path) -> None:
    """Aus einer Schleife wird eine lange Liste -- das darf nicht stillschweigen."""
    path = write_source(tmp_path, LOOP_SOURCE)

    report = save_world(filled_world((Stone(), 1, 1)), path=path)

    assert report.flattened is True


def test_eine_flache_methode_wird_nicht_gemeldet(tmp_path: Path) -> None:
    path = write_source(tmp_path, PLAIN_SOURCE)

    report = save_world(filled_world((Stone(), 1, 1)), path=path)

    assert report.flattened is False


# ----------------------------------------------------------------------
# F3 -- keine Datei geht verloren
# ----------------------------------------------------------------------


def test_vor_dem_schreiben_entsteht_eine_sicherungskopie(tmp_path: Path) -> None:
    path = write_source(tmp_path, PLAIN_SOURCE)

    report = save_world(filled_world((Stone(), 1, 1)), path=path)

    assert report.backup.is_file()
    assert report.backup.name == "arena.py" + BACKUP_SUFFIX
    assert report.backup.read_text(encoding="utf-8") == PLAIN_SOURCE


def test_eine_fehlerhafte_datei_wird_nicht_angeruehrt(tmp_path: Path) -> None:
    broken = "class Arena(World):\n    def prepare(self) ->\n"
    path = write_source(tmp_path, broken)

    with pytest.raises(SaveError, match="Syntaxfehler"):
        save_world(filled_world((Stone(), 1, 1)), path=path)

    assert path.read_text(encoding="utf-8") == broken


def test_eine_fremde_datei_wird_nicht_angeruehrt(tmp_path: Path) -> None:
    """Steht die Klasse nicht darin, wird nichts geschrieben."""
    other = '"""Eine Datei ohne die gesuchte Klasse."""\n'
    path = write_source(tmp_path, other)

    with pytest.raises(SaveError, match="keine Klasse namens Arena"):
        save_world(filled_world((Stone(), 1, 1)), path=path)

    assert path.read_text(encoding="utf-8") == other


def test_keine_zwischendatei_bleibt_liegen(tmp_path: Path) -> None:
    path = write_source(tmp_path, PLAIN_SOURCE)

    save_world(filled_world((Stone(), 1, 1)), path=path)

    assert not (tmp_path / "arena.py.tmp").exists()


def test_zweimal_sichern_bleibt_stabil(tmp_path: Path) -> None:
    """Der erzeugte Code muss sich selbst wieder einlesen lassen."""
    path = write_source(tmp_path, PLAIN_SOURCE)
    world = filled_world((Stone(), 1, 1), (Crystal(0.2), 2, 2))

    save_world(world, path=path)
    first = path.read_text(encoding="utf-8")
    save_world(world, path=path)
    second = path.read_text(encoding="utf-8")

    assert first == second
