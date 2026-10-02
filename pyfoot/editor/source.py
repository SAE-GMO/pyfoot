"""Oeffnet Quelldateien im Editor.

Anforderung B3: Ein Befehl oeffnet die Quelldatei der angeklickten Klasse.
PyFoot bringt **keinen eigenen Texteditor** mit.

Gesucht wird in dieser Reihenfolge:

1. die Angabe in `PYFOOT_EDITOR` -- damit laesst sich jeder Editor eintragen
2. das VS Code, aus dessen Terminal das Programm gestartet wurde
3. `code` im Suchpfad
4. die ueblichen Orte einer VS-Code-Installation, auch die benutzereigene
5. die **Standardanwendung des Systems** fuer `.py`

Punkt 2 steht vorn, damit die Datei in dem VS Code landet, mit dem gerade
gearbeitet wird -- und nicht in einem zweiten, das zufaellig auch installiert
ist. Zusammen mit `--reuse-window` oeffnet sie sich dann im **schon offenen
Fenster** statt in einem neuen.

Punkt 3 bis 5 gibt es, weil ein aus dem ZIP entpacktes VS Code sich **nicht**
in den Suchpfad eintraegt -- und genau dieser Weg ist in der
Installationsanleitung als der einfachste empfohlen. Ohne sie bliebe der
Doppelklick auf eine Klasse dort wirkungslos.

Findet sich gar nichts, ist das kein Fehler: Die Rueckmeldung nennt dann Pfad
und Zeile, damit sich die Stelle von Hand oeffnen laesst.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

__all__ = [
    "EDITOR_COMMAND",
    "EDITOR_VARIABLE",
    "command_for",
    "find_editor",
    "open_in_editor",
    "open_with_system",
]

#: Aufruf von VS Code.
#:
#: `-r` oeffnet die Datei im **schon offenen Fenster**, statt ein zweites
#: aufzumachen; laeuft noch keines, startet VS Code eines. `-g datei:zeile`
#: springt an die Stelle.
EDITOR_COMMAND: tuple[str, ...] = ("code", "-r", "-g")

#: Umgebungsvariable, mit der sich ein anderer Editor eintragen laesst.
#: Der Pfad zeigt auf das Programm, nicht auf die Datei.
EDITOR_VARIABLE = "PYFOOT_EDITOR"

#: Von VS Code im eigenen Terminal gesetzt und auf `Code.exe` zeigend. Nicht
#: zugesichert, deshalb nur als einer von mehreren Versuchen -- der Fund wird
#: geprueft, bevor er benutzt wird.
_VSCODE_HINT = "VSCODE_GIT_ASKPASS_NODE"

#: Uebliche Orte einer VS-Code-Installation. `{}` steht fuer einen Ordner aus
#: der Umgebung; fehlt er, entfaellt der Eintrag.
_KNOWN_PLACES: tuple[tuple[str, str], ...] = (
    ("LOCALAPPDATA", r"Programs\Microsoft VS Code\bin\code.cmd"),
    ("PROGRAMFILES", r"Microsoft VS Code\bin\code.cmd"),
    ("PROGRAMFILES(X86)", r"Microsoft VS Code\bin\code.cmd"),
    ("LOCALAPPDATA", r"Programs\Microsoft VS Code Insiders\bin\code-insiders.cmd"),
)


def _from_variable() -> str | None:
    """Liefert den ausdruecklich eingetragenen Editor, falls es ihn gibt."""
    eintrag = os.environ.get(EDITOR_VARIABLE, "").strip().strip('"')
    if not eintrag:
        return None
    if Path(eintrag).is_file():
        return eintrag
    # Auch ein blosser Programmname ist erlaubt, etwa `notepad++`.
    return shutil.which(eintrag)


def _from_known_places() -> str | None:
    """Sucht VS Code an den ueblichen Orten unter Windows."""
    for variable, rest in _KNOWN_PLACES:
        ordner = os.environ.get(variable)
        if not ordner:
            continue
        kandidat = Path(ordner) / rest
        if kandidat.is_file():
            return str(kandidat)
    return None


def _from_running_vscode() -> str | None:
    """Findet das VS Code, aus dessen Terminal gestartet wurde.

    Trifft den Fall, den der Suchpfad nicht abdeckt: ein aus dem ZIP
    entpacktes VS Code. Neben `Code.exe` liegt `bin\\code.cmd`, das die
    Sprungmarke `-g` versteht.
    """
    hinweis = os.environ.get(_VSCODE_HINT)
    if not hinweis:
        return None
    programm = Path(hinweis)
    if not programm.is_file():
        return None
    for name in ("code.cmd", "code"):
        kandidat = programm.parent / "bin" / name
        if kandidat.is_file():
            return str(kandidat)
    return str(programm) if programm.is_file() else None


def find_editor() -> str | None:
    """Sucht ein Programm zum Oeffnen von Quelldateien.

    Returns:
        Der Pfad zum Programm, oder `None`, wenn keines zu finden ist.
    """
    for suche in (
        _from_variable,
        _from_running_vscode,
        lambda: shutil.which(EDITOR_COMMAND[0]),
        _from_known_places,
    ):
        gefunden = suche()
        if gefunden:
            return gefunden
    return None


def command_for(program: str, path: Path, line: int) -> list[str]:
    """Baut die Aufrufzeile fuer das gefundene Programm.

    Die Schalter aus `EDITOR_COMMAND` versteht nur VS Code. Ein anderer
    Editor -- ueber `PYFOOT_EDITOR` etwa Notepad++ oder Thonny -- bekommt
    allein den Dateinamen; er wuerde `-r` sonst fuer eine zu oeffnende Datei
    halten.
    """
    name = Path(program).name.lower()
    if name.startswith("code"):
        return [program, *EDITOR_COMMAND[1:], f"{path}:{line}"]
    return [program, str(path)]


def open_with_system(path: Path) -> bool:
    """Oeffnet die Datei mit der Standardanwendung des Systems.

    Der letzte Ausweg, wenn sich kein Editor finden laesst: Windows oeffnet
    `.py` dann mit dem, was dafuer eingetragen ist -- IDLE, Thonny, Notepad++.
    An eine Zeile springen laesst sich so nicht.

    Returns:
        Ob das Oeffnen angestossen werden konnte.
    """
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606 -- eigene Datei, kein Fremdeingang
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except (OSError, AttributeError):
        return False
    return True


def open_in_editor(path: Path, line: int = 1) -> str:
    """Oeffnet eine Datei im Editor und liefert die Rueckmeldung dazu.

    Args:
        path: Die zu oeffnende Datei.
        line: Zeile, an die gesprungen wird.

    Returns:
        Ein Satz fuer die Statuszeile -- im Erfolgsfall wie im Fehlerfall.
    """
    program = find_editor()
    if program is not None:
        try:
            subprocess.Popen(command_for(program, path, line))
        except OSError as error:
            return (
                f"Der Editor liess sich nicht starten ({error}). "
                f"Datei: {path.name}:{line}"
            )
        return f"{path.name}:{line} im Editor geoeffnet."

    if open_with_system(path):
        return f"{path.name} geoeffnet -- Zeile {line} von Hand ansteuern."

    return (
        f"Kein Editor gefunden. Die Stelle steht in {path.name}, Zeile {line}. "
        f"Mit {EDITOR_VARIABLE} laesst sich einer eintragen."
    )
