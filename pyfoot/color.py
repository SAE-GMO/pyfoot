"""Farben fuer PyFoot.

Kapselt die Farbdarstellung, damit im Kurscode nirgends direkt mit
pygame-Farbobjekten gearbeitet werden muss.
"""

from __future__ import annotations

from typing import ClassVar

import pygame

__all__ = ["Color"]


class Color:
    """Eine Farbe mit den Anteilen Rot, Gruen, Blau und optional Deckkraft.

    Alle Werte liegen zwischen 0 und 255.
    """

    __slots__ = ("_red", "_green", "_blue", "_alpha")

    # Werden unmittelbar nach der Klassendefinition belegt.
    BLACK: ClassVar[Color]
    WHITE: ClassVar[Color]
    RED: ClassVar[Color]
    GREEN: ClassVar[Color]
    BLUE: ClassVar[Color]
    YELLOW: ClassVar[Color]

    def __init__(self, red: int, green: int, blue: int, alpha: int = 255) -> None:
        for name, value in (
            ("red", red),
            ("green", green),
            ("blue", blue),
            ("alpha", alpha),
        ):
            if not 0 <= value <= 255:
                raise ValueError(
                    f"Der Farbanteil '{name}' muss zwischen 0 und 255 liegen, war {value}."
                )
        self._red = red
        self._green = green
        self._blue = blue
        self._alpha = alpha

    @property
    def red(self) -> int:
        """Der Rotanteil der Farbe."""
        return self._red

    @property
    def green(self) -> int:
        """Der Gruenanteil der Farbe."""
        return self._green

    @property
    def blue(self) -> int:
        """Der Blauanteil der Farbe."""
        return self._blue

    @property
    def alpha(self) -> int:
        """Die Deckkraft der Farbe (255 = vollstaendig deckend)."""
        return self._alpha

    def with_alpha(self, alpha: int) -> Color:
        """Liefert dieselbe Farbe mit einer anderen Deckkraft."""
        return Color(self._red, self._green, self._blue, alpha)

    @property
    def _pygame(self) -> pygame.Color:
        """Interne Umwandlung in eine pygame-Farbe."""
        return pygame.Color(self._red, self._green, self._blue, self._alpha)

    def as_tuple(self) -> tuple[int, int, int, int]:
        """Liefert die Farbe als Tupel (rot, gruen, blau, deckkraft)."""
        return (self._red, self._green, self._blue, self._alpha)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __hash__(self) -> int:
        return hash(self.as_tuple())

    def __repr__(self) -> str:
        return (
            f"Color(red={self._red}, green={self._green}, "
            f"blue={self._blue}, alpha={self._alpha})"
        )


Color.BLACK = Color(0, 0, 0)
Color.WHITE = Color(255, 255, 255)
Color.RED = Color(255, 0, 0)
Color.GREEN = Color(0, 255, 0)
Color.BLUE = Color(0, 0, 255)
Color.YELLOW = Color(255, 255, 0)
