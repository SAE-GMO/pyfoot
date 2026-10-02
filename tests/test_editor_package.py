"""Tests fuer das Eintragen neuer Klassen in die Paketdatei (Anforderung B4f).

Befund vom 12.09.2026: Eine in der Oberflaeche angelegte Klasse stand sofort
im Klassenbaum, fehlte aber nach einem Neustart -- niemand band ihre Datei
ein. Umgekehrt startete das Programm nach dem Loeschen einer Klasse nicht
mehr, weil `__init__.py` sie weiter einband.

"Neustart" heisst in diesen Tests: alle Module des Pakets verwerfen und das
Paket frisch einbinden -- genau das, was ein neuer Programmstart tut.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from typing import Iterator

import pytest

from pyfoot import Actor, get_engine, World
from pyfoot.editor import codegen
from pyfoot.editor.reload import unregistered_files

INIT_SOURCE = '''"""Eigene Akteure."""

from __future__ import annotations

from .alpha_ship import AlphaShip
from .zulu_ship import ZuluShip

__all__ = [
    "AlphaShip",
    "ZuluShip",
]
'''

SHIP_SOURCE = """from __future__ import annotations

from pyfoot import Actor

__all__ = ["{name}"]


class {name}(Actor):
    __slots__ = ()
"""


@pytest.fixture
def package(tmp_path: Path) -> Iterator[Path]:
    """Ein Paket `crew` mit zwei Klassen, angemeldet als eigener Ordner."""
    folder = tmp_path / "crew"
    folder.mkdir()
    (folder / "__init__.py").write_text(INIT_SOURCE, encoding="utf-8")
    for module, name in (("alpha_ship", "AlphaShip"), ("zulu_ship", "ZuluShip")):
        (folder / f"{module}.py").write_text(SHIP_SOURCE.format(name=name), encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    codegen.set_class_folders(actors=folder)
    try:
        yield folder
    finally:
        sys.path.remove(str(tmp_path))
        forget()


def forget() -> None:
    for name in [n for n in sys.modules if n.split(".")[0] == "crew"]:
        del sys.modules[name]


def restart() -> object:
    """Bindet das Paket frisch ein, wie ein neuer Programmstart."""
    forget()
    importlib.invalidate_caches()
    return importlib.import_module("crew")


def init_text(package: Path) -> str:
    return (package / "__init__.py").read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Anlegen
# ----------------------------------------------------------------------


def test_neue_klasse_steht_nach_dem_neustart_im_paket(package: Path) -> None:
    codegen.create_subclass(Actor, "MikeShip", folder=package)

    crew = restart()

    assert hasattr(crew, "MikeShip")


def test_einfuhr_und_all_bleiben_sortiert(package: Path) -> None:
    codegen.create_subclass(Actor, "MikeShip", folder=package)

    text = init_text(package)
    assert (
        "from .alpha_ship import AlphaShip\n"
        "from .mike_ship import MikeShip\n"
        "from .zulu_ship import ZuluShip\n"
    ) in text
    assert '    "AlphaShip",\n    "MikeShip",\n    "ZuluShip",\n' in text
    assert (package / "__init__.py.bak").is_file(), "Auflage F3: Sicherungskopie."


def test_kurzes_all_bleibt_auf_einer_zeile(package: Path) -> None:
    (package / "__init__.py").write_text(
        'from .alpha_ship import AlphaShip\n\n__all__ = ["AlphaShip"]\n', encoding="utf-8"
    )

    codegen.create_subclass(Actor, "BravoShip", folder=package)

    assert '__all__ = ["AlphaShip", "BravoShip"]\n' in init_text(package)


def test_leere_paketdatei_bekommt_die_einfuhr(package: Path) -> None:
    (package / "__init__.py").write_text('"""Eigene Akteure."""\n', encoding="utf-8")

    codegen.create_subclass(Actor, "BravoShip", folder=package)

    text = init_text(package)
    ast.parse(text)
    assert "from .bravo_ship import BravoShip" in text
    assert hasattr(restart(), "BravoShip")


def test_unlesbare_paketdatei_verhindert_das_anlegen(package: Path) -> None:
    (package / "__init__.py").write_text("from . import (\n", encoding="utf-8")

    with pytest.raises(codegen.SaveError, match="Syntaxfehler"):
        codegen.create_subclass(Actor, "BravoShip", folder=package)

    assert not (package / "bravo_ship.py").exists(), "Keine halbe Klasse zuruecklassen."


def test_ordner_ohne_paketdatei_bleibt_wie_er_ist(tmp_path: Path) -> None:
    path = codegen.create_subclass(Actor, "LoneShip", folder=tmp_path)

    assert codegen.package_init_for(path) is None
    assert not (tmp_path / "__init__.py").exists()


def test_engine_meldet_den_eintrag(package: Path) -> None:
    engine = get_engine()
    engine.enable_ui()
    engine.set_world(World(4, 4, cell_size=10))

    engine.create_subclass(Actor, "MikeShip")

    assert "in crew/__init__.py eingetragen" in engine.status


def test_die_grundklasse_steht_vor_ihrer_unterklasse(package: Path) -> None:
    """Befund vom 18.09.2026: Sonst startet das Programm nicht mehr.

    Die neue Datei schreibt `from crew import ZuluShip`. Stuende ihre Einfuhr
    alphabetisch vor der von `zulu_ship`, gaebe es diesen Namen im halb
    eingebundenen Paket noch nicht -- `ImportError: cannot import name ...
    from partially initialized module`.
    """
    crew = restart()

    codegen.create_subclass(getattr(crew, "ZuluShip"), "BravoShip", folder=package)

    text = init_text(package)
    assert text.index("from .zulu_ship import ZuluShip") < text.index(
        "from .bravo_ship import BravoShip"
    )
    assert text.index('"ZuluShip"') < text.index('"BravoShip"')
    assert hasattr(restart(), "BravoShip"), "Das Paket muss sich einbinden lassen."


def test_eine_zweite_unterklasse_bleibt_dahinter_sortiert(package: Path) -> None:
    crew = restart()
    zulu = getattr(crew, "ZuluShip")
    codegen.create_subclass(zulu, "CharlieShip", folder=package)
    codegen.create_subclass(zulu, "BravoShip", folder=package)

    text = init_text(package)
    assert text.index("from .zulu_ship import") < text.index("from .bravo_ship import")
    assert text.index("from .bravo_ship import") < text.index("from .charlie_ship import")
    assert '    "BravoShip",\n    "CharlieShip",\n' in text
    assert hasattr(restart(), "BravoShip")


def test_grundklasse_ausserhalb_des_pakets_aendert_nichts(package: Path) -> None:
    """`Actor` kommt aus PyFoot -- da bleibt es bei der alphabetischen Ordnung."""
    codegen.create_subclass(Actor, "MikeShip", folder=package)

    text = init_text(package)
    assert text.index("from .alpha_ship import") < text.index("from .mike_ship import")
    assert text.index("from .mike_ship import") < text.index("from .zulu_ship import")


# ----------------------------------------------------------------------
# Loeschen
# ----------------------------------------------------------------------


def test_geloeschte_klasse_verschwindet_aus_dem_paket(package: Path) -> None:
    crew = restart()
    codegen.delete_class(getattr(crew, "ZuluShip"))

    text = init_text(package)
    assert "zulu_ship" not in text
    assert "ZuluShip" not in text
    crew = restart()  # vorher: ModuleNotFoundError -- das Programm startete nicht
    assert hasattr(crew, "AlphaShip")


def test_anlegen_und_wieder_loeschen_hinterlaesst_das_paket_wie_vorher(package: Path) -> None:
    vorher = init_text(package)
    codegen.create_subclass(Actor, "MikeShip", folder=package)
    crew = restart()

    codegen.delete_class(getattr(crew, "MikeShip"))

    assert init_text(package) == vorher


# ----------------------------------------------------------------------
# Von Hand angelegt
# ----------------------------------------------------------------------


def test_von_hand_angelegte_datei_wird_gemeldet(package: Path) -> None:
    restart()
    (package / "hand_ship.py").write_text(SHIP_SOURCE.format(name="HandShip"), encoding="utf-8")

    assert [p.name for p in unregistered_files()] == ["hand_ship.py"]


def test_zuruecksetzen_nennt_die_fehlende_eintragung(package: Path) -> None:
    restart()
    engine = get_engine()
    engine.enable_ui()
    engine.set_world(World(4, 4, cell_size=10))

    (package / "hand_ship.py").write_text(SHIP_SOURCE.format(name="HandShip"), encoding="utf-8")
    engine._perform_reset()

    assert "Nicht eingebunden: crew/hand_ship.py" in engine.status


def test_mit_eintrag_erscheint_sie_nach_dem_zuruecksetzen(package: Path) -> None:
    from pyfoot.editor.sidebar import class_tree

    restart()
    engine = get_engine()
    engine.enable_ui()
    engine.set_world(World(4, 4, cell_size=10))

    (package / "hand_ship.py").write_text(SHIP_SOURCE.format(name="HandShip"), encoding="utf-8")
    (package / "__init__.py").write_text(
        INIT_SOURCE.replace(
            "from .zulu_ship import ZuluShip\n",
            "from .hand_ship import HandShip\nfrom .zulu_ship import ZuluShip\n",
        ),
        encoding="utf-8",
    )
    engine._perform_reset()

    assert "HandShip" in [row.cls.__name__ for row in class_tree()]
    assert "Nicht eingebunden" not in engine.status
