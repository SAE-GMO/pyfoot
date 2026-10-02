"""PyFoot -- eine Lernumgebung fuer den Programmierunterricht.

PyFoot stellt eine Gitterwelt bereit, in der Akteure stehen und sich bewegen.
Anweisungen werden von oben nach unten in eine `init`-Methode geschrieben und
laufen sichtbar verlangsamt ab, waehrend das Fenster bedienbar bleibt.

Beispiel:
    from pyfoot import ScriptActor, World, set_world, run

    class Probe(ScriptActor):
        def init(self) -> None:
            self.move()
            self.turn(90)
            self.move()

    world = World(8, 8)
    world.add_object(Probe(), 0, 0)
    set_world(world)
    run()
"""

from __future__ import annotations

from .actor import EAST, NORTH, SOUTH, WEST, Actor, ScriptActor
from .color import Color
from .diagram import write_diagram
from .engine import (
    Engine,
    SimulationReset,
    SimulationStopped,
    disable_ui,
    enable_ui,
    get_engine,
    random_number,
    redraws,
    run,
    set_world,
    stop,
    ui_enabled,
    update_screen,
)
from .editor.codegen import set_class_folders
from .editor.errors import install_error_hook
from .image import Image, add_image_folder
from .input import (
    MouseInfo,
    get_key,
    is_key_down,
    mouse_clicked,
    mouse_dragged,
    mouse_info,
    mouse_moved,
    mouse_pressed,
)
from .world import World

__version__ = "0.1.1"

# Beendet ein Fehler das Programm -- etwa beim Start, bevor ein Fenster offen
# ist --, steht unter der gewohnten Ausgabe eine Zusammenfassung auf Deutsch
# (Editor-Anforderung H6). Am Verhalten des Programms aendert das nichts.
install_error_hook()

__all__ = [
    "Actor",
    "ScriptActor",
    "World",
    "Image",
    "Color",
    "Engine",
    "SimulationStopped",
    "SimulationReset",
    "EAST",
    "SOUTH",
    "WEST",
    "NORTH",
    "redraws",
    "get_engine",
    "set_world",
    "run",
    "stop",
    "update_screen",
    "random_number",
    "add_image_folder",
    "set_class_folders",
    "write_diagram",
    "enable_ui",
    "disable_ui",
    "ui_enabled",
    "MouseInfo",
    "is_key_down",
    "get_key",
    "mouse_info",
    "mouse_clicked",
    "mouse_pressed",
    "mouse_dragged",
    "mouse_moved",
    "__version__",
]
