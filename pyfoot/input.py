"""Maus- und Tastatureingabe fuer PyFoot.

Umgesetzt nach Anforderungsdokument 4.10.5: PyFoot stellt Eingabe bereit
(G5, G6). Im Kurs wird sie **nicht** verwendet (G7) -- der Kursinhalt bleibt
eingabefrei. Die Oberflaeche (Editor-Anforderungsdokument) baut darauf auf.

Beispiel:
    from pyfoot import Actor, is_key_down, mouse_clicked

    class Ship(Actor):
        def act(self) -> None:
            if is_key_down("left"):
                self.turn(-90)
            if mouse_clicked(self):
                self.remove()

Die Ereignisse werden von der Laufzeitsteuerung eingesammelt. Angaben, die
sich auf einen einzelnen Durchlauf beziehen -- Klicks, Tastendruecke --,
gelten jeweils bis zum naechsten Act-Durchlauf. Ob eine Taste *gerade*
gedrueckt ist, beantwortet dagegen `is_key_down` jederzeit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from .actor import Actor

__all__ = [
    "MouseInfo",
    "InputState",
    "is_key_down",
    "get_key",
    "mouse_info",
    "mouse_clicked",
    "mouse_pressed",
    "mouse_dragged",
    "mouse_moved",
]

#: Namen, die im Unterricht naheliegen, aber bei pygame anders heissen.
_KEY_ALIASES: dict[str, str] = {
    "enter": "return",
    "esc": "escape",
    "ctrl": "left ctrl",
    "alt": "left alt",
    "shift": "left shift",
    "control": "left ctrl",
}

#: Rueckrichtung fuer `get_key`, damit die Namen zu den Aliasnamen passen.
_KEY_NAMES: dict[str, str] = {"return": "enter"}


def _key_code(name: str) -> int:
    """Uebersetzt einen Tastennamen in den pygame-Code.

    Raises:
        ValueError: Wenn es keine Taste dieses Namens gibt.
    """
    plain = name.strip().lower()
    plain = _KEY_ALIASES.get(plain, plain)
    try:
        return pygame.key.key_code(plain)
    except ValueError:
        raise ValueError(
            f"Unbekannte Taste: '{name}'. Beispiele: 'left', 'space', 'enter', 'a'."
        ) from None


def _key_name(code: int) -> str:
    """Liefert den Namen einer Taste, passend zu den Namen von `is_key_down`."""
    name = pygame.key.name(code)
    return _KEY_NAMES.get(name, name)


class MouseInfo:
    """Auskunft ueber die Maus zum Zeitpunkt eines Ereignisses."""

    __slots__ = ("_x", "_y", "_pixel_x", "_pixel_y", "_button", "_clicks")

    def __init__(
        self,
        x: int,
        y: int,
        pixel_x: int,
        pixel_y: int,
        button: int = 0,
        clicks: int = 0,
    ) -> None:
        self._x = x
        self._y = y
        self._pixel_x = pixel_x
        self._pixel_y = pixel_y
        self._button = button
        self._clicks = clicks

    @property
    def x(self) -> int:
        """Die Spalte der Welt, ueber der die Maus steht."""
        return self._x

    @property
    def y(self) -> int:
        """Die Zeile der Welt, ueber der die Maus steht."""
        return self._y

    @property
    def pixel_x(self) -> int:
        """Die waagerechte Position im Fenster in Bildpunkten."""
        return self._pixel_x

    @property
    def pixel_y(self) -> int:
        """Die senkrechte Position im Fenster in Bildpunkten."""
        return self._pixel_y

    @property
    def button(self) -> int:
        """Die betaetigte Taste: 1 links, 2 Mitte, 3 rechts, 0 keine."""
        return self._button

    @property
    def clicks(self) -> int:
        """Anzahl der Klicks; 2 bei einem Doppelklick."""
        return self._clicks

    def __repr__(self) -> str:
        return (
            f"MouseInfo(x={self._x}, y={self._y}, "
            f"button={self._button}, clicks={self._clicks})"
        )


class InputState:
    """Sammelt Tastatur- und Mausereignisse.

    Die Laufzeitsteuerung fuellt den Zustand beim Abholen der Fensterereignisse
    und leert die durchlaufbezogenen Angaben vor jedem Act-Durchlauf.
    """

    __slots__ = (
        "_cell_size",
        "_origin",
        "_typed",
        "_position",
        "_clicked",
        "_pressed",
        "_dragged",
        "_moved",
        "_last_button",
        "_last_click_time",
    )

    #: Groesster Abstand zweier Klicks in Millisekunden, der noch als
    #: Doppelklick gilt.
    DOUBLE_CLICK_MS: int = 400

    def __init__(self, cell_size: int = 1) -> None:
        self._cell_size = max(1, cell_size)
        self._origin: tuple[int, int] = (0, 0)
        self._typed: list[str] = []
        self._position: tuple[int, int] = (0, 0)
        self._clicked: MouseInfo | None = None
        self._pressed: MouseInfo | None = None
        self._dragged: MouseInfo | None = None
        self._moved: MouseInfo | None = None
        self._last_button: int = 0
        self._last_click_time: int = 0

    # ------------------------------------------------------------------
    # Von der Laufzeitsteuerung gefuellt
    # ------------------------------------------------------------------

    @property
    def cell_size(self) -> int:
        """Kantenlaenge eines Feldes; noetig fuer die Feldkoordinaten."""
        return self._cell_size

    @cell_size.setter
    def cell_size(self, value: int) -> None:
        self._cell_size = max(1, value)

    @property
    def origin(self) -> tuple[int, int]:
        """Obere linke Ecke der Welt im Fenster.

        Ist das Fenster wegen der Bedienleiste breiter als die Welt, liegt
        diese mittig -- dann darf die Umrechnung in Feldkoordinaten den
        Randstreifen nicht mitzaehlen.
        """
        return self._origin

    @origin.setter
    def origin(self, value: tuple[int, int]) -> None:
        self._origin = value

    def _info(self, pixel: tuple[int, int], button: int, clicks: int) -> MouseInfo:
        """Baut eine Auskunft aus einer Position in Bildpunkten."""
        left = pixel[0] - self._origin[0]
        top = pixel[1] - self._origin[1]
        return MouseInfo(
            left // self._cell_size,
            top // self._cell_size,
            pixel[0],
            pixel[1],
            button,
            clicks,
        )

    def handle(self, event: pygame.event.Event) -> None:
        """Nimmt ein Fensterereignis entgegen."""
        if event.type == pygame.KEYDOWN:
            self._typed.append(_key_name(event.key))
        elif event.type == pygame.MOUSEMOTION:
            self._position = event.pos
            if event.buttons and any(event.buttons):
                self._dragged = self._info(event.pos, self._last_button, 0)
            else:
                self._moved = self._info(event.pos, 0, 0)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._position = event.pos
            self._last_button = event.button
            self._pressed = self._info(event.pos, event.button, 0)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._position = event.pos
            now = pygame.time.get_ticks()
            double = now - self._last_click_time <= InputState.DOUBLE_CLICK_MS
            self._last_click_time = now
            self._clicked = self._info(event.pos, event.button, 2 if double else 1)

    def begin_cycle(self) -> None:
        """Verwirft die Angaben des vorigen Durchlaufs."""
        self._typed.clear()
        self._clicked = None
        self._pressed = None
        self._dragged = None
        self._moved = None

    # ------------------------------------------------------------------
    # Abfragen
    # ------------------------------------------------------------------

    def is_key_down(self, key: str) -> bool:
        """Gibt an, ob die Taste gerade gedrueckt ist."""
        if not pygame.get_init():
            return False
        pressed = pygame.key.get_pressed()
        code = _key_code(key)
        return bool(pressed[code]) if code < len(pressed) else False

    def get_key(self) -> str | None:
        """Liefert die zuletzt gedrueckte Taste und verbraucht sie dabei."""
        return self._typed.pop(0) if self._typed else None

    def mouse_info(self) -> MouseInfo:
        """Liefert Auskunft ueber die aktuelle Mausposition."""
        return self._info(self._position, 0, 0)

    def _matches(self, info: MouseInfo | None, target: object | None) -> bool:
        """Prueft, ob ein Ereignis zum angefragten Ziel gehoert."""
        if info is None:
            return False
        if target is None:
            return True
        x: object = getattr(target, "x", None)
        y: object = getattr(target, "y", None)
        if not isinstance(x, int) or not isinstance(y, int):
            # Eine Welt hat keine Position: Jedes Ereignis gehoert zu ihr.
            return True
        return info.x == x and info.y == y

    def mouse_clicked(self, target: object | None = None) -> bool:
        """Gibt an, ob in diesem Durchlauf geklickt wurde."""
        return self._matches(self._clicked, target)

    def mouse_pressed(self, target: object | None = None) -> bool:
        """Gibt an, ob in diesem Durchlauf eine Maustaste gedrueckt wurde."""
        return self._matches(self._pressed, target)

    def mouse_dragged(self, target: object | None = None) -> bool:
        """Gibt an, ob in diesem Durchlauf mit gedrueckter Taste gezogen wurde."""
        return self._matches(self._dragged, target)

    def mouse_moved(self, target: object | None = None) -> bool:
        """Gibt an, ob die Maus in diesem Durchlauf bewegt wurde."""
        return self._matches(self._moved, target)

    def last_click(self) -> MouseInfo | None:
        """Liefert den Klick dieses Durchlaufs, falls es einen gab."""
        return self._clicked

    def __repr__(self) -> str:
        return f"InputState(position={self._position}, typed={len(self._typed)})"


# ----------------------------------------------------------------------
# Bequeme Modulfunktionen
# ----------------------------------------------------------------------


def _state() -> InputState:
    """Liefert den Eingabezustand der Laufzeitsteuerung."""
    from .engine import Engine

    return Engine.instance().input


def is_key_down(key: str) -> bool:
    """Gibt an, ob die genannte Taste gerade gedrueckt ist.

    Args:
        key: Name der Taste, etwa 'left', 'space', 'enter' oder 'a'.
    """
    return _state().is_key_down(key)


def get_key() -> str | None:
    """Liefert die zuletzt gedrueckte Taste und verbraucht sie dabei."""
    return _state().get_key()


def mouse_info() -> MouseInfo:
    """Liefert Auskunft ueber die aktuelle Mausposition."""
    return _state().mouse_info()


def mouse_clicked(target: Actor | object | None = None) -> bool:
    """Gibt an, ob in diesem Durchlauf geklickt wurde.

    Args:
        target: Ohne Angabe zaehlt jeder Klick. Wird ein Akteur uebergeben,
            zaehlt nur ein Klick auf dessen Feld.
    """
    return _state().mouse_clicked(target)


def mouse_pressed(target: Actor | object | None = None) -> bool:
    """Gibt an, ob in diesem Durchlauf eine Maustaste gedrueckt wurde."""
    return _state().mouse_pressed(target)


def mouse_dragged(target: Actor | object | None = None) -> bool:
    """Gibt an, ob in diesem Durchlauf mit gedrueckter Taste gezogen wurde."""
    return _state().mouse_dragged(target)


def mouse_moved(target: Actor | object | None = None) -> bool:
    """Gibt an, ob die Maus in diesem Durchlauf bewegt wurde."""
    return _state().mouse_moved(target)
