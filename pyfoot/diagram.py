"""Erzeugt PlantUML-Klassendiagramme aus dem Projektquelltext.

Die Analyse erfolgt rein statisch ueber das `ast`-Modul: Der Quelltext wird
gelesen und geparst, aber nie importiert oder ausgefuehrt. Dadurch entstehen
keine Seiteneffekte, und auch unvollstaendiger Schuelercode laesst sich
zeichnen, solange er syntaktisch gueltig ist (Anforderungsdokument 4.8).

Es werden ausschliesslich lokale Dateien geschrieben. Ein Versand an externe
Dienste findet nicht statt.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["ClassInfo", "collect_classes", "build_plantuml", "write_diagram"]

_DEFAULT_IGNORED = {"__pycache__", ".git", ".venv", "venv", ".mypy_cache", ".pytest_cache"}


@dataclass
class ClassInfo:
    """Die aus dem Quelltext gelesene Beschreibung einer Klasse."""

    name: str
    bases: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


def _visibility(name: str) -> str:
    """Bildet die Python-Namenskonvention auf die PlantUML-Zeichen ab.

    Namen mit doppeltem Unterstrich vorn und hinten (etwa `__init__`) gehoeren
    zur oeffentlichen Schnittstelle und gelten deshalb als oeffentlich.
    """
    if name.startswith("__") and name.endswith("__"):
        return "+"
    if name.startswith("__"):
        return "-"
    if name.startswith("_"):
        return "~"
    return "+"


def _argument_text(argument: ast.arg) -> str:
    """Formatiert einen einzelnen Parameter mit seiner Typangabe."""
    if argument.annotation is None:
        return argument.arg
    return f"{argument.arg}: {ast.unparse(argument.annotation)}"


def _method_text(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Formatiert eine Methode als PlantUML-Zeile."""
    arguments = node.args
    parts: list[str] = [
        _argument_text(a) for a in (*arguments.posonlyargs, *arguments.args)
    ]
    if arguments.vararg is not None:
        parts.append("*" + _argument_text(arguments.vararg))
    parts.extend(_argument_text(a) for a in arguments.kwonlyargs)
    if arguments.kwarg is not None:
        parts.append("**" + _argument_text(arguments.kwarg))

    # Der erste Parameter einer Methode ist das Objekt selbst und wird
    # im Diagramm weggelassen.
    if parts and parts[0].split(":")[0].strip() in ("self", "cls"):
        parts = parts[1:]

    marker = ""
    for decorator in node.decorator_list:
        decorator_text = ast.unparse(decorator)
        if decorator_text in ("property", "staticmethod", "classmethod", "abstractmethod"):
            marker = f" {{{decorator_text}}}"
            break

    text = f"{_visibility(node.name)}{marker} {node.name}({', '.join(parts)})"
    if node.returns is not None and node.name != "__init__":
        text += f" -> {ast.unparse(node.returns)}"
    return text


def _attributes_from_init(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Liest die in `__init__` gesetzten Objektattribute aus."""
    found: list[str] = []
    for statement in ast.walk(node):
        if isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Attribute
        ):
            text = ast.unparse(statement.target)
            if text.startswith("self."):
                name = text[len("self.") :]
                found.append(
                    f"{_visibility(name)} {name}: {ast.unparse(statement.annotation)}"
                )
        elif isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Attribute):
                    text = ast.unparse(target)
                    if text.startswith("self."):
                        name = text[len("self.") :]
                        found.append(f"{_visibility(name)} {name}")
    # Reihenfolge erhalten, Doppelnennungen entfernen
    seen: set[str] = set()
    unique: list[str] = []
    for entry in found:
        key = entry.split(":")[0]
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique


def _class_from_node(node: ast.ClassDef) -> ClassInfo:
    """Wandelt einen Klassenknoten in eine Beschreibung um."""
    info = ClassInfo(name=node.name)
    for base in node.bases:
        info.bases.append(ast.unparse(base))

    for body_node in node.body:
        if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.methods.append(_method_text(body_node))
            if body_node.name == "__init__":
                info.attributes.extend(_attributes_from_init(body_node))
        elif isinstance(body_node, ast.AnnAssign) and isinstance(
            body_node.target, ast.Name
        ):
            name = body_node.target.id
            info.attributes.append(
                f"{_visibility(name)} {{static}} {name}: {ast.unparse(body_node.annotation)}"
            )
    return info


def collect_classes(
    root: str | Path, ignore: set[str] | None = None
) -> list[ClassInfo]:
    """Sammelt alle Klassen unterhalb von `root`.

    Args:
        root: Wurzelverzeichnis der Analyse.
        ignore: Zusaetzliche Ordnernamen, die uebersprungen werden.

    Returns:
        Die gefundenen Klassen in der Reihenfolge ihres Auftretens.
    """
    ignored = _DEFAULT_IGNORED | (ignore or set())
    classes: list[ClassInfo] = []

    for path in sorted(Path(root).rglob("*.py")):
        if any(part in ignored for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            # Fehlerhafte Dateien werden uebersprungen, nicht gemeldet:
            # unfertiger Schuelercode soll die Erzeugung nicht abbrechen.
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(_class_from_node(node))

    return classes


def build_plantuml(classes: list[ClassInfo], title: str = "PyFoot") -> str:
    """Formt die gesammelten Klassen zu einem PlantUML-Diagramm."""
    known = {info.name for info in classes}
    lines: list[str] = [f"@startuml {title}", "", "skinparam classAttributeIconSize 0", ""]

    for info in classes:
        lines.append(f"class {info.name} {{")
        for attribute in info.attributes:
            lines.append(f"  {attribute}")
        if info.attributes and info.methods:
            lines.append("  --")
        for method in info.methods:
            lines.append(f"  {method}")
        lines.append("}")
        lines.append("")

    for info in classes:
        for base in info.bases:
            # Nur Vererbung innerhalb des Projekts zeichnen.
            if base in known:
                lines.append(f"{base} <|-- {info.name}")

    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines)


def write_diagram(
    root: str | Path = ".",
    output_dir: str | Path = "_structure",
    filename: str = "diagram",
    title: str = "PyFoot",
    ignore: set[str] | None = None,
) -> Path:
    """Erzeugt das Klassendiagramm und schreibt es als PlantUML-Datei.

    Args:
        root: Wurzelverzeichnis der Analyse.
        output_dir: Zielordner; wird bei Bedarf angelegt.
        filename: Dateiname ohne Endung.
        title: Titel des Diagramms.
        ignore: Zusaetzliche Ordnernamen, die uebersprungen werden.

    Returns:
        Der Pfad der geschriebenen Datei.
    """
    classes = collect_classes(root, ignore)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{filename}.puml"
    target.write_text(build_plantuml(classes, title), encoding="utf-8")
    return target
