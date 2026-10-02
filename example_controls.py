"""Beispiel fuer die Bedienleiste von PyFoot.

Zeigt dieselbe Anweisungsfolge wie `example_minimal.py`, diesmal aber mit
eingeschalteter Oberflaeche: Das Programm wartet auf den Startbefehl und
laesst sich Aktion fuer Aktion mitverfolgen.

Bedienung:
    Leertaste   Start und Pause
    D           ein vollstaendiger Durchlauf
    S           ein einzelner Schritt der Anweisungsfolge
    R           zuruecksetzen
    + / -       Tempo
    Esc         beenden

Dieselben Funktionen liegen als Schaltflaechen unter der Welt.

Starten mit:
    python example_controls.py

Ohne den Aufruf von `enable_ui()` verhaelt sich PyFoot wie bisher. Wer die
Leiste fuer ein bestehendes Programm einschalten moechte, ohne es zu aendern,
setzt die Umgebungsvariable PYFOOT_UI:

    $env:PYFOOT_UI = "1"; python example_minimal.py
"""

from __future__ import annotations

from pyfoot import (
    Color,
    Image,
    ScriptActor,
    World,
    enable_ui,
    get_engine,
    run,
    set_world,
)


class Probe(ScriptActor):
    """Ein Akteur, der ein Quadrat abfaehrt."""

    def __init__(self) -> None:
        super().__init__(image=Image.blank(34, 34, Color(120, 200, 255)))

    def init(self) -> None:
        """Faehrt zweimal ein Quadrat ab."""
        for _ in range(2):
            for _ in range(4):
                self.drive_edge()
                self.turn(90)

    def drive_edge(self) -> None:
        """Faehrt drei Felder geradeaus."""
        for _ in range(3):
            self.move()


def main() -> None:
    """Baut die Welt auf und startet die Oberflaeche."""
    # Vor set_world einschalten, damit das Fenster gleich Platz fuer die
    # Bedienleiste bekommt.
    enable_ui()

    world = World(width=8, height=8, cell_size=60)
    world.add_object(Probe(), 2, 2)

    set_world(world)
    get_engine().step_duration = 0.2
    run()


if __name__ == "__main__":
    main()
