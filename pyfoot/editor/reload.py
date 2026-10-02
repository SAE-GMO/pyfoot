"""Geaenderte eigene Dateien ins laufende Programm uebernehmen.

Anforderung H7: Nach einem Fehler soll man die Datei aendern, speichern,
`Zuruecksetzen` druecken und weiterarbeiten koennen -- ohne Neustart.

Python bindet eine Datei nur einmal ein. `Zuruecksetzen` baut die Welt zwar
ueber ihren Konstruktor neu, aber mit der Klasse, die schon im Speicher liegt.
Nachgemessen: Das Raumschiff flog danach mit dem **alten** Code.

Zwei Wege wurden ausprobiert:

- **Nur die geaenderte Datei neu laden** (`importlib.reload`) -- verworfen.
  Die Klasse stand danach doppelt im Klassenbaum, `from ships import X`
  lieferte weiter die alte Klasse, und nach dem Zuruecksetzen lief wieder
  der alte Code.
- **Alle eigenen Module verwerfen und neu einbinden** -- gewaehlt. Eigene
  Module sind die, deren Datei in einem ueber `set_class_folders`
  angemeldeten Ordner liegt. Die Bibliothek bleibt unberuehrt; eine Klasse
  wie `Asteroid` behaelt ihre Identitaet, `isinstance` greift weiter.

Ein Neustart des ganzen Programms wurde nicht gewaehlt: Das Fenster
verschwaende kurz, ein Debugger hinge am alten Prozess, und ein Syntaxfehler
fiele auf, bevor das Fenster offen ist.

Schlaegt das Einbinden fehl, wird der vorherige Stand wiederhergestellt: Die
angezeigte Welt und der Klassenbaum bleiben, wie sie waren.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TypeVar

__all__ = [
    "ModuleBackup",
    "SourceSignature",
    "changed_files",
    "changed_paths",
    "current_class",
    "discard",
    "file_signature",
    "forget_bytecode",
    "import_again",
    "own_modules",
    "source_signature",
    "unregistered_files",
    "watched_folders",
]

_T = TypeVar("_T")

#: Aenderungszeit und Groesse je Datei -- genug, um ein Speichern zu erkennen.
SourceSignature = dict[str, tuple[int, int]]


def watched_folders() -> list[Path]:
    """Die angemeldeten Ordner fuer eigene Klassen, sofern es sie gibt."""
    from .codegen import class_folders

    return [
        folder.resolve()
        for folder in class_folders()
        if folder is not None and folder.is_dir()
    ]


def file_signature(path: Path) -> tuple[int, int] | None:
    """Aenderungszeit und Groesse einer Datei; `None`, wenn es sie nicht gibt."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def source_signature() -> SourceSignature:
    """Nimmt den Stand aller Python-Dateien in den eigenen Ordnern auf."""
    signature: SourceSignature = {}
    for folder in watched_folders():
        for path in folder.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            found = file_signature(path)
            if found is not None:
                signature[str(path)] = found
    return signature


def changed_paths(before: SourceSignature, after: SourceSignature) -> list[Path]:
    """Liefert die Dateien, die sich geaendert haben, hinzukamen oder fehlen."""
    return sorted(
        Path(key) for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    )


def changed_files(before: SourceSignature, after: SourceSignature) -> list[str]:
    """Nennt die Namen der geaenderten Dateien -- fuer die Statuszeile."""
    return sorted({path.name for path in changed_paths(before, after)})


def forget_bytecode(paths: list[Path]) -> None:
    """Loescht den zwischengespeicherten Bytecode geaenderter Dateien.

    Python prueft den Zwischenstand in `__pycache__` nur anhand der
    Aenderungszeit **in ganzen Sekunden** und der Dateigroesse. Wird eine
    Datei innerhalb derselben Sekunde auf gleiche Laenge geaendert -- aus
    `SPEED = 1` wird `SPEED = 7` --, liefe sonst der alte Code. Nachgemessen
    in den Tests; beim Tippen im Unterricht selten, aber nicht ausgeschlossen.

    Der Bytecode ist ein reiner Zwischenstand und entsteht beim naechsten
    Einbinden neu.
    """
    for path in paths:
        if path.suffix != ".py":
            continue
        try:
            Path(importlib.util.cache_from_source(str(path))).unlink(missing_ok=True)
        except (OSError, NotImplementedError, ValueError):  # pragma: no cover
            pass


def unregistered_files() -> list[Path]:
    """Nennt Dateien in den eigenen Ordnern, die nicht eingebunden sind.

    Das betrifft vor allem von Hand angelegte Klassen: Solange ihre Datei
    nicht in der `__init__.py` des Pakets steht, liest das Programm sie nicht
    ein -- weder beim Start noch beim Zuruecksetzen.
    """
    from .codegen import module_name_for

    found: list[Path] = []
    for folder in watched_folders():
        for path in sorted(folder.rglob("*.py")):
            if path.name == "__init__.py" or "__pycache__" in path.parts:
                continue
            if module_name_for(path) not in sys.modules:
                found.append(path)
    return found


def _file_of(module: ModuleType) -> Path | None:
    """Liefert die Datei eines Moduls, sofern es eine hat."""
    filename = getattr(module, "__file__", None)
    if not isinstance(filename, str):
        return None
    try:
        return Path(filename).resolve()
    except OSError:  # pragma: no cover -- exotische Dateinamen
        return None


def own_modules() -> list[str]:
    """Nennt die eingebundenen Module, deren Datei in einem eigenen Ordner liegt.

    `__main__` gehoert nie dazu: Die Startdatei laeuft gerade.
    """
    folders = watched_folders()
    if not folders:
        return []
    found: list[str] = []
    for name, module in list(sys.modules.items()):
        if name == "__main__" or module is None:
            continue
        path = _file_of(module)
        if path is None:
            continue
        if any(folder == path.parent or folder in path.parents for folder in folders):
            found.append(name)
    return sorted(found)


class ModuleBackup:
    """Haelt verworfene Module fest, damit sich der alte Stand wiederherstellen laesst."""

    __slots__ = ("_modules",)

    def __init__(self, modules: dict[str, ModuleType]) -> None:
        self._modules = modules

    @property
    def names(self) -> list[str]:
        """Die gesicherten Modulnamen."""
        return sorted(self._modules)

    def restore(self) -> None:
        """Stellt den Stand vor dem Verwerfen wieder her.

        Zuerst werden die halb neu eingebundenen Module entfernt -- sonst
        stuende neben der alten Klasse eine neue im Klassenbaum.
        """
        for name in own_modules():
            if name not in self._modules:
                _remove(name)
        for name in sorted(self._modules):
            _remove(name)
            module = self._modules[name]
            sys.modules[name] = module
            _attach(name, module)


def _remove(name: str) -> None:
    """Nimmt ein Modul aus `sys.modules` und aus seinem umgebenden Paket."""
    sys.modules.pop(name, None)
    if "." in name:
        # Beim Einbinden setzt Python das Modul zusaetzlich als Merkmal des
        # umgebenden Pakets. Bliebe es dort stehen, hielte `ships` das alte
        # Modul -- und damit die alte Klasse -- weiter fest.
        package, _, part = name.rpartition(".")
        parent = sys.modules.get(package)
        if parent is not None and hasattr(parent, part):
            delattr(parent, part)


def _attach(name: str, module: ModuleType) -> None:
    """Traegt ein Modul wieder als Merkmal seines Pakets ein."""
    if "." not in name:
        return
    package, _, part = name.rpartition(".")
    parent = sys.modules.get(package)
    if parent is not None:
        setattr(parent, part, module)


def discard(names: list[str]) -> ModuleBackup:
    """Verwirft die genannten Module und liefert die Sicherung zurueck."""
    backup = {name: sys.modules[name] for name in names if name in sys.modules}
    # Die tieferen zuerst: Sonst waere das Paket schon weg, wenn sein
    # Untermodul daraus ausgetragen werden soll.
    for name in sorted(names, key=lambda n: n.count("."), reverse=True):
        _remove(name)
    importlib.invalidate_caches()
    return ModuleBackup(backup)


def import_again(names: list[str]) -> None:
    """Bindet die Module erneut ein -- soweit ihre Datei noch existiert.

    Raises:
        Exception: Was beim Einbinden schiefgeht, etwa ein `SyntaxError`.
    """
    for name in sorted(names, key=lambda n: n.count(".")):
        if name in sys.modules:
            continue  # schon als Abhaengigkeit eines anderen eingebunden
        if importlib.util.find_spec(name) is None:
            continue  # die Datei wurde geloescht oder umbenannt
        importlib.import_module(name)


def current_class(cls: type[_T]) -> type[_T]:
    """Liefert die aktuell eingebundene Version einer Klasse.

    Nach dem Neueinbinden gibt es eine neue Klasse gleichen Namens. Wer eine
    Klasse aufbewahrt -- etwa um eine Welt neu zu bauen --, holt sie sich
    hierueber jedes Mal frisch. Laesst sie sich nicht finden, etwa weil sie
    innerhalb einer Funktion entstand, bleibt es bei der alten.
    """
    module = sys.modules.get(cls.__module__)
    if module is None:
        return cls
    found: object = module
    for part in cls.__qualname__.split("."):
        found = getattr(found, part, None)
        if found is None:
            return cls
    if isinstance(found, type) and found.__name__ == cls.__name__:
        return found
    return cls
