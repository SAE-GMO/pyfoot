"""Prueft den Quelltext des Projekts selbst auf Typfehler.

Gemeint ist die Bibliothek und das Basisprojekt, nicht die Loesungen aus dem
Unterricht -- fuer die gibt es `check_code.py` mit milderen Einstellungen.
Hier gilt die strenge Einstellung aus `pyproject.toml`.

Die Pruefung ist nicht blockierend: Sie meldet das Ergebnis, der Rueckgabewert
ist immer 0 (Anforderungsdokument Abschnitt 5). Ausnahme ist `--ci` fuer die
automatische Pruefung auf GitHub: Dort soll ein Typfehler den Lauf rot faerben.

Der Aufruf gelingt aus jedem Verzeichnis:
    python tools\\check_project.py
    python tools\\check_project.py --ci
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

#: Aus dem Ort dieser Datei bestimmt, nicht aus dem Arbeitsverzeichnis.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Was zum Projekt gehoert und streng geprueft wird.
#: Was zum jeweiligen Projekt gehoert. Nicht vorhandene Eintraege werden
#: uebersprungen, dieselbe Datei laesst sich also in allen Projekten nutzen.
TARGETS = [
    "pyfoot",
    "space",
    "ships",
    "levels",
    "tools",
    "tests",
    "example_minimal.py",
    "main_space.py",
    "main_editor.py",
]


def run_mypy() -> tuple[int, str]:
    """Ruft mypy fuer den Projektquelltext auf.

    Returns:
        Rueckgabewert von mypy und die gesammelte Ausgabe.
    """
    existing = [name for name in TARGETS if (PROJECT_ROOT / name).exists()]
    result = subprocess.run(
        [sys.executable, "-m", "mypy", *existing],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def main(arguments: list[str]) -> int:
    """Prueft das Projekt und meldet das Ergebnis.

    Args:
        arguments: Befehlszeilenargumente; `--ci` gibt den Rueckgabewert von
            mypy weiter, statt immer 0 zu liefern.
    """
    ci = "--ci" in arguments
    print(f"Projektordner: {PROJECT_ROOT}")
    print("")

    try:
        code, output = run_mypy()
    except FileNotFoundError:
        print("mypy ist nicht installiert.")
        print("Nachinstallieren mit: python -m pip install mypy")
        return 1 if ci else 0

    if output:
        print(output)

    print("")
    if code == 0:
        print("Typpruefung ohne Beanstandung.")
    else:
        print("Die Typpruefung hat etwas gefunden (siehe oben).")
        print("Sie ist nicht blockierend -- das Projekt laeuft trotzdem.")

    return code if ci else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
