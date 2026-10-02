"""Tests fuer die Erzeugung der Klassendiagramme."""

from __future__ import annotations

from pathlib import Path

from pyfoot.diagram import build_plantuml, collect_classes, write_diagram

EXAMPLE_SOURCE = '''
class Base:
    """Eine Basisklasse."""

    count: int

    def __init__(self, name: str) -> None:
        self.name: str = name
        self._internal = 0
        self.__secret = 1

    def show(self) -> str:
        return self.name

    @property
    def length(self) -> int:
        return len(self.name)


class Derived(Base):
    def show(self) -> str:
        return self.name.upper()
'''


def _write_example(folder: Path) -> None:
    (folder / "example.py").write_text(EXAMPLE_SOURCE, encoding="utf-8")


def test_classes_are_found(tmp_path: Path) -> None:
    _write_example(tmp_path)
    classes = collect_classes(tmp_path)

    names = [c.name for c in classes]
    assert names == ["Base", "Derived"]


def test_inheritance_is_detected(tmp_path: Path) -> None:
    _write_example(tmp_path)
    classes = {c.name: c for c in collect_classes(tmp_path)}

    assert classes["Derived"].bases == ["Base"]
    assert classes["Base"].bases == []


def test_visibility_is_mapped(tmp_path: Path) -> None:
    _write_example(tmp_path)
    base = {c.name: c for c in collect_classes(tmp_path)}["Base"]

    attributes = " ".join(base.attributes)
    assert "+ name: str" in attributes
    assert "~ _internal" in attributes
    assert "- __secret" in attributes


def test_method_signature_contains_types(tmp_path: Path) -> None:
    _write_example(tmp_path)
    base = {c.name: c for c in collect_classes(tmp_path)}["Base"]

    methods = " ".join(base.methods)
    assert "+ __init__(name: str)" in methods
    assert "+ show() -> str" in methods
    assert "{property}" in methods


def test_self_is_not_shown_as_parameter(tmp_path: Path) -> None:
    _write_example(tmp_path)
    base = {c.name: c for c in collect_classes(tmp_path)}["Base"]
    assert all("self" not in m for m in base.methods)


def test_broken_file_does_not_abort_analysis(tmp_path: Path) -> None:
    _write_example(tmp_path)
    (tmp_path / "broken.py").write_text("class Missing(:\n", encoding="utf-8")

    classes = collect_classes(tmp_path)
    assert [c.name for c in classes] == ["Base", "Derived"]


def test_plantuml_contains_frame_and_arrow(tmp_path: Path) -> None:
    _write_example(tmp_path)
    text = build_plantuml(collect_classes(tmp_path), title="Test")

    assert text.startswith("@startuml Test")
    assert text.rstrip().endswith("@enduml")
    assert "class Base {" in text
    assert "Base <|-- Derived" in text


def test_file_is_written_locally(tmp_path: Path) -> None:
    _write_example(tmp_path)
    target = write_diagram(root=tmp_path, output_dir=tmp_path / "_structure")

    assert target.is_file()
    assert target.suffix == ".puml"
    assert "@startuml" in target.read_text(encoding="utf-8")
