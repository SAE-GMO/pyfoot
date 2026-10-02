"""Minimalbeispiel fuer PyFoot ohne das Basisprojekt.

Zeigt das Ausfuehrungsmodell: Die Anweisungen in `init` stehen schlicht
untereinander und laufen sichtbar verlangsamt ab. Das Fenster bleibt
waehrenddessen bedienbar und laesst sich jederzeit schliessen.

Starten mit:
    python example_minimal.py
"""

from __future__ import annotations

from pyfoot import Color, Image, ScriptActor, World, get_engine, run, set_world


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
    """Baut die Welt auf und startet die Simulation."""
    world = World(width=8, height=8, cell_size=60)
    world.add_object(Probe(), 2, 2)

    set_world(world)
    get_engine().step_duration = 0.2
    run()


if __name__ == "__main__":
    main()
