"""Die Klassenanzeige am rechten Rand.

Zeigt die Klassen des laufenden Programms als Vererbungsbaum, getrennt nach
Welten und Akteuren (Anforderung B1), und die beiden Befehle, die zum
Bearbeiten gehoeren.

Wie ueberall gilt C1 und C2: Jede Funktion ist mit der Maus **und** ueber die
Tastatur erreichbar. Die setzbaren Klassen tragen die Ziffern 1 bis 9, die
beiden Befehle die Tasten B und W.

Auf einer Zeile:
    Klick          waehlt die Klasse zum Setzen aus
    Doppelklick    oeffnet ihre Quelldatei im Editor (B3a)
    Rechtsklick    oeffnet das Kontextmenue der Klasse
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import pygame

if TYPE_CHECKING:
    from ..actor import Actor
    from ..engine import Engine

__all__ = ["ClassRow", "ClassSidebar", "class_tree"]

_BACKGROUND = (22, 25, 33)
_SEPARATOR = (60, 66, 82)
_LABEL = (226, 230, 238)
_LABEL_ABSTRACT = (150, 158, 176)
_HINT = (128, 136, 152)
_NUMBER = (108, 116, 132)
_BUTTON = (52, 58, 74)
_BUTTON_ACTIVE = (58, 118, 178)
_ROW_SELECTED = (48, 74, 108)
_TREE_LINE = (66, 72, 88)


class ClassRow(NamedTuple):
    """Eine Zeile des Klassenbaums."""

    cls: type
    depth: int
    placeable: bool
    number: int | None


def class_tree() -> list[ClassRow]:
    """Baut den Vererbungsbaum aus den eingebundenen Klassen.

    Zuerst die Akteure, dann die Welten -- in Greenfoot stehen beide Baeume
    ebenfalls untereinander. Aufgenommen werden auch die Grundklassen von
    PyFoot: Sie zeigen, woher die eigenen Klassen ihre Faehigkeiten haben.
    """
    from ..actor import Actor as _Actor
    from ..world import World as _World
    from .mode import can_construct

    import sys

    rows: list[ClassRow] = []
    counter = 0

    def loaded(cls: type) -> bool:
        """Gibt an, ob die Klasse noch zum eingebundenen Stand gehoert.

        Eine geloeschte Klasse verschwindet sonst erst, wenn die
        Speicherbereinigung sie einsammelt -- und darauf ist kein Verlass,
        solange noch irgendwo ein Verweis liegt (Anforderung B8).

        Dasselbe gilt nach dem Neueinbinden geaenderter Dateien (H7): Die
        alte Klasse bleibt Unterklasse ihrer Grundklasse, bis sie eingesammelt
        ist. Traegt das Modul unter ihrem Namen inzwischen eine **andere**
        Klasse, ist sie ueberholt. Fehlt der Name ganz -- etwa bei einer
        Klasse, die in einer Funktion entstand --, bleibt sie sichtbar.
        """
        module = sys.modules.get(cls.__module__)
        if module is None:
            return False
        current = getattr(module, cls.__name__, None)
        return current is None or current is cls

    def walk(cls: type, depth: int, actors: bool) -> None:
        nonlocal counter
        if not loaded(cls):
            return
        # Die Bauteile von PyFoot stehen im Baum, lassen sich aber nicht
        # setzen: Sie sind Grundlage, keine Spielfiguren.
        placeable = (
            actors
            and not cls.__module__.startswith("pyfoot")
            and can_construct(cls)  # type: ignore[arg-type]
        )
        number = None
        if placeable:
            counter += 1
            number = counter if counter <= 9 else None
        rows.append(ClassRow(cls, depth, placeable, number))
        subclasses: list[type] = sorted(cls.__subclasses__(), key=lambda c: c.__name__)
        for subclass in subclasses:
            walk(subclass, depth + 1, actors)

    walk(_Actor, 0, True)
    walk(_World, 0, False)
    return rows


class ClassSidebar:
    """Zeichnet die Klassenanzeige und wertet ihre Ereignisse aus."""

    __slots__ = (
        "_engine",
        "_height",
        "_edit_button",
        "_save_button",
        "_rows",
        "_visible",
        "_scroll",
        "_font",
        "_small",
        "_last_click",
    )

    #: Breite der Anzeige in Bildpunkten.
    WIDTH: int = 190

    #: Hoehe einer Klassenzeile.
    ROW_HEIGHT: int = 21

    #: Einrueckung je Vererbungsstufe.
    INDENT: int = 10

    #: Groesster Abstand zweier Klicks in Millisekunden, der noch als
    #: Doppelklick gilt.
    DOUBLE_CLICK_MS: int = 400

    def __init__(self, engine: Engine, height: int) -> None:
        self._engine = engine
        self._height = height
        self._font: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        self._edit_button = pygame.Rect(0, 0, 0, 0)
        self._save_button = pygame.Rect(0, 0, 0, 0)
        self._rows: list[ClassRow] = []
        self._visible: list[tuple[ClassRow, pygame.Rect]] = []
        self._scroll = 0
        # Klasse und Zeitpunkt des letzten Klicks, um einen Doppelklick zu
        # erkennen (Anforderung B3a).
        self._last_click: tuple[type | None, int] = (None, 0)
        self.resize(height)

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------

    def resize(self, height: int) -> None:
        """Passt die Anzeige an eine neue Fensterhoehe an."""
        self._height = height
        width = ClassSidebar.WIDTH
        self._edit_button = pygame.Rect(10, 10, width - 20, 26)
        self._save_button = pygame.Rect(10, height - 36, width - 20, 26)

    @property
    def edit_button(self) -> pygame.Rect:
        """Lage der Schaltflaeche fuer den Bearbeitungsmodus."""
        return self._edit_button

    @property
    def save_button(self) -> pygame.Rect:
        """Lage der Schaltflaeche zum Sichern."""
        return self._save_button

    def refresh(self) -> None:
        """Sucht die Klassen erneut zusammen."""
        self._rows = class_tree()

    @property
    def tree(self) -> list[ClassRow]:
        """Die Zeilen des Klassenbaums."""
        if not self._rows:
            self.refresh()
        return list(self._rows)

    def _tree_area(self) -> pygame.Rect:
        """Liefert die Flaeche, in der der Baum steht."""
        top = self._edit_button.bottom + 24
        return pygame.Rect(
            6, top, ClassSidebar.WIDTH - 12, max(0, self._save_button.top - 40 - top)
        )

    def _layout(self) -> list[tuple[ClassRow, pygame.Rect]]:
        """Berechnet die sichtbaren Zeilen unter Beruecksichtigung des Rollens."""
        area = self._tree_area()
        rows = self.tree
        fit = max(0, area.height // ClassSidebar.ROW_HEIGHT)
        self._scroll = max(0, min(self._scroll, max(0, len(rows) - fit)))

        visible: list[tuple[ClassRow, pygame.Rect]] = []
        for offset, row in enumerate(rows[self._scroll : self._scroll + fit]):
            rect = pygame.Rect(
                area.left,
                area.top + offset * ClassSidebar.ROW_HEIGHT,
                area.width,
                ClassSidebar.ROW_HEIGHT,
            )
            visible.append((row, rect))
        return visible

    @property
    def rows(self) -> list[tuple[ClassRow, pygame.Rect]]:
        """Die aktuell sichtbaren Zeilen samt Lage."""
        if not self._visible:
            self._visible = self._layout()
        return list(self._visible)

    def scroll_by(self, steps: int) -> None:
        """Rollt den Baum um die angegebene Anzahl Zeilen."""
        self._scroll = max(0, self._scroll + steps)
        self._visible = self._layout()

    # ------------------------------------------------------------------
    # Ereignisse
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event, offset_x: int) -> bool:
        """Wertet ein Ereignis in der Klassenanzeige aus.

        Args:
            event: Das Ereignis.
            offset_x: Linke Kante der Anzeige im Fenster.

        Returns:
            True, wenn das Ereignis verbraucht wurde.
        """
        if event.type == pygame.KEYDOWN:
            return self._handle_key(event.key)
        if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL):
            return False

        if event.type == pygame.MOUSEWHEEL:
            position = pygame.mouse.get_pos()
            if position[0] < offset_x:
                return False
            self.scroll_by(-event.y)
            return True

        spot: tuple[int, int] = event.pos
        local = (int(spot[0]) - offset_x, int(spot[1]))
        if local[0] < 0 or local[1] < 0 or local[1] >= self._height:
            return False

        mode = self._engine.edit_mode
        if self._edit_button.collidepoint(local):
            if mode is not None:
                mode.toggle()
            return True
        if self._save_button.collidepoint(local):
            self._engine.request_save()
            return True

        self._visible = self._layout()
        for row, rect in self._visible:
            if not rect.collidepoint(local):
                continue
            if event.button == 3:
                self._engine.open_class_menu(row.cls, (int(spot[0]), int(spot[1])))
            elif event.button == 1:
                self._handle_left_click(row, mode)
            return True
        return True

    def _handle_left_click(self, row: ClassRow, mode: object) -> None:
        """Waehlt eine Klasse aus -- oder oeffnet beim Doppelklick ihre Datei."""
        from .mode import EditMode

        if self._is_double_click(row.cls):
            self._engine.open_source(row.cls)
            return

        if isinstance(mode, EditMode) and row.placeable:
            mode.select_class(row.cls)  # type: ignore[arg-type]
            if not mode.enabled:
                mode.enable()
        else:
            self._engine.status = (
                f"{row.cls.__name__} laesst sich nicht setzen. "
                "Doppelklick oeffnet den Quelltext, Rechtsklick das Menue."
            )

    def _is_double_click(self, cls: type) -> bool:
        """Gibt an, ob dieser Klick der zweite auf dieselbe Klasse war."""
        now = pygame.time.get_ticks()
        previous, when = self._last_click
        double = previous is cls and now - when <= ClassSidebar.DOUBLE_CLICK_MS
        # Nach einem Doppelklick von vorn zaehlen, damit ein dritter Klick
        # nicht erneut als Doppelklick gilt.
        self._last_click = (None if double else cls, now)
        return double

    def _handle_key(self, key: int) -> bool:
        """Tastenbedienung: B bearbeitet, W sichert."""
        mode = self._engine.edit_mode
        if key == pygame.K_b:
            if mode is not None:
                mode.toggle()
            return True
        if key == pygame.K_w:
            self._engine.request_save()
            return True
        return False

    # ------------------------------------------------------------------
    # Zeichnen
    # ------------------------------------------------------------------

    def _ensure_fonts(self) -> None:
        """Legt die Schriften an, sobald zum ersten Mal gezeichnet wird."""
        if self._font is not None:
            return
        if not pygame.font.get_init():
            pygame.font.init()
        self._font = pygame.font.Font(None, 19)
        self._small = pygame.font.Font(None, 16)

    def render(self, surface: pygame.Surface) -> None:
        """Zeichnet die Klassenanzeige auf die uebergebene Flaeche."""
        self._ensure_fonts()
        font, small = self._font, self._small
        if font is None or small is None:
            return

        mode = self._engine.edit_mode
        surface.fill(_BACKGROUND)
        pygame.draw.line(surface, _SEPARATOR, (0, 0), (0, surface.get_height()))

        editing = mode is not None and mode.enabled
        self._render_button(
            surface, font, self._edit_button, "Bearbeiten", "B", active=editing
        )

        top = self._edit_button.bottom + 6
        heading = small.render("Klassen", True, _HINT)
        surface.blit(heading, (12, top))
        # Ueber der Ziffernspalte steht, wofuer die Ziffern gut sind
        # (Anforderung C2a): Eine Taste zu zeigen genuegt nicht, wenn nicht
        # erkennbar ist, dass es eine Taste ist.
        legend = small.render("Taste", True, _NUMBER)
        surface.blit(legend, legend.get_rect(topright=(ClassSidebar.WIDTH - 8, top)))

        self.refresh()
        self._visible = self._layout()
        for row, rect in self._visible:
            self._render_row(surface, font, small, row, rect)

        hint = small.render("Doppelklick: Quelltext", True, _NUMBER)
        surface.blit(hint, (12, self._save_button.top - 34))
        hint = small.render("Rechtsklick: Menü", True, _NUMBER)
        surface.blit(hint, (12, self._save_button.top - 20))

        self._render_button(surface, font, self._save_button, "Welt sichern", "W")

    def _render_button(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        rect: pygame.Rect,
        label: str,
        key_hint: str,
        active: bool = False,
    ) -> None:
        """Zeichnet eine Schaltflaeche der Anzeige."""
        pygame.draw.rect(
            surface, _BUTTON_ACTIVE if active else _BUTTON, rect, border_radius=4
        )
        pygame.draw.rect(surface, _SEPARATOR, rect, width=1, border_radius=4)
        text = font.render(label, True, _LABEL)
        surface.blit(text, text.get_rect(center=(rect.centerx - 8, rect.centery)))
        if self._small is not None:
            hint = self._small.render(key_hint, True, _HINT)
            surface.blit(hint, hint.get_rect(midright=(rect.right - 8, rect.centery)))

    def _render_row(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        small: pygame.font.Font,
        row: ClassRow,
        rect: pygame.Rect,
    ) -> None:
        """Zeichnet eine Zeile des Baums mit Einrueckung, Ziffer und Bild."""
        from .mode import EditMode

        mode = self._engine.edit_mode
        selected = isinstance(mode, EditMode) and mode.selected_class is row.cls
        if selected:
            pygame.draw.rect(surface, _ROW_SELECTED, rect, border_radius=3)

        left = rect.left + 4 + row.depth * ClassSidebar.INDENT
        if row.depth > 0:
            # Ein kurzer Strich zeigt die Vererbungsbeziehung an.
            pygame.draw.line(
                surface,
                _TREE_LINE,
                (left - 6, rect.centery),
                (left - 1, rect.centery),
            )

        if row.number is not None:
            digit = small.render(str(row.number), True, _NUMBER)
            surface.blit(digit, digit.get_rect(midright=(rect.right - 4, rect.centery)))

        if row.placeable and isinstance(mode, EditMode):
            sample = mode.preview(row.cls)  # type: ignore[arg-type]
            if sample is not None:
                icon = sample.image
                if icon.width > 0 and icon.height > 0:
                    surface.blit(icon.scaled(14, 14)._surface, (left, rect.centery - 7))
            left += 18

        color = _LABEL if row.placeable else _LABEL_ABSTRACT
        name = font.render(row.cls.__name__, True, color)
        surface.blit(name, name.get_rect(midleft=(left, rect.centery)))

    def __repr__(self) -> str:
        return f"ClassSidebar(height={self._height}, rows={len(self._rows)})"
