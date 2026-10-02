"""Bilder fuer PyFoot.

Kapselt pygame-Oberflaechen, damit im Kurscode nicht direkt mit pygame
gearbeitet werden muss.
"""

from __future__ import annotations

import os
from pathlib import Path

import pygame

from .color import Color

__all__ = ["Image", "add_image_folder", "image_folders", "find_image"]

_image_folders: list[Path] = [Path("images")]


def add_image_folder(folder: str | os.PathLike[str]) -> None:
    """Fuegt einen Ordner hinzu, in dem nach Bilddateien gesucht wird.

    Zuletzt hinzugefuegte Ordner werden zuerst durchsucht.
    """
    _image_folders.insert(0, Path(folder))


def image_folders() -> list[Path]:
    """Liefert die aktuell durchsuchten Bildordner in Suchreihenfolge."""
    return list(_image_folders)


def find_image(filename: str) -> Path:
    """Sucht eine Bilddatei in den bekannten Bildordnern.

    Args:
        filename: Dateiname, auch mit Unterordner moeglich.

    Returns:
        Der gefundene Pfad.

    Raises:
        FileNotFoundError: Wenn die Datei in keinem Ordner liegt.
    """
    direct = Path(filename)
    if direct.is_file():
        return direct
    for folder in _image_folders:
        candidate = folder / filename
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(f) for f in _image_folders)
    raise FileNotFoundError(
        f"Bilddatei '{filename}' wurde nicht gefunden. Durchsucht: {searched}"
    )


class Image:
    """Ein Bild, das einem Akteur oder einer Welt zugeordnet werden kann."""

    __slots__ = ("_surface",)

    def __init__(self, surface: pygame.Surface) -> None:
        """Erzeugt ein Bild aus einer pygame-Oberflaeche.

        Im Kurscode werden stattdessen die Klassenmethoden `from_file`,
        `from_text` oder `blank` verwendet.
        """
        self._surface = surface

    @classmethod
    def from_file(cls, filename: str) -> Image:
        """Laedt ein Bild aus einer Datei.

        Gesucht wird in den ueber `add_image_folder` bekannt gemachten Ordnern.
        """
        path = find_image(filename)
        surface = pygame.image.load(str(path))
        # Die Umwandlung in das Bildschirmformat beschleunigt das Zeichnen,
        # setzt aber ein geoeffnetes Fenster voraus. Welten laden ihre Bilder
        # jedoch schon im Konstruktor, also bevor das Fenster existiert.
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            surface = surface.convert_alpha()
        return cls(surface)

    @classmethod
    def blank(cls, width: int, height: int, color: Color | None = None) -> Image:
        """Erzeugt ein einfarbiges Bild.

        Ohne Farbangabe ist das Bild vollstaendig durchsichtig.
        """
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill((color or Color(0, 0, 0, 0))._pygame)
        return cls(surface)

    @classmethod
    def from_text(
        cls,
        text: str,
        size: int,
        color: Color,
        background: Color | None = None,
        border: Color | None = None,
    ) -> Image:
        """Erzeugt ein Bild, das den uebergebenen Text zeigt.

        Args:
            text: Der darzustellende Text.
            size: Schriftgroesse in Punkt.
            color: Schriftfarbe.
            background: Hintergrundfarbe, ohne Angabe durchsichtig.
            border: Farbe eines Rahmens, ohne Angabe kein Rahmen.
        """
        if not pygame.font.get_init():
            pygame.font.init()
        font = pygame.font.Font(None, size)
        rendered = font.render(text, True, color._pygame)

        padding = 6
        width = rendered.get_width() + 2 * padding
        height = rendered.get_height() + 2 * padding
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        if background is not None:
            surface.fill(background._pygame)
        if border is not None:
            pygame.draw.rect(surface, border._pygame, surface.get_rect(), width=2)
        surface.blit(rendered, (padding, padding))
        return cls(surface)

    def copy(self) -> Image:
        """Liefert eine unabhaengige Kopie dieses Bildes."""
        return Image(self._surface.copy())

    @property
    def width(self) -> int:
        """Die Breite des Bildes in Bildpunkten."""
        return self._surface.get_width()

    @property
    def height(self) -> int:
        """Die Hoehe des Bildes in Bildpunkten."""
        return self._surface.get_height()

    def mirror_horizontally(self) -> Image:
        """Liefert das an der senkrechten Achse gespiegelte Bild (links/rechts)."""
        return Image(pygame.transform.flip(self._surface, True, False))

    def mirror_vertically(self) -> Image:
        """Liefert das an der waagerechten Achse gespiegelte Bild (oben/unten)."""
        return Image(pygame.transform.flip(self._surface, False, True))

    def scaled(self, width: int, height: int) -> Image:
        """Liefert das auf die angegebene Groesse skalierte Bild."""
        return Image(pygame.transform.smoothscale(self._surface, (width, height)))

    def rotated(self, degrees: float) -> Image:
        """Liefert das um den angegebenen Winkel gedrehte Bild.

        Positive Werte drehen im Uhrzeigersinn, passend zu den
        Bildschirmkoordinaten von PyFoot.
        """
        if degrees % 360 == 0:
            return self
        return Image(pygame.transform.rotate(self._surface, -degrees))

    def with_transparency(self, transparency: int) -> Image:
        """Liefert das Bild mit veraenderter Deckkraft (0 bis 255)."""
        if not 0 <= transparency <= 255:
            raise ValueError(
                f"Die Deckkraft muss zwischen 0 und 255 liegen, war {transparency}."
            )
        copy = self._surface.copy()
        copy.set_alpha(transparency)
        return Image(copy)

    def __repr__(self) -> str:
        return f"Image(width={self.width}, height={self.height})"
