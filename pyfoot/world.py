"""Die Welt, in der die Akteure stehen.

Die Welt ist ein Gitter aus quadratischen Feldern. Sie verwaltet die Akteure,
den Hintergrund und die angezeigten Texte und zeichnet sich selbst.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

import pygame

from .color import Color
from .image import Image

if TYPE_CHECKING:
    from .actor import Actor

__all__ = ["World"]

_A = TypeVar("_A", bound="Actor")


class World:
    """Ein rechteckiges Gitter, in dem Akteure stehen."""

    __slots__ = (
        "_width",
        "_height",
        "_cell_size",
        "_actors",
        "_paint_order",
        "_background",
        "_texts",
        "_grid_color",
    )

    DEFAULT_CELL_SIZE: int = 60

    def __init__(
        self, width: int = 8, height: int = 8, cell_size: int = DEFAULT_CELL_SIZE
    ) -> None:
        """Erzeugt eine Welt.

        Args:
            width: Anzahl der Spalten.
            height: Anzahl der Zeilen.
            cell_size: Kantenlaenge eines Feldes in Bildpunkten.
        """
        if width <= 0 or height <= 0:
            raise ValueError("Breite und Hoehe muessen groesser als 0 sein.")
        if cell_size <= 0:
            raise ValueError("Die Feldgroesse muss groesser als 0 sein.")

        self._width = width
        self._height = height
        self._cell_size = cell_size
        self._actors: list[Actor] = []
        self._paint_order: list[type[Actor]] = []
        self._background: Image | None = None
        self._texts: dict[tuple[int, int], Image] = {}
        self._grid_color: Color | None = Color(40, 44, 60)

    # ------------------------------------------------------------------
    # Groesse
    # ------------------------------------------------------------------

    @property
    def width(self) -> int:
        """Anzahl der Spalten."""
        return self._width

    @property
    def height(self) -> int:
        """Anzahl der Zeilen."""
        return self._height

    @property
    def cell_size(self) -> int:
        """Kantenlaenge eines Feldes in Bildpunkten."""
        return self._cell_size

    def contains(self, x: int, y: int) -> bool:
        """Gibt an, ob das Feld (x, y) innerhalb der Welt liegt."""
        return 0 <= x < self._width and 0 <= y < self._height

    # ------------------------------------------------------------------
    # Akteure
    # ------------------------------------------------------------------

    def add_object(self, actor: Actor, x: int, y: int) -> None:
        """Fuegt einen Akteur auf dem Feld (x, y) hinzu.

        Raises:
            TypeError: Wenn `actor` kein Akteur ist.
            ValueError: Wenn das Feld ausserhalb der Welt liegt. Ohne diese
                Pruefung stuende der Akteur unsichtbar neben der Welt -- ein
                Fehler ohne jede Meldung (Editor-Anforderung H8).
        """
        from .actor import Actor as _Actor

        if not isinstance(actor, _Actor):
            raise TypeError("add_object erwartet ein Objekt der Klasse Actor.")
        if not self.contains(x, y):
            raise ValueError(
                f"Das Feld ({x}, {y}) liegt ausserhalb der Welt. Erlaubt sind "
                f"x von 0 bis {self._width - 1} und y von 0 bis {self._height - 1}."
            )
        actor.set_location(x, y)
        actor._set_world(self)
        self._actors.append(actor)
        actor.on_added_to_world(self)

    def remove_object(self, actor: Actor) -> None:
        """Entfernt einen Akteur aus der Welt."""
        try:
            self._actors.remove(actor)
        except ValueError:
            raise ValueError(
                f"{type(actor).__name__} befindet sich nicht in dieser Welt."
            ) from None
        actor._set_world(None)

    def objects(self, cls: type[_A] | None = None) -> list[_A]:
        """Liefert alle Akteure der Welt, bei Angabe von `cls` nur diesen Typ."""
        if cls is None:
            return list(self._actors)  # type: ignore[arg-type]
        return [a for a in self._actors if isinstance(a, cls)]

    def objects_at(self, x: int, y: int, cls: type[_A] | None = None) -> list[_A]:
        """Liefert alle Akteure auf dem Feld (x, y)."""
        found = [a for a in self._actors if a.x == x and a.y == y]
        if cls is None:
            return found  # type: ignore[return-value]
        return [a for a in found if isinstance(a, cls)]

    def number_of_objects(self) -> int:
        """Liefert die Anzahl der Akteure in der Welt."""
        return len(self._actors)

    def set_paint_order(self, *classes: type[Actor]) -> None:
        """Legt fest, welche Klassen zuletzt (also obenauf) gezeichnet werden.

        Die zuerst genannte Klasse erscheint ganz oben, wie in Greenfoot.
        """
        self._paint_order = list(classes)

    # ------------------------------------------------------------------
    # Darstellung
    # ------------------------------------------------------------------

    def set_background(self, filename_or_image: str | Image) -> None:
        """Setzt das Hintergrundbild.

        Ist das Bild kleiner als die Welt, wird es gekachelt.
        """
        image = (
            Image.from_file(filename_or_image)
            if isinstance(filename_or_image, str)
            else filename_or_image
        )
        self._background = image

    @property
    def grid_color(self) -> Color | None:
        """Farbe der Gitterlinien; None schaltet sie ab."""
        return self._grid_color

    @grid_color.setter
    def grid_color(self, value: Color | None) -> None:
        self._grid_color = value

    def show_text(self, text: str | None, x: int, y: int) -> None:
        """Zeigt Text auf dem Feld (x, y) an; None entfernt ihn wieder."""
        if text is None or text == "":
            self._texts.pop((x, y), None)
            return
        self._texts[(x, y)] = Image.from_text(
            text, max(12, self._cell_size // 3), Color.WHITE, Color(0, 0, 0, 160)
        )

    def clear_texts(self) -> None:
        """Entfernt alle angezeigten Texte."""
        self._texts.clear()

    def text_at(self, x: int, y: int) -> str | None:
        """Liefert nur, ob auf dem Feld Text liegt (Text selbst wird nicht gespeichert)."""
        return "" if (x, y) in self._texts else None

    # ------------------------------------------------------------------
    # Ablauf
    # ------------------------------------------------------------------

    def act(self) -> None:
        """Wird in jedem Durchlauf einmal aufgerufen.

        Unterklassen koennen die Methode ueberschreiben; standardmaessig
        geschieht nichts.
        """

    def _act_cycle(self) -> None:
        """Fuehrt einen Durchlauf aus: erst die Welt, dann alle Akteure."""
        self.act()
        # Kopie, damit Akteure waehrend des Durchlaufs entfernt werden duerfen.
        for actor in list(self._actors):
            if actor.has_world:
                actor.act()

    # ------------------------------------------------------------------
    # Zeichnen
    # ------------------------------------------------------------------

    def _paint_sorted_actors(self) -> list[Actor]:
        """Sortiert die Akteure so, dass die Zeichenreihenfolge stimmt."""
        if not self._paint_order:
            return list(self._actors)

        def rank(actor: Actor) -> int:
            for index, cls in enumerate(self._paint_order):
                if isinstance(actor, cls):
                    return len(self._paint_order) - index
            return 0

        return sorted(self._actors, key=rank)

    def _render_to(self, surface: pygame.Surface) -> None:
        """Zeichnet Hintergrund, Gitter, Akteure und Texte auf die Oberflaeche."""
        self._render_background(surface)
        self._render_grid(surface)

        for actor in self._paint_sorted_actors():
            self._render_actor(surface, actor)

        for (x, y), text_image in self._texts.items():
            self._blit_centered(surface, text_image, x, y)

    def _render_background(self, surface: pygame.Surface) -> None:
        if self._background is None:
            surface.fill(Color(12, 14, 24)._pygame)
            return

        tile = self._background._surface
        tile_width, tile_height = tile.get_width(), tile.get_height()
        if tile_width <= 0 or tile_height <= 0:
            surface.fill(Color(12, 14, 24)._pygame)
            return

        for x in range(0, surface.get_width(), tile_width):
            for y in range(0, surface.get_height(), tile_height):
                surface.blit(tile, (x, y))

    def _render_grid(self, surface: pygame.Surface) -> None:
        if self._grid_color is None:
            return
        color = self._grid_color._pygame
        for column in range(self._width + 1):
            x = column * self._cell_size
            pygame.draw.line(surface, color, (x, 0), (x, self._height * self._cell_size))
        for row in range(self._height + 1):
            y = row * self._cell_size
            pygame.draw.line(surface, color, (0, y), (self._width * self._cell_size, y))

    def _render_actor(self, surface: pygame.Surface, actor: Actor) -> None:
        image = actor.image.rotated(actor.rotation)
        self._blit_centered(surface, image, actor.x, actor.y)

    def _blit_centered(
        self, surface: pygame.Surface, image: Image, x: int, y: int
    ) -> None:
        """Zeichnet ein Bild mittig auf das Feld (x, y)."""
        left = x * self._cell_size + (self._cell_size - image.width) // 2
        top = y * self._cell_size + (self._cell_size - image.height) // 2
        surface.blit(image._surface, (left, top))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(width={self._width}, height={self._height}, "
            f"cell_size={self._cell_size}, objects={len(self._actors)})"
        )
