"""Schreibt den Weltaufbau als Quelltext in die Weltklasse.

Umgesetzt nach dem Editor-Anforderungsdokument A4 und A5. Leitprinzip
(dort 2.2): **Der Quelltext ist die einzige Wahrheit.** Die Oberflaeche legt
keinen eigenen Dateityp an, sondern erzeugt lesbaren Python-Code, den
Schueler:innen verstehen und von Hand weiterbearbeiten koennen.

Gearbeitet wird ueber den Syntaxbaum (`ast`), nicht mit Zeichenkettensuche
(Editor-Anforderungsdokument 4.3). Alles ausserhalb der erzeugten Methode
bleibt dabei unangetastet.

Die Besonderheit `START`
------------------------
Eine Weltklasse darf ein Klassenmerkmal `START` fuehren. Es benennt das Feld,
auf dem ein von aussen uebergebener Akteur eingesetzt wird -- im Kurs das
Raumschiff der Schuelerin. Ein solcher Akteur gehoert **nicht** in
`prepare()`, sonst stuende er doppelt in der Welt. Beim Sichern wird
stattdessen die `START`-Angabe fortgeschrieben (Anforderung A5).

`START` ist eine Vereinbarung ueber einen Namen, kein Wissen ueber
Raumschiffe: PyFoot bleibt themenfrei.
"""

from __future__ import annotations

import ast
import inspect
import keyword
import os
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from ..actor import Actor
    from ..world import World

__all__ = [
    "Placement",
    "SaveReport",
    "SaveError",
    "START_ATTRIBUTE",
    "IMAGE_ATTRIBUTE",
    "assign_image",
    "available_images",
    "can_delete",
    "can_save",
    "class_folder_for",
    "delete_class",
    "class_folders",
    "set_class_folders",
    "collect_placements",
    "create_subclass",
    "import_class",
    "module_name_for",
    "package_init_for",
    "public_module_for",
    "render_prepare",
    "save_world",
    "source_file",
    "source_line",
    "start_classes",
]

#: Name des Klassenmerkmals, das das Startfeld benennt (siehe Modulbeschreibung).
START_ATTRIBUTE = "START"

#: Name des Klassenmerkmals, das die Bilddatei eines Akteurs benennt.
#: Klassen, die ihr Bild im Konstruktor laden, brauchen es nicht -- dort wird
#: stattdessen der Dateiname im Aufruf fortgeschrieben (Anforderung B5).
IMAGE_ATTRIBUTE = "IMAGE"

#: Endungen, die als Bilddatei gelten.
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp")

#: Erste Zeile der erzeugten Methode. Sie sagt, woher der Code stammt und dass
#: er bearbeitet werden darf (didaktische Auflage E3).
GENERATED_DOCSTRING = (
    '"""Von der Oberflaeche erzeugt. Darf von Hand bearbeitet werden."""'
)

#: Endung der Sicherungskopie, die vor jedem Schreibvorgang entsteht.
BACKUP_SUFFIX = ".bak"

#: Ordner, in denen selbst geschriebene Klassen liegen (Anforderung B4b).
#: PyFoot kennt keine Namen dafuer -- das Projekt meldet sie an, so wie es
#: auch seine Bildordner anmeldet:
#:
#:     set_class_folders(actors=ROOT / "ships", worlds=ROOT / "levels")
#:
#: Ohne Anmeldung entsteht eine neue Klasse neben ihrer Grundklasse.
_actor_folder: Path | None = None
_world_folder: Path | None = None


def set_class_folders(
    actors: Path | None = None, worlds: Path | None = None
) -> None:
    """Legt fest, wohin die Oberflaeche neue Klassen schreibt.

    Args:
        actors: Ordner fuer neue Akteursklassen.
        worlds: Ordner fuer neue Weltklassen.
    """
    global _actor_folder, _world_folder
    if actors is not None:
        _actor_folder = Path(actors)
    if worlds is not None:
        _world_folder = Path(worlds)


def class_folders() -> tuple[Path | None, Path | None]:
    """Liefert die angemeldeten Ordner fuer Akteure und Welten."""
    return _actor_folder, _world_folder


def class_folder_for(base: type) -> Path:
    """Liefert den Ordner, in den eine Unterklasse von `base` gehoert.

    Akteure und Welten werden getrennt abgelegt -- so, wie sie auch in der
    Klassenanzeige getrennt stehen. Ist nichts angemeldet, entsteht die
    Klasse neben ihrer Grundklasse.
    """
    from ..actor import Actor as _Actor
    from ..world import World as _World

    if issubclass(base, _Actor) and _actor_folder is not None:
        return _actor_folder
    if issubclass(base, _World) and _world_folder is not None:
        return _world_folder
    return source_file(base).parent


class Placement(NamedTuple):
    """Ein Akteur auf einem Feld, wie er im Quelltext erscheint."""

    code: str
    x: int
    y: int


class SaveReport(NamedTuple):
    """Auskunft darueber, was beim Sichern geschehen ist."""

    path: Path
    backup: Path
    objects: int
    replaced_lines: int
    added_imports: tuple[str, ...]
    start: tuple[int, int] | None
    skipped: tuple[str, ...]
    flattened: bool
    #: Die Namen der Klassen, deren Startobjekt aus dem Konstruktor entfernt
    #: wurde -- weil es in der Welt nicht mehr steht (A5c).
    removed_start: tuple[str, ...] = ()

    def summary(self) -> str:
        """Fasst das Ergebnis in einem Satz zusammen."""
        parts = [f"{self.objects} Objekt(e) in {self.path.name} gesichert"]
        if self.start is not None:
            parts.append(f"Start {self.start}")
        if self.removed_start:
            parts.append(f"{', '.join(self.removed_start)} vom Startfeld entfernt")
        if self.added_imports:
            parts.append(f"{len(self.added_imports)} Einfuhr(en) ergaenzt")
        if self.skipped:
            parts.append(f"{len(self.skipped)} uebersprungen")
        return ", ".join(parts) + "."


class SaveError(RuntimeError):
    """Wird ausgeloest, wenn sich der Weltaufbau nicht sichern laesst."""


# ----------------------------------------------------------------------
# Welche Akteure lassen sich sichern
# ----------------------------------------------------------------------


def can_save(actor: Actor) -> bool:
    """Gibt an, ob sich der Akteur als Quelltext erzeugen laesst.

    Erzeugbar ist, wer selbst sagt, wie er entsteht (`construction_code`), oder
    dessen Konstruktor ohne Werte auskommt. Ein Akteur, der zwingend Werte
    braucht -- etwa ein Hinweistext --, laesst sich nicht sinnvoll erzeugen und
    wird beim Sichern uebergangen.
    """
    from ..actor import Actor as _Actor

    if type(actor).construction_code is not _Actor.construction_code:
        return True

    parameters = list(inspect.signature(type(actor).__init__).parameters.values())
    for parameter in parameters[1:]:  # self ueberspringen
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if parameter.default is inspect.Parameter.empty:
            return False
    return True


def collect_placements(
    world: World, skip: Actor | None = None
) -> tuple[list[Placement], list[str]]:
    """Sammelt die Akteure der Welt in der Reihenfolge, in der sie stehen.

    Args:
        world: Die Welt, deren Aufbau gesichert werden soll.
        skip: Ein Akteur, der nicht in `prepare()` gehoert -- der Akteur auf
            dem Startfeld (Anforderung A5).

    Returns:
        Die Platzierungen und die Namen der uebergangenen Klassen.
    """
    from ..actor import Actor as _Actor

    placements: list[Placement] = []
    skipped: list[str] = []
    actors: list[_Actor] = world.objects()
    for actor in actors:
        if actor is skip:
            continue
        if not can_save(actor):
            name = type(actor).__name__
            if name not in skipped:
                skipped.append(name)
            continue
        placements.append(Placement(actor.construction_code(), actor.x, actor.y))
    return placements, skipped


# ----------------------------------------------------------------------
# Quelltext erzeugen
# ----------------------------------------------------------------------


def render_prepare(placements: list[Placement], indent: str = "    ") -> str:
    """Erzeugt den Quelltext der Methode `prepare`.

    Args:
        placements: Die zu setzenden Akteure.
        indent: Eine Einrueckungsstufe, wie sie die Datei verwendet.
    """
    body = indent * 2
    lines = [
        f"{indent}def prepare(self) -> None:",
        f"{body}{GENERATED_DOCSTRING}",
    ]
    lines.extend(
        f"{body}self.add_object({p.code}, {p.x}, {p.y})" for p in placements
    )
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# Syntaxbaum durchsuchen
# ----------------------------------------------------------------------


def source_file(cls: type) -> Path:
    """Liefert die Quelldatei einer Klasse.

    Raises:
        SaveError: Wenn die Datei nicht zu finden ist -- etwa weil die Klasse
            in der Konsole entstanden ist.
    """
    try:
        found = inspect.getsourcefile(cls)
    except TypeError:  # pragma: no cover -- nur bei eingebauten Typen
        found = None
    if not found or not Path(found).is_file():
        raise SaveError(
            f"Die Quelldatei von {cls.__name__} laesst sich nicht finden. "
            "Sichern ist nur fuer Klassen moeglich, die in einer Datei stehen."
        )
    return Path(found)


def source_line(cls: type) -> int:
    """Liefert die Zeile, in der die Klasse beginnt; 1, wenn unbekannt."""
    try:
        _, line = inspect.getsourcelines(cls)
    except (OSError, TypeError):  # pragma: no cover -- nur ohne Quelldatei
        return 1
    return max(1, line)


def public_module_for(cls: type) -> str:
    """Liefert das kuerzeste Modul, ueber das die Klasse erreichbar ist.

    `Spaceship` steht in `space.actors.spaceship`, wird aber von `space`
    weitergereicht. Erzeugter Code soll den kurzen Weg nehmen -- so, wie er
    auch von Hand geschrieben wuerde.
    """
    import sys

    parts = cls.__module__.split(".")
    for count in range(1, len(parts)):
        candidate = ".".join(parts[:count])
        module = sys.modules.get(candidate)
        if module is not None and getattr(module, cls.__name__, None) is cls:
            return candidate
    return cls.__module__


def _class_node(tree: ast.Module, name: str) -> ast.ClassDef:
    """Sucht die Klasse im Syntaxbaum.

    Raises:
        SaveError: Wenn die Datei keine Klasse dieses Namens enthaelt.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise SaveError(f"In der Datei steht keine Klasse namens {name}.")


def _method_node(node: ast.ClassDef, name: str) -> ast.FunctionDef | None:
    """Sucht eine Methode im Klassenrumpf."""
    for statement in node.body:
        if isinstance(statement, ast.FunctionDef) and statement.name == name:
            return statement
    return None


def _start_assignment(node: ast.ClassDef) -> ast.Assign | ast.AnnAssign | None:
    """Sucht die Zuweisung an das Klassenmerkmal `START`."""
    for statement in node.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id == START_ATTRIBUTE:
                    return statement
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            if isinstance(target, ast.Name) and target.id == START_ATTRIBUTE:
                return statement
    return None


def _start_additions(node: ast.ClassDef) -> list[ast.Expr]:
    """Sucht im Konstruktor die Anweisungen, die ein Objekt auf `START` setzen.

    Erkannt wird genau die Form, in der eine Welt ihr Startobjekt einsetzt:

        self.add_object(NormalSpaceship(), *self.START)

    Nur solche Objekte sind **Startobjekte** (A5). Ein Objekt, das `prepare`
    zufaellig auf das Startfeld legt, ist keines -- sonst fiele es beim Sichern
    heraus.
    """
    init = _method_node(node, "__init__")
    if init is None:
        return []
    found: list[ast.Expr] = []
    for statement in init.body:
        if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)):
            continue
        call = statement.value
        function = call.func
        if not (isinstance(function, ast.Attribute) and function.attr == "add_object"):
            continue
        if len(call.args) != 2 or not isinstance(call.args[1], ast.Starred):
            continue
        spread = call.args[1].value
        if isinstance(spread, ast.Attribute) and spread.attr == START_ATTRIBUTE:
            found.append(statement)
    return found


def _created_class(statement: ast.Expr) -> str:
    """Liefert den Klassennamen aus `self.add_object(X(), ...)`; leer, wenn unklar."""
    call = statement.value
    if isinstance(call, ast.Call) and call.args:
        created = call.args[0]
        if isinstance(created, ast.Call) and isinstance(created.func, ast.Name):
            return created.func.id
    return ""


def start_classes(cls: type) -> list[str] | None:
    """Nennt die Klassen, die der Konstruktor auf das Startfeld setzt.

    Returns:
        Die Klassennamen -- ein leerer Name, wo er sich nicht ablesen laesst.
        `None`, wenn der Konstruktor gar nichts auf `START` setzt oder die
        Datei sich nicht lesen laesst.
    """
    try:
        path = source_file(cls)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        node = _class_node(tree, cls.__name__)
    except (SaveError, OSError, SyntaxError, ValueError):
        return None
    additions = _start_additions(node)
    if not additions:
        return None
    return [_created_class(statement) for statement in additions]


def _unused_import_edits(
    tree: ast.Module, names: set[str], removed: list[ast.Expr]
) -> list[_Edit]:
    """Entfernt Einfuhren, die nach dem Loeschen nicht mehr gebraucht werden.

    Beruecksichtigt wird nur die einfache Form `from x import Name` mit genau
    einem Namen -- so, wie die Kursdateien sie schreiben. Alles andere bleibt
    stehen; eine ueberzaehlige Einfuhr schadet nicht.
    """
    skip = {id(node) for statement in removed for node in ast.walk(statement)}
    still_used = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and id(node) not in skip
    }
    edits: list[_Edit] = []
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom) or len(statement.names) != 1:
            continue
        alias = statement.names[0]
        name = alias.asname or alias.name
        if name in names and name not in still_used:
            edits.append(
                _Edit(statement.lineno - 1, statement.end_lineno or statement.lineno, "")
            )
    return edits


def _known_names(tree: ast.Module) -> set[str]:
    """Sammelt alle Namen, die die Datei bereits kennt.

    Beruecksichtigt werden Einfuhren und alles, was die Datei selbst
    definiert -- danach richtet sich, ob eine Einfuhr zu ergaenzen ist.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
    return names


def _last_import_line(tree: ast.Module) -> int:
    """Liefert die letzte Zeile der Einfuhren; 0, wenn es keine gibt."""
    last = 0
    for statement in tree.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            last = max(last, statement.end_lineno or statement.lineno)
    return last


def _is_flat(method: ast.FunctionDef) -> bool:
    """Prueft, ob die Methode nur aus `add_object`-Aufrufen besteht.

    Enthaelt sie mehr -- Schleifen, Bedingungen, Berechnungen --, geht diese
    Struktur beim Sichern verloren. Der Bericht weist darauf hin, denn der
    erzeugte Aufbau ist dann laenger und weniger lesbar als der bisherige.
    """
    for index, statement in enumerate(method.body):
        if (
            index == 0
            and isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            continue
        if not isinstance(statement, ast.Expr):
            return False
        call = statement.value
        if not isinstance(call, ast.Call):
            return False
        function = call.func
        if not isinstance(function, ast.Attribute) or function.attr != "add_object":
            return False
    return True


def _indent_of(node: ast.ClassDef) -> str:
    """Ermittelt die Einrueckungsstufe aus dem Klassenrumpf."""
    if node.body:
        width = node.body[0].col_offset - node.col_offset
        if width > 0:
            return " " * width
    return "    "


# ----------------------------------------------------------------------
# Datei aendern
# ----------------------------------------------------------------------


class _Edit(NamedTuple):
    """Eine Aenderung an einem Zeilenbereich; Zeilen sind ab 0 gezaehlt."""

    start: int
    end: int
    text: str


def _apply_edits(lines: list[str], edits: list[_Edit]) -> list[str]:
    """Wendet Aenderungen von unten nach oben an, damit Zeilennummern gelten."""
    result = list(lines)
    for edit in sorted(edits, key=lambda e: e.start, reverse=True):
        result[edit.start : edit.end] = [edit.text] if edit.text else []
    return result


def _start_edit(
    lines: list[str],
    assignment: ast.Assign | ast.AnnAssign,
    value: ast.expr,
    start: tuple[int, int],
    indent: str,
) -> _Edit:
    """Baut die Aenderung, die `START` auf das neue Feld setzt.

    Steht der Wert auf einer Zeile, wird nur er ersetzt -- Typangabe und ein
    nachgestellter Kommentar bleiben damit erhalten. Andernfalls wird die
    gesamte Zuweisung neu geschrieben.
    """
    new_value = f"({start[0]}, {start[1]})"
    single_line = value.end_lineno == value.lineno and value.end_col_offset is not None

    if single_line:
        line = value.lineno - 1
        original = lines[line]
        replacement = (
            original[: value.col_offset] + new_value + original[value.end_col_offset :]
        )
        return _Edit(line, line + 1, replacement)

    first = assignment.lineno - 1
    last = assignment.end_lineno or assignment.lineno
    return _Edit(first, last, f"{indent}{START_ATTRIBUTE} = {new_value}\n")


def _write_atomically(path: Path, text: str) -> Path:
    """Schreibt die Datei, ohne sie bei einem Fehler zu beschaedigen.

    Zuerst entsteht eine Sicherungskopie, dann wird ueber eine Zwischendatei
    im selben Ordner ersetzt. Schlaegt das fehl, bleibt die urspruengliche
    Datei unveraendert (Auflage F3).

    Returns:
        Der Pfad der Sicherungskopie.
    """
    backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    try:
        os.replace(temporary, path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise SaveError(
            f"{path.name} laesst sich nicht schreiben: {error}. "
            "Die Datei ist unveraendert; die Sicherungskopie liegt daneben."
        ) from error
    return backup


def snake_case(name: str) -> str:
    """Wandelt einen Klassennamen in einen Dateinamen um.

    'NormalSpaceship' wird zu 'normal_spaceship'.
    """
    parts: list[str] = []
    for index, letter in enumerate(name):
        if letter.isupper() and index > 0 and not name[index - 1].isupper():
            parts.append("_")
        parts.append(letter.lower())
    return "".join(parts)


#: Was im Rumpf einer erzeugten Methode steht. Der Text wird gelesen, also
#: soll er sagen, wofuer die Methode da ist.
STUB_DOCSTRINGS: dict[str, str] = {
    "init": "Hier stehen die Anweisungen.",
    "prepare": "Hier wird die Welt aufgebaut.",
}


def _stub_for(base: type, method_name: str) -> str:
    """Erzeugt den Rumpf einer noch offenen Methode.

    Die erzeugte Datei muss ohne Nacharbeit lauffaehig sein und die
    Typpruefung bestehen (Anforderung B4). Liefert die Methode einen Wert,
    steht deshalb ein `raise` im Rumpf -- sonst genuegt die Beschreibung.
    """
    original = getattr(base, method_name, None)
    try:
        signature = inspect.signature(original) if original is not None else None
    except (TypeError, ValueError):  # pragma: no cover -- exotische Methoden
        signature = None

    arguments = "self"
    returns = "None"
    if signature is not None:
        # Die Signatur der unveraenderten Methode fuehrt `self` bereits mit.
        parameters = list(signature.parameters.values())
        rest = [str(p) for p in parameters[1:]] if parameters else []
        arguments = ", ".join(["self", *rest]) if rest else "self"
        if signature.return_annotation is not inspect.Signature.empty:
            annotation = signature.return_annotation
            returns = (
                annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "None")
            )

    lines = [
        f"    def {method_name}({arguments}) -> {returns}:",
        f'        """{STUB_DOCSTRINGS.get(method_name, "Hier stehen die Anweisungen.")}"""',
    ]
    if returns not in ("None", "NoReturn"):
        lines.append(
            '        raise NotImplementedError("Diese Methode muss noch geschrieben werden.")'
        )
    return "\n".join(lines)


#: Methoden, die eine neue Klasse immer anbieten soll -- sofern die
#: Grundklasse sie ueberhaupt kennt. In sie wird geschrieben: `init` traegt
#: die Anweisungen eines Akteurs, `prepare` den Aufbau einer Welt.
TEMPLATE_METHODS: tuple[str, ...] = ("init", "prepare")


def render_subclass(base: type, name: str) -> str:
    """Erzeugt den Quelltext einer neuen Unterklasse.

    Offene Methoden der Grundklasse werden als Rumpf angelegt, damit sich die
    Klasse sofort verwenden laesst.

    Die Vorlage traegt `__slots__`, weil die Angabe nur wirkt, wenn sie
    *jede* Klasse der Vererbungskette hat: Eine einzige Unterklasse ohne sie
    holt das `__dict__` fuer alle Instanzen zurueck. Eine im Editor erzeugte
    Klasse wuerde den Schutz der gesamten Hierarchie sonst aufheben.

    Geprueft und verworfen wurde `@dataclass(slots=True)`: Der erzeugte
    `__init__` verdraengt den der Grundklasse, der Akteur bliebe unfertig;
    ausserdem baut der Umsetzer eine *neue* Klasse, sodass die alte im
    Klassenbaum stehen bleibt und jede Klasse doppelt erschiene.
    """
    offen = set(getattr(base, "__abstractmethods__", frozenset()))
    # Auch wenn die Grundklasse sie schon ausfuellt: In diese Methoden wird
    # geschrieben, also gehoeren sie in die Vorlage. Sonst entstuende beim
    # Ableiten von `NormalSpaceship` eine Klasse ohne `init` -- der Methode,
    # um die es im ganzen Kurs geht.
    offen.update(name for name in TEMPLATE_METHODS if hasattr(base, name))
    body = "\n\n".join(_stub_for(base, method) for method in sorted(offen))

    return (
        f'"""{name} -- neue Klasse, erzeugt von der Oberflaeche.\n'
        f"\n"
        f"Diese Datei gehoert dir. Hier kann eine Beschreibung stehen.\n"
        f'"""\n'
        f"\n"
        f"from __future__ import annotations\n"
        f"\n"
        f"from {public_module_for(base)} import {base.__name__}\n"
        f"\n"
        f'__all__ = ["{name}"]\n'
        f"\n"
        f"\n"
        f"class {name}({base.__name__}):\n"
        f'    """Beschreibung."""\n'
        f"\n"
        f"    # Eigene Attribute hier eintragen: `__slots__ = (\"counter\",)`, den\n"
        f"    # Typ bei Bedarf darunter als `counter: int`.\n"
        f"    __slots__ = ()\n"
        + (f"\n{body}\n" if body else "")
    )


def module_name_for(path: Path) -> str:
    """Bestimmt den Modulnamen einer Datei aus ihrer Lage im Paket.

    `Space/space/actors/probe_ship.py` heisst `space.actors.probe_ship` --
    also genauso, wie die Datei nach einem Neustart eingebunden wuerde. Nur
    so greifen auch die Einfuhren innerhalb des Pakets.
    """
    parts = [path.stem]
    folder = path.parent
    while (folder / "__init__.py").is_file():
        parts.insert(0, folder.name)
        folder = folder.parent
    return ".".join(parts)


def import_class(path: Path, name: str) -> type:
    """Bindet eine gerade angelegte Datei ein und liefert ihre Klasse.

    Ohne diesen Schritt kennt das laufende Programm die neue Klasse nicht --
    sie erschiene erst nach einem Neustart in der Klassenanzeige.

    Raises:
        SaveError: Wenn sich die Datei nicht einbinden laesst oder die Klasse
            darin fehlt.
    """
    import importlib.util
    import sys

    module_name = module_name_for(path)
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        raise SaveError(f"{path.name} laesst sich nicht einbinden.")

    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    try:
        specification.loader.exec_module(module)
    except Exception as error:
        # Ein halb eingebundenes Modul darf nicht zurueckbleiben.
        sys.modules.pop(module_name, None)
        raise SaveError(
            f"{path.name} wurde angelegt, laesst sich aber nicht einbinden: {error}"
        ) from error

    found = getattr(module, name, None)
    if not isinstance(found, type):
        sys.modules.pop(module_name, None)
        raise SaveError(f"In {path.name} steht keine Klasse namens {name}.")
    return found


# ----------------------------------------------------------------------
# Paketdatei fortschreiben (Anforderung B4f)
# ----------------------------------------------------------------------


#: Groesste Zeilenlaenge, bis zu der `__all__` auf einer Zeile bleibt.
_ALL_LINE_LIMIT = 88


def package_init_for(path: Path) -> Path | None:
    """Liefert die `__init__.py` des Pakets, in dem die Datei liegt.

    Ohne Paketdatei gibt es nichts einzutragen -- dann `None`.
    """
    init = path.parent / "__init__.py"
    return init if init.is_file() and path.name != "__init__.py" else None


def _all_assignment(tree: ast.Module) -> ast.Assign | None:
    """Sucht `__all__ = [...]` mit lauter Zeichenketten auf oberster Ebene."""
    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not (isinstance(target, ast.Name) and target.id == "__all__"):
            continue
        if isinstance(statement.value, (ast.List, ast.Tuple)) and all(
            isinstance(element, ast.Constant) and isinstance(element.value, str)
            for element in statement.value.elts
        ):
            return statement
    return None


def _all_names(assignment: ast.Assign) -> list[str]:
    """Liest die Namen aus einer `__all__`-Zuweisung."""
    value = assignment.value
    assert isinstance(value, (ast.List, ast.Tuple))
    return [str(element.value) for element in value.elts if isinstance(element, ast.Constant)]


def _render_all(names: list[str], multiline: bool) -> str:
    """Schreibt `__all__` in der Form, die die Datei schon hat.

    Eine Liste mit einem Namen je Zeile bleibt so. Eine einzeilige bleibt
    einzeilig, solange sie in die Zeile passt.
    """
    single = "__all__ = [" + ", ".join(f'"{n}"' for n in names) + "]\n"
    if not multiline and len(single) <= _ALL_LINE_LIMIT:
        return single
    return "__all__ = [\n" + "".join(f'    "{n}",\n' for n in names) + "]\n"


def _base_in_package(base: type, target: Path) -> tuple[str, str] | None:
    """Liefert Modul und Name der Grundklasse, wenn sie im selben Paket liegt.

    Nur dann ist die Reihenfolge in der Paketdatei ueberhaupt eine Frage
    (B4g): Eine Grundklasse aus `space/` ist laengst eingebunden, wenn
    `ships/__init__.py` an die Reihe kommt.
    """
    try:
        source = source_file(base)
    except SaveError:
        return None
    if source.parent.resolve() != target.parent.resolve():
        return None
    return source.stem, base.__name__


def _all_with(names: list[str], name: str, after: str | None) -> list[str]:
    """Traegt einen Namen in `__all__` ein -- hinter seiner Grundklasse (B4g).

    Vor der Grundklasse wird nicht einsortiert: `__all__` soll dieselbe
    Reihenfolge zeigen wie die Einfuhren darueber. Dahinter bleibt es
    alphabetisch, solange die Liste es war; sonst wird angehaengt.
    """
    start = names.index(after) + 1 if after in names else 0
    if names[start:] != sorted(names[start:]):
        return [*names, name]
    stelle = start
    while stelle < len(names) and names[stelle] < name:
        stelle += 1
    return [*names[:stelle], name, *names[stelle:]]


def _relative_imports(tree: ast.Module) -> list[ast.ImportFrom]:
    """Die Einfuhren der Form `from .modul import Name` auf oberster Ebene."""
    return [
        statement
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom) and statement.level == 1
    ]


def _package_text(
    init: Path,
    module: str,
    name: str,
    add: bool,
    base: tuple[str, str] | None = None,
) -> str | None:
    """Berechnet den neuen Inhalt der Paketdatei.

    Args:
        init: Die Paketdatei.
        module: Modulname der Klasse, ohne Punkt.
        name: Name der Klasse.
        add: Eintragen oder austragen.
        base: Modul und Name der Grundklasse, sofern sie **im selben Paket**
            liegt. Der Eintrag kommt dann dahinter (B4g).

    Returns:
        Den neuen Text -- oder `None`, wenn nichts zu aendern ist.

    Raises:
        SaveError: Wenn sich die Paketdatei nicht lesen laesst.
    """
    original = init.read_text(encoding="utf-8")
    try:
        tree = ast.parse(original, filename=str(init))
    except SyntaxError as error:
        raise SaveError(
            f"{init.parent.name}/{init.name} enthaelt einen Syntaxfehler und wird "
            f"nicht angeruehrt: {error}"
        ) from error

    lines = original.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    edits: list[_Edit] = []
    imports = _relative_imports(tree)
    vorhanden = [s for s in imports if s.module == module and any(a.name == name for a in s.names)]

    # --- Einfuhr --------------------------------------------------------
    if add and not vorhanden:
        zeile = f"from .{module} import {name}\n"
        # Die Grundklasse muss vorher eingebunden sein: Die neue Datei
        # schreibt `from ships import NormalSpaceship`, und solange `ships`
        # erst halb eingebunden ist, gibt es diesen Namen dort noch nicht
        # (B4g). Alphabetisch stuende `alpha_ship` sonst vor
        # `normal_spaceship` -- und das Programm startete nicht mehr.
        ab = 0
        if base is not None:
            for stelle, statement in enumerate(imports):
                if statement.module == base[0]:
                    ab = stelle + 1
                    break
        danach = [s for s in imports[ab:] if (s.module or "") > module]
        if danach:
            position = danach[0].lineno - 1
        elif imports:
            position = imports[-1].end_lineno or imports[-1].lineno
        else:
            position = _last_import_line(tree)
            if position == 0 and tree.body and isinstance(tree.body[0], ast.Expr):
                position = tree.body[0].end_lineno or 0
            zeile = "\n" + zeile
        edits.append(_Edit(position, position, zeile))
    if not add:
        for statement in vorhanden:
            first = statement.lineno - 1
            last = statement.end_lineno or statement.lineno
            uebrig = [a for a in statement.names if a.name != name]
            if uebrig:
                rest = ", ".join(
                    a.name if a.asname is None else f"{a.name} as {a.asname}" for a in uebrig
                )
                edits.append(_Edit(first, last, f"from .{module} import {rest}\n"))
            else:
                edits.append(_Edit(first, last, ""))

    # --- __all__ --------------------------------------------------------
    assignment = _all_assignment(tree)
    if assignment is not None:
        namen = _all_names(assignment)
        if add and name not in namen:
            neu = _all_with(namen, name, base[1] if base is not None else None)
        elif not add and name in namen:
            neu = [n for n in namen if n != name]
        else:
            neu = namen
        if neu != namen:
            first = assignment.lineno - 1
            last = assignment.end_lineno or assignment.lineno
            edits.append(_Edit(first, last, _render_all(neu, multiline=last > first + 1)))

    if not edits:
        return None
    changed = "".join(_apply_edits(lines, edits))
    try:
        ast.parse(changed, filename=str(init))
    except SyntaxError as error:  # pragma: no cover -- Schutz gegen eigene Fehler
        raise SaveError(f"Die Paketdatei waere fehlerhaft ({error}).") from error
    return changed


def create_subclass(base: type, name: str, folder: Path | None = None) -> Path:
    """Legt eine neue Unterklasse als eigene Datei an (Anforderung B4).

    Args:
        base: Die Klasse, von der geerbt wird.
        name: Name der neuen Klasse.
        folder: Zielordner; ohne Angabe der angemeldete Ordner fuer eigene
            Klassen (siehe `set_class_folders`).

    Returns:
        Der Pfad der angelegten Datei.

    Raises:
        SaveError: Bei ungueltigem Namen oder wenn die Datei schon besteht.
    """
    plain = name.strip()
    if not plain.isidentifier() or keyword.iskeyword(plain):
        raise SaveError(
            f"'{name}' ist kein gueltiger Klassenname. Erlaubt sind Buchstaben, "
            "Ziffern und Unterstriche; los geht es mit einem Buchstaben."
        )
    if not plain[0].isupper():
        raise SaveError(
            f"Klassennamen beginnen mit einem Grossbuchstaben -- also "
            f"'{plain[0].upper()}{plain[1:]}' statt '{plain}'."
        )

    target_folder = folder if folder is not None else class_folder_for(base)
    target_folder.mkdir(parents=True, exist_ok=True)
    target = target_folder / f"{snake_case(plain)}.py"
    if target.exists():
        raise SaveError(f"Es gibt bereits eine Datei {target.name}.")

    text = render_subclass(base, plain)
    try:
        ast.parse(text, filename=str(target))
    except SyntaxError as error:  # pragma: no cover -- Schutz gegen eigene Fehler
        raise SaveError(f"Die Vorlage waere fehlerhaft: {error}") from error

    # Liegt die Datei in einem Paket, wird sie dort eingetragen (B4f). Sonst
    # bindet nach einem Neustart niemand sie ein, und die Klasse fehlt im
    # Klassenbaum. Zuerst berechnen, dann schreiben: Eine unlesbare
    # Paketdatei verhindert das Anlegen, statt eine halbe Klasse zu hinterlassen.
    init = package_init_for(target)
    package_text = (
        _package_text(init, target.stem, plain, add=True, base=_base_in_package(base, target))
        if init is not None
        else None
    )

    target.write_text(text, encoding="utf-8")
    if init is not None and package_text is not None:
        _write_atomically(init, package_text)
    return target


# ----------------------------------------------------------------------
# Klasse loeschen (Anforderung B8)
# ----------------------------------------------------------------------


def _classes_in(path: Path) -> list[str]:
    """Liefert die Namen aller Klassen, die in der Datei stehen."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return []
    return [n.name for n in tree.body if isinstance(n, ast.ClassDef)]


def can_delete(cls: type) -> tuple[bool, str]:
    """Prueft, ob sich eine Klasse loeschen laesst.

    Geloescht wird nur, was ausdruecklich zum eigenen Bereich gehoert -- also
    in einem der ueber `set_class_folders` angemeldeten Ordner liegt. Das ist
    eine Erlaubnisliste: Was nicht dort steht, ist geschuetzt, ohne dass
    jemand eine Verbotsliste pflegen muesste.

    Returns:
        Ein Paar aus `erlaubt` und der Begruendung, wenn nicht.
    """
    try:
        path = source_file(cls)
    except SaveError as error:
        return False, str(error)

    erlaubte = [folder for folder in class_folders() if folder is not None]
    if not erlaubte:
        return False, "Es ist kein Ordner fuer eigene Klassen angemeldet."
    if path.parent.resolve() not in [f.resolve() for f in erlaubte]:
        return False, (
            f"{cls.__name__} gehoert zum vorgegebenen Teil des Projekts "
            "und laesst sich nicht loeschen."
        )

    weitere = [name for name in _classes_in(path) if name != cls.__name__]
    if weitere:
        # In Java gilt eine Klasse je Datei, in Python nicht. Eine einzelne
        # Klasse herauszuschneiden hinterliesse einen unklaren Rest.
        return False, (
            f"In {path.name} stehen noch {', '.join(weitere)}. "
            "Geloescht wird nur, was allein in seiner Datei steht."
        )
    return True, ""


def delete_class(cls: type) -> Path:
    """Entfernt eine Klasse samt ihrer Datei (Anforderung B8).

    Die Datei wird **nicht** geloescht, sondern zur Sicherungskopie
    umbenannt (Auflage F3). Anschliessend wird das Modul entladen, damit die
    Klasse aus der Klassenanzeige verschwindet.

    Returns:
        Der Pfad der Sicherungskopie.

    Raises:
        SaveError: Wenn die Klasse geschuetzt ist oder sich die Datei nicht
            umbenennen laesst.
    """
    import gc
    import sys

    erlaubt, grund = can_delete(cls)
    if not erlaubt:
        raise SaveError(grund)

    path = source_file(cls)
    # Auch aus der Paketdatei austragen (B4f). Bliebe die Einfuhr stehen,
    # startete das Programm nach dem Loeschen nicht mehr -- nachgemessen.
    init = package_init_for(path)
    package_text = (
        _package_text(init, path.stem, cls.__name__, add=False) if init is not None else None
    )

    backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if backup.exists():
        backup.unlink()
    try:
        path.rename(backup)
    except OSError as error:
        raise SaveError(f"{path.name} laesst sich nicht umbenennen: {error}") from error
    if init is not None and package_text is not None:
        _write_atomically(init, package_text)

    # Ohne das Entladen bliebe die Klasse im laufenden Programm bestehen und
    # stuende weiter in der Anzeige.
    name = module_name_for(path)
    sys.modules.pop(name, None)
    if "." in name:
        # Beim Einbinden setzt Python das Modul zusaetzlich als Merkmal des
        # umgebenden Pakets. Ohne diesen Schritt haelt `ships` das Modul --
        # und damit die Klasse -- weiter fest.
        paket, _, teil = name.rpartition(".")
        umgebung = sys.modules.get(paket)
        if umgebung is not None and hasattr(umgebung, teil):
            delattr(umgebung, teil)
    gc.collect()
    return backup


# ----------------------------------------------------------------------
# Bild zuweisen (Anforderung B5)
# ----------------------------------------------------------------------


def available_images() -> list[str]:
    """Sammelt die Bilddateien aus den bekannten Bildordnern."""
    from ..image import image_folders

    names: list[str] = []
    for folder in image_folders():
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir()):
            if entry.suffix.lower() in IMAGE_SUFFIXES and entry.name not in names:
                names.append(entry.name)
    return names


def _image_literal(node: ast.ClassDef) -> ast.Constant | None:
    """Sucht den Dateinamen in einem Aufruf `Image.from_file("...")`."""
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        function = child.func
        if not isinstance(function, ast.Attribute) or function.attr != "from_file":
            continue
        if not child.args:
            continue
        first = child.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first
    return None


def _named_assignment(
    node: ast.ClassDef, name: str
) -> ast.Assign | ast.AnnAssign | None:
    """Sucht eine Zuweisung an ein Klassenmerkmal."""
    for statement in node.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return statement
        elif isinstance(statement, ast.AnnAssign):
            target_name = statement.target
            if isinstance(target_name, ast.Name) and target_name.id == name:
                return statement
    return None


def assign_image(cls: type, filename: str, path: Path | None = None) -> Path:
    """Weist einer Klasse ein Bild zu -- als Quelltext, nicht als Nebendatei.

    Laedt die Klasse ihr Bild bereits im Konstruktor, wird dort der Dateiname
    fortgeschrieben. Andernfalls entsteht das Klassenmerkmal `IMAGE`, das
    `Actor` beim Erzeugen auswertet.

    Args:
        cls: Die Klasse, die das Bild bekommt.
        filename: Name der Bilddatei, etwa 'asteroid.png'.
        path: Abweichende Zieldatei; ohne Angabe die Quelldatei der Klasse.

    Returns:
        Der Pfad der Sicherungskopie.

    Raises:
        SaveError: Wenn sich die Datei nicht lesen oder schreiben laesst.
    """
    target = path if path is not None else source_file(cls)
    text = target.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    try:
        tree = ast.parse(text, filename=str(target))
    except SyntaxError as error:
        raise SaveError(
            f"{target.name} enthaelt einen Syntaxfehler und wird nicht angeruehrt: {error}"
        ) from error

    class_node = _class_node(tree, cls.__name__)
    indent = _indent_of(class_node)
    literal = _image_literal(class_node)

    if literal is not None:
        line = literal.lineno - 1
        original = lines[line]
        if literal.end_lineno != literal.lineno or literal.end_col_offset is None:
            raise SaveError(  # pragma: no cover -- mehrzeilige Zeichenkette
                "Der Dateiname steht ueber mehrere Zeilen und wird nicht veraendert."
            )
        replacement = (
            original[: literal.col_offset]
            + f'"{filename}"'
            + original[literal.end_col_offset :]
        )
        edits = [_Edit(line, line + 1, replacement)]
    else:
        assignment = _named_assignment(class_node, IMAGE_ATTRIBUTE)
        if assignment is not None and assignment.value is not None:
            value = assignment.value
            line = value.lineno - 1
            original = lines[line]
            replacement = (
                original[: value.col_offset]
                + f'"{filename}"'
                + original[value.end_col_offset :]
            )
            edits = [_Edit(line, line + 1, replacement)]
        else:
            anchor = class_node.body[0].end_lineno or class_node.lineno
            edits = [
                _Edit(
                    anchor,
                    anchor,
                    f"\n{indent}#: Von der Oberflaeche erzeugt: das Bild dieser Klasse.\n"
                    f'{indent}{IMAGE_ATTRIBUTE} = "{filename}"\n',
                )
            ]

    changed = "".join(_apply_edits(lines, edits))
    try:
        ast.parse(changed, filename=str(target))
    except SyntaxError as error:  # pragma: no cover -- Schutz gegen eigene Fehler
        raise SaveError(
            f"Der erzeugte Quelltext waere fehlerhaft ({error}). "
            f"{target.name} bleibt unveraendert."
        ) from error

    return _write_atomically(target, changed)


def save_world(
    world: World,
    start_actor: Actor | None = None,
    path: Path | None = None,
    dry_run: bool = False,
) -> SaveReport:
    """Schreibt den aktuellen Weltaufbau als `prepare()` in die Quelldatei.

    Eine vorhandene `prepare()` wird ersetzt, alles andere bleibt stehen.
    Fehlende Einfuhren werden ergaenzt. Steht ein Akteur auf dem Startfeld,
    wird stattdessen die `START`-Angabe fortgeschrieben (A5).

    Setzt der Konstruktor ein Startobjekt ein -- `self.add_object(X(),
    *self.START)` --, ohne dass ein `start_actor` uebergeben wird, ist es aus
    der Welt entfernt worden. Dann wird auch die Anweisung im Konstruktor
    entfernt, samt der nicht mehr gebrauchten Einfuhr (A5c). Sonst kaeme das
    geloeschte Objekt beim naechsten Aufbau zurueck.

    Args:
        world: Die Welt, deren Aufbau gesichert wird.
        start_actor: Der Akteur, der ueber `START` eingesetzt wird -- `None`,
            wenn es keinen (mehr) gibt.
        path: Abweichende Zieldatei; ohne Angabe die Quelldatei der Klasse.
        dry_run: Alles vorbereiten, aber nichts schreiben. Damit laesst sich
            vorab feststellen, was der Vorgang bewirken wuerde.

    Returns:
        Ein Bericht darueber, was geschrieben wurde.

    Raises:
        SaveError: Wenn die Datei fehlt, die Klasse nicht enthaelt oder sich
            nicht schreiben laesst.
    """
    cls = type(world)
    target = path if path is not None else source_file(cls)
    text = target.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    try:
        tree = ast.parse(text, filename=str(target))
    except SyntaxError as error:
        raise SaveError(
            f"{target.name} enthaelt einen Syntaxfehler und wird nicht angeruehrt: {error}"
        ) from error

    class_node = _class_node(tree, cls.__name__)
    indent = _indent_of(class_node)

    placements, skipped = collect_placements(world, start_actor)
    edits: list[_Edit] = []

    # --- prepare() ersetzen oder anlegen -------------------------------
    method = _method_node(class_node, "prepare")
    flattened = False
    replaced_lines = 0
    new_method = render_prepare(placements, indent)

    if method is not None:
        first = method.decorator_list[0].lineno if method.decorator_list else method.lineno
        last = method.end_lineno or method.lineno
        replaced_lines = last - first + 1
        flattened = not _is_flat(method)
        edits.append(_Edit(first - 1, last, new_method))
    else:
        after = class_node.body[-1].end_lineno or class_node.lineno
        edits.append(_Edit(after, after, "\n" + new_method))

    # --- START fortschreiben -------------------------------------------
    start: tuple[int, int] | None = None
    if start_actor is not None:
        start = (start_actor.x, start_actor.y)
        assignment = _start_assignment(class_node)
        if assignment is not None and assignment.value is not None:
            edits.append(_start_edit(lines, assignment, assignment.value, start, indent))
        else:
            anchor = class_node.body[0].end_lineno or class_node.lineno
            edits.append(
                _Edit(
                    anchor,
                    anchor,
                    f"\n{indent}#: Von der Oberflaeche erzeugt: Feld, auf dem der\n"
                    f"{indent}#: uebergebene Akteur eingesetzt wird.\n"
                    f"{indent}{START_ATTRIBUTE} = ({start[0]}, {start[1]})\n",
                )
            )

    # --- ein geloeschtes Startobjekt aus dem Konstruktor nehmen (A5c) ----
    removed_start: tuple[str, ...] = ()
    additions = _start_additions(class_node)
    if additions and start_actor is None:
        for statement in additions:
            edits.append(
                _Edit(statement.lineno - 1, statement.end_lineno or statement.lineno, "")
            )
        names = {_created_class(statement) for statement in additions} - {""}
        removed_start = tuple(sorted(names))
        # Wird die Klasse in `prepare` wieder gebraucht, bleibt die Einfuhr.
        vorhanden: list[Actor] = world.objects()
        needed_again = {type(actor).__name__ for actor in vorhanden if can_save(actor)}
        edits.extend(_unused_import_edits(tree, names - needed_again, additions))

    # --- fehlende Einfuhren ergaenzen ----------------------------------
    from ..actor import Actor as _Actor

    known = _known_names(tree)
    needed: dict[str, str] = {}
    present: list[_Actor] = world.objects()
    for actor in present:
        if actor is start_actor or not can_save(actor):
            continue
        name = type(actor).__name__
        if name not in known and name not in needed:
            # Der kurze Weg, wie von Hand geschrieben: `from space import
            # PowerUp` statt `from space.actors.power_up import PowerUp` (E3).
            needed[name] = public_module_for(type(actor))

    added_imports: tuple[str, ...] = ()
    if needed:
        # Nach Modul buendeln, damit die Zeilen so aussehen wie von Hand
        # geschrieben (didaktische Auflage E3).
        by_module: dict[str, list[str]] = {}
        for name, module in sorted(needed.items()):
            by_module.setdefault(module, []).append(name)
        statements = "".join(
            f"from {module} import {', '.join(names)}\n"
            for module, names in sorted(by_module.items())
        )
        anchor = _last_import_line(tree)
        edits.append(_Edit(anchor, anchor, statements))
        added_imports = tuple(sorted(needed))

    changed = "".join(_apply_edits(lines, edits))

    # Gegenprobe: Was geschrieben wird, muss uebersetzbar sein.
    try:
        ast.parse(changed, filename=str(target))
    except SyntaxError as error:  # pragma: no cover -- Schutz gegen eigene Fehler
        raise SaveError(
            f"Der erzeugte Quelltext waere fehlerhaft ({error}). "
            f"{target.name} bleibt unveraendert."
        ) from error

    backup = (
        target.with_suffix(target.suffix + BACKUP_SUFFIX)
        if dry_run
        else _write_atomically(target, changed)
    )

    return SaveReport(
        path=target,
        backup=backup,
        objects=len(placements),
        replaced_lines=replaced_lines,
        added_imports=added_imports,
        start=start,
        skipped=tuple(skipped),
        flattened=flattened,
        removed_start=removed_start,
    )
