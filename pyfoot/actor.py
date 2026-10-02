"""Akteure fuer PyFoot.

Ein Akteur ist ein Objekt, das auf einem Feld der Welt steht. Die Klasse
`Actor` stellt die Grundfaehigkeiten bereit; `ScriptActor` ergaenzt das im
Unterricht benoetigte Muster einer einmalig ausgefuehrten `init`-Methode.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, TypeVar

from .engine import Engine, redraws
from .image import Image

if TYPE_CHECKING:
    from .world import World

__all__ = ["Actor", "ScriptActor", "EAST", "SOUTH", "WEST", "NORTH"]

#: Blickrichtungen als Drehwinkel. Die y-Achse zeigt nach unten,
#: deshalb entspricht 90 Grad der Richtung Sueden.
EAST: int = 0
SOUTH: int = 90
WEST: int = 180
NORTH: int = 270

_A = TypeVar("_A", bound="Actor")


class Actor(ABC):
    """Ein Objekt, das auf einem Feld der Welt steht."""

    __slots__ = ("_x", "_y", "_rotation", "_image", "_world")

    #: Name der Bilddatei dieser Klasse. Wer beim Erzeugen kein Bild uebergibt,
    #: bekommt dieses. Die Oberflaeche schreibt das Merkmal beim Zuweisen eines
    #: Bildes fort (Editor-Anforderungsdokument B5); von Hand laesst es sich
    #: ebenso setzen:
    #:
    #:     class Comet(Actor):
    #:         IMAGE = "comet.png"
    IMAGE: ClassVar[str | None] = None

    def __init__(self, image: Image | None = None, rotation: int = EAST) -> None:
        """Erzeugt einen Akteur.

        Args:
            image: Das darzustellende Bild. Ohne Angabe gilt das Klassenmerkmal
                `IMAGE`; fehlt auch das, entsteht ein leeres Bild.
            rotation: Die anfaengliche Blickrichtung in Grad.
        """
        self._x: int = 0
        self._y: int = 0
        self._rotation: int = rotation % 360
        self._image: Image = image if image is not None else self._default_image()
        self._world: World | None = None

    @classmethod
    def _default_image(cls) -> Image:
        """Liefert das Bild aus dem Klassenmerkmal `IMAGE`, sonst ein leeres."""
        filename = cls.IMAGE
        if filename:
            return Image.from_file(filename)
        return Image.blank(1, 1)

    # ------------------------------------------------------------------
    # Zustand
    # ------------------------------------------------------------------

    @property
    def x(self) -> int:
        """Die Spalte, in der der Akteur steht."""
        return self._x

    @property
    def y(self) -> int:
        """Die Zeile, in der der Akteur steht."""
        return self._y

    @property
    def rotation(self) -> int:
        """Die Blickrichtung in Grad (0 = Osten, 90 = Sueden)."""
        return self._rotation

    @rotation.setter
    def rotation(self, degrees: int) -> None:
        self._rotation = degrees % 360

    @property
    def image(self) -> Image:
        """Das Bild, mit dem der Akteur dargestellt wird."""
        return self._image

    @image.setter
    def image(self, value: Image) -> None:
        self._image = value

    @property
    def world(self) -> World:
        """Die Welt, in der der Akteur steht.

        Raises:
            RuntimeError: Wenn der Akteur noch keiner Welt hinzugefuegt wurde.
        """
        if self._world is None:
            raise RuntimeError(
                f"{type(self).__name__} wurde noch keiner Welt hinzugefuegt."
            )
        return self._world

    @property
    def has_world(self) -> bool:
        """Gibt an, ob der Akteur bereits in einer Welt steht."""
        return self._world is not None

    # ------------------------------------------------------------------
    # Von der Welt aufgerufen
    # ------------------------------------------------------------------

    def _set_world(self, world: World | None) -> None:
        """Wird von der Welt gesetzt, wenn der Akteur hinzugefuegt wird."""
        self._world = world

    def on_added_to_world(self, world: World) -> None:
        """Wird aufgerufen, sobald der Akteur einer Welt hinzugefuegt wurde.

        Unterklassen koennen die Methode ueberschreiben; standardmaessig
        geschieht nichts.
        """

    def act(self) -> None:
        """Wird in jedem Durchlauf einmal aufgerufen.

        Unterklassen koennen die Methode ueberschreiben; standardmaessig
        geschieht nichts.
        """

    def construction_code(self) -> str:
        """Liefert den Quelltext, der einen solchen Akteur erzeugt.

        Die Oberflaeche schreibt den Weltaufbau als Quelltext in die
        Weltklasse; dabei muss sie jeden Akteur benennen koennen. Akteure mit
        Werten im Konstruktor ueberschreiben die Methode, damit die Werte
        erhalten bleiben:

            def construction_code(self) -> str:
                return f"{type(self).__name__}({self._probability})"

        Returns:
            Ein Ausdruck wie 'PowerUp()', der einen gleichartigen Akteur
            erzeugt.
        """
        return f"{type(self).__name__}()"

    # ------------------------------------------------------------------
    # Bewegung
    # ------------------------------------------------------------------

    def set_location(self, x: int, y: int) -> None:
        """Setzt den Akteur unmittelbar auf das Feld (x, y)."""
        self._x = x
        self._y = y

    def move(self, distance: int = 1) -> None:
        """Bewegt den Akteur in Blickrichtung.

        Args:
            distance: Anzahl der Felder. Negative Werte bewegen rueckwaerts.
        """
        dx, dy = self.direction_offset()
        self._x += dx * distance
        self._y += dy * distance

    def turn(self, degrees: int) -> None:
        """Dreht den Akteur um den angegebenen Winkel."""
        self.rotation = self._rotation + degrees

    def direction_offset(self) -> tuple[int, int]:
        """Liefert die Schrittweite (dx, dy) fuer die aktuelle Blickrichtung.

        Raises:
            ValueError: Bei Blickrichtungen, die keinem der vier
                Gitterrichtungen entsprechen.
        """
        offsets: dict[int, tuple[int, int]] = {
            EAST: (1, 0),
            SOUTH: (0, 1),
            WEST: (-1, 0),
            NORTH: (0, -1),
        }
        try:
            return offsets[self._rotation]
        except KeyError:
            raise ValueError(
                f"Die Blickrichtung {self._rotation} Grad passt nicht zum Gitter. "
                "Erlaubt sind 0, 90, 180 und 270 Grad."
            ) from None

    # ------------------------------------------------------------------
    # Umgebung wahrnehmen
    # ------------------------------------------------------------------

    def objects_at_offset(
        self, dx: int, dy: int, cls: type[_A] | None = None
    ) -> list[_A]:
        """Liefert alle Objekte auf dem Feld, das um (dx, dy) versetzt liegt."""
        return self.world.objects_at(self._x + dx, self._y + dy, cls)

    def object_at_offset(
        self, dx: int, dy: int, cls: type[_A] | None = None
    ) -> _A | None:
        """Liefert ein Objekt auf dem versetzten Feld oder None."""
        found = self.objects_at_offset(dx, dy, cls)
        return found[0] if found else None

    def is_at_edge(self) -> bool:
        """Gibt an, ob der Akteur am Rand der Welt steht."""
        world = self.world
        return (
            self._x <= 0
            or self._y <= 0
            or self._x >= world.width - 1
            or self._y >= world.height - 1
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(x={self._x}, y={self._y}, rotation={self._rotation})"


class ScriptActor(Actor):
    """Ein Akteur, dessen `init`-Methode genau einmal ausgefuehrt wird.

    Das ist das Muster fuer den Unterricht: Schueler:innen schreiben ihre
    Anweisungen von oben nach unten in `init`. Damit das Fenster waehrend der
    Ausfuehrung bedienbar bleibt, sind die veraendernden Aktionen mit
    `redraws` gekennzeichnet (Anforderungsdokument 4.6).
    """

    __slots__ = ("_init_done",)

    def __init__(self, image: Image | None = None, rotation: int = EAST) -> None:
        super().__init__(image, rotation)
        self._init_done: bool = False

    @abstractmethod
    def init(self) -> None:
        """Hier stehen die Anweisungen, die der Akteur ausfuehren soll."""

    def act(self) -> None:
        """Ruft `init` beim ersten Durchlauf genau einmal auf."""
        if not self._init_done:
            self._init_done = True
            self.init()

    @property
    def init_done(self) -> bool:
        """Gibt an, ob `init` bereits ausgefuehrt wurde."""
        return self._init_done

    def _reset_init(self) -> None:
        """Gibt die Anweisungsfolge erneut frei.

        Wird vom Zuruecksetzen der Oberflaeche aufgerufen, damit `init` beim
        naechsten Durchlauf wieder ausgefuehrt wird.
        """
        self._init_done = False

    # Die folgenden Aktionen veraendern den sichtbaren Zustand und drehen
    # deshalb nach ihrer Ausfuehrung die Ereignisschleife einen Schritt weiter.

    @redraws
    def move(self, distance: int = 1) -> None:
        """Bewegt den Akteur in Blickrichtung und zeichnet neu."""
        super().move(distance)

    @redraws
    def turn(self, degrees: int) -> None:
        """Dreht den Akteur und zeichnet neu."""
        super().turn(degrees)

    @redraws
    def set_location(self, x: int, y: int) -> None:
        """Setzt den Akteur auf das Feld (x, y) und zeichnet neu."""
        super().set_location(x, y)

    def update_screen(self) -> None:
        """Zeichnet neu, ohne dass sich etwas veraendert hat.

        Aus langen Rechenschleifen heraus aufrufen, damit das Fenster
        bedienbar bleibt.
        """
        Engine.instance().update_screen()
