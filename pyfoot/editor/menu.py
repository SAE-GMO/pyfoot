"""Kontextmenue und Texteingabe der Oberflaeche.

Greenfoot bietet zu Klassen und Objekten je ein Kontextmenue; PyFoot bildet
das mit einem schlichten, selbst gezeichneten Menue nach
(Editor-Anforderungsdokument B3 bis B5 und D1 bis D3).

Wie ueberall gilt C1 und C2: Jeder Eintrag ist mit der Maus anklickbar und
ueber seine Ziffer erreichbar. `Esc` schliesst das Menue -- und nur das
Menue, das Fenster bleibt offen.
"""

from __future__ import annotations

import re
from typing import Callable, NamedTuple

import pygame

__all__ = [
    "MenuEntry",
    "ContextMenu",
    "TextPrompt",
    "Inspector",
    "attributes",
    "attribute_names",
    "editable_attributes",
]

_BACKGROUND = (32, 36, 46)
_BORDER = (86, 94, 112)
_LABEL = (226, 230, 238)
_LABEL_DISABLED = (110, 116, 130)
_HINT = (128, 136, 152)
_HOVER = (58, 118, 178)
_TITLE = (150, 158, 176)
#: Farbe der Attribute, die sich aendern lassen -- sie landen beim Sichern
#: im Quelltext (Anforderung D5).
_EDITABLE = (140, 210, 160)


class MenuEntry(NamedTuple):
    """Ein Eintrag des Kontextmenues."""

    label: str
    action: Callable[[], None]
    enabled: bool = True


class ContextMenu:
    """Ein Menue, das ueber der Welt liegt."""

    __slots__ = ("_title", "_entries", "_position", "_rect", "_hover", "_font", "_small")

    #: Hoehe einer Zeile in Bildpunkten.
    ROW_HEIGHT: int = 24

    #: Breite des Menues.
    WIDTH: int = 210

    #: Hoehe der Ueberschrift.
    TITLE_HEIGHT: int = 22

    def __init__(
        self, title: str, entries: list[MenuEntry], position: tuple[int, int]
    ) -> None:
        """Erzeugt ein Menue an der angegebenen Stelle im Fenster."""
        self._title = title
        self._entries = entries
        self._position = position
        self._hover: int | None = None
        self._font: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        self._rect = pygame.Rect(
            position[0],
            position[1],
            ContextMenu.WIDTH,
            ContextMenu.TITLE_HEIGHT + ContextMenu.ROW_HEIGHT * len(entries) + 8,
        )

    @property
    def title(self) -> str:
        """Die Ueberschrift des Menues."""
        return self._title

    @property
    def entries(self) -> list[MenuEntry]:
        """Die Eintraege des Menues."""
        return list(self._entries)

    @property
    def rect(self) -> pygame.Rect:
        """Lage und Groesse im Fenster."""
        return self._rect

    def fit_into(self, width: int, height: int) -> None:
        """Verschiebt das Menue, damit es ganz im Fenster liegt."""
        self._rect.left = max(0, min(self._rect.left, width - self._rect.width))
        self._rect.top = max(0, min(self._rect.top, height - self._rect.height))

    def _row_rect(self, index: int) -> pygame.Rect:
        """Liefert das Rechteck einer Zeile."""
        return pygame.Rect(
            self._rect.left + 4,
            self._rect.top + ContextMenu.TITLE_HEIGHT + index * ContextMenu.ROW_HEIGHT,
            self._rect.width - 8,
            ContextMenu.ROW_HEIGHT,
        )

    def entry_at(self, position: tuple[int, int]) -> int | None:
        """Liefert die Zeile an dieser Stelle im Fenster."""
        for index in range(len(self._entries)):
            if self._row_rect(index).collidepoint(position):
                return index
        return None

    def choose(self, index: int) -> bool:
        """Fuehrt den Eintrag aus; liefert False, wenn er nichts bewirkt."""
        if not 0 <= index < len(self._entries):
            return False
        entry = self._entries[index]
        if not entry.enabled:
            return False
        entry.action()
        return True

    def handle_event(self, event: pygame.event.Event) -> tuple[bool, bool]:
        """Wertet ein Ereignis aus.

        Returns:
            Ein Paar aus `verbraucht` und `schliessen`.
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return True, True
            if pygame.K_1 <= event.key <= pygame.K_9:
                self.choose(event.key - pygame.K_1)
                return True, True
            return True, False

        if event.type == pygame.MOUSEMOTION:
            position: tuple[int, int] = event.pos
            self._hover = self.entry_at((int(position[0]), int(position[1])))
            return True, False

        if event.type == pygame.MOUSEBUTTONDOWN:
            spot: tuple[int, int] = event.pos
            point = (int(spot[0]), int(spot[1]))
            index = self.entry_at(point)
            if index is not None:
                self.choose(index)
                return True, True
            # Ein Klick daneben schliesst das Menue.
            return True, True

        return False, False

    def _ensure_fonts(self) -> None:
        """Legt die Schriften an, sobald zum ersten Mal gezeichnet wird."""
        if self._font is not None:
            return
        if not pygame.font.get_init():
            pygame.font.init()
        self._font = pygame.font.Font(None, 20)
        self._small = pygame.font.Font(None, 16)

    def render(self, surface: pygame.Surface) -> None:
        """Zeichnet das Menue in das Fenster."""
        self._ensure_fonts()
        font, small = self._font, self._small
        if font is None or small is None:
            return

        pygame.draw.rect(surface, _BACKGROUND, self._rect, border_radius=5)
        pygame.draw.rect(surface, _BORDER, self._rect, width=1, border_radius=5)

        heading = small.render(self._title, True, _TITLE)
        surface.blit(heading, (self._rect.left + 8, self._rect.top + 5))

        for index, entry in enumerate(self._entries):
            row = self._row_rect(index)
            if index == self._hover and entry.enabled:
                pygame.draw.rect(surface, _HOVER, row, border_radius=3)

            color = _LABEL if entry.enabled else _LABEL_DISABLED
            if index < 9:
                digit = small.render(str(index + 1), True, _HINT)
                surface.blit(digit, digit.get_rect(midleft=(row.left + 6, row.centery)))
            # Klassennamen wie `Level3gGiantRandomPowerUpField` sprengen die
            # Zeile; sie werden gekuerzt statt ueberzulaufen.
            label = _shortened(font, entry.label, row.width - 28)
            text = font.render(label, True, color)
            surface.blit(text, text.get_rect(midleft=(row.left + 22, row.centery)))

    def __repr__(self) -> str:
        return f"ContextMenu(title={self._title!r}, entries={len(self._entries)})"


class TextPrompt:
    """Eine einzeilige Eingabe, etwa fuer den Namen einer neuen Klasse."""

    __slots__ = ("_question", "_text", "_on_accept", "_rect", "_font", "_small")

    #: Hoehe der Eingabe in Bildpunkten.
    HEIGHT: int = 62

    #: Breite der Eingabe.
    WIDTH: int = 320

    def __init__(
        self, question: str, on_accept: Callable[[str], None], text: str = ""
    ) -> None:
        """Erzeugt eine Eingabe mit der Frage und dem Empfaenger der Antwort.

        Args:
            question: Die Frage ueber dem Eingabefeld.
            on_accept: Bekommt den Text, sobald bestaetigt wird.
            text: Voreingetragener Text -- etwa die bisherigen Werte, damit
                ein Druck auf die Eingabetaste sie unveraendert uebernimmt.
        """
        self._question = question
        self._text = text
        self._on_accept = on_accept
        self._rect = pygame.Rect(0, 0, TextPrompt.WIDTH, TextPrompt.HEIGHT)
        self._font: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None

    @property
    def question(self) -> str:
        """Die gestellte Frage."""
        return self._question

    @property
    def text(self) -> str:
        """Der bisher eingegebene Text."""
        return self._text

    def center_in(self, width: int, height: int) -> None:
        """Stellt die Eingabe mittig in eine Flaeche."""
        self._rect.center = (width // 2, height // 2)

    def handle_event(self, event: pygame.event.Event) -> tuple[bool, bool]:
        """Wertet ein Ereignis aus.

        Returns:
            Ein Paar aus `verbraucht` und `schliessen`.
        """
        if event.type != pygame.KEYDOWN:
            # Solange die Eingabe offen ist, gehoert ihr auch die Maus --
            # sonst liefe ein Klick versehentlich in die Welt.
            return event.type in (
                pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP,
                pygame.MOUSEMOTION,
            ), False

        if event.key == pygame.K_ESCAPE:
            return True, True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self._text:
                self._on_accept(self._text)
            return True, True
        if event.key == pygame.K_BACKSPACE:
            self._text = self._text[:-1]
            return True, False

        letter = getattr(event, "unicode", "")
        if letter and letter.isprintable() and len(self._text) < 40:
            self._text += letter
        return True, False

    def _ensure_fonts(self) -> None:
        """Legt die Schriften an, sobald zum ersten Mal gezeichnet wird."""
        if self._font is not None:
            return
        if not pygame.font.get_init():
            pygame.font.init()
        self._font = pygame.font.Font(None, 24)
        self._small = pygame.font.Font(None, 16)

    def render(self, surface: pygame.Surface) -> None:
        """Zeichnet die Eingabe in das Fenster."""
        self._ensure_fonts()
        font, small = self._font, self._small
        if font is None or small is None:
            return

        pygame.draw.rect(surface, _BACKGROUND, self._rect, border_radius=5)
        pygame.draw.rect(surface, _BORDER, self._rect, width=1, border_radius=5)

        question = small.render(self._question, True, _TITLE)
        surface.blit(question, (self._rect.left + 10, self._rect.top + 8))

        field = pygame.Rect(self._rect.left + 10, self._rect.top + 28, self._rect.width - 20, 24)
        pygame.draw.rect(surface, (18, 20, 28), field, border_radius=3)
        text = font.render(self._text + "_", True, _LABEL)
        surface.blit(text, text.get_rect(midleft=(field.left + 6, field.centery)))

    def __repr__(self) -> str:
        return f"TextPrompt(question={self._question!r}, text={self._text!r})"


#: Laengste Darstellung eines Wertes; laengere werden gekuerzt.
_VALUE_LIMIT = 30


def attribute_names(target: object) -> list[str]:
    """Sammelt die Namen der Attribute eines Objekts.

    Beruecksichtigt werden die ueber `__slots__` festgelegten Attribute der
    ganzen Vererbungskette und -- falls vorhanden -- die frei gesetzten aus
    `__dict__`.
    """
    names: list[str] = []
    for cls in type(target).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for slot in slots:
            if slot not in names:
                names.append(slot)

    try:
        own = vars(target)
    except TypeError:  # Objekt ohne __dict__ -- der Regelfall in PyFoot.
        own = {}
    names.extend(name for name in own if name not in names)
    return sorted(names)


def attributes(target: object) -> list[tuple[str, str]]:
    """Sammelt die Attribute eines Objekts samt ihrer aktuellen Werte.

    Gezeigt wird der tatsaechliche Zustand des Objekts, auch der intern
    gehaltene: Genau er macht das Objekt aus.
    """
    rows: list[tuple[str, str]] = []
    for name in attribute_names(target):
        try:
            value = repr(getattr(target, name))
        except Exception as error:  # pragma: no cover -- eigenwillige Attribute
            value = f"<{type(error).__name__}>"
        if len(value) > _VALUE_LIMIT:
            value = value[: _VALUE_LIMIT - 1] + "…"
        rows.append((name, value))
    return rows


def editable_attributes(target: object) -> set[str]:
    """Liefert die Attribute, die sich gefahrlos aendern lassen.

    Bearbeitbar ist nur, **was beim Sichern der Welt auch im Quelltext
    landet** -- also im Ausdruck aus `construction_code` vorkommt. Bei
    `RandomPowerUp(0.5)` ist das die Wahrscheinlichkeit.

    Der Grund ist das Leitprinzip: Der Quelltext ist die einzige Wahrheit.
    Ein Wert, der nur zur Laufzeit existierte, waere beim naechsten
    Zuruecksetzen wieder weg -- eine Aenderung daran taeuschte Dauerhaftigkeit
    vor, die es nicht gibt.

    Die Lage eines Objekts steht nicht in dieser Liste: Sie wird durch Ziehen
    geaendert (Anforderung A3).
    """
    from ..actor import Actor as _Actor

    if not isinstance(target, _Actor):
        return set()
    try:
        code = target.construction_code()
    except Exception:  # pragma: no cover -- eigenwillige Akteure
        return set()

    found: set[str] = set()
    for name in attribute_names(target):
        value = getattr(target, name, None)
        if not isinstance(value, (int, float, str, bool)):
            continue
        # Als ganzer Wert vorkommen, nicht als Teil eines anderen: Die 5 aus
        # `_count` steckt sonst schon in `RandomPowerUp(0.5)`.
        muster = r"(?<![\w.])" + re.escape(repr(value)) + r"(?![\w.])"
        if re.search(muster, code):
            found.add(name)
    return found


def _shortened(font: pygame.font.Font, text: str, room: int) -> str:
    """Kuerzt einen Text so weit, dass er in die angegebene Breite passt."""
    if room <= 0 or font.size(text)[0] <= room:
        return text
    shortened = text
    while shortened and font.size(shortened + "…")[0] > room:
        shortened = shortened[:-1]
    return shortened + "…"


class Inspector:
    """Zeigt den Zustand eines Objekts an -- Greenfoots *Inspect*.

    Die Werte werden bei jedem Zeichnen neu gelesen. Zusammen mit dem
    Einzelschritt laesst sich damit zusehen, wie sich ein Wert Anweisung fuer
    Anweisung aendert (Anforderung D4).

    Die Anzeige ist nur lesend und laesst die Bedienleiste durch: Ein
    Tastendruck auf `Leertaste` oder `S` wirkt weiterhin.
    """

    __slots__ = ("_target", "_rect", "_font", "_small", "_on_edit", "_hover")

    #: Breite der Anzeige in Bildpunkten.
    WIDTH: int = 250

    #: Hoehe einer Zeile.
    ROW_HEIGHT: int = 18

    #: Hoehe von Ueberschrift und Fusszeile zusammen.
    CHROME_HEIGHT: int = 44

    def __init__(
        self,
        target: object,
        position: tuple[int, int],
        on_edit: Callable[[str], None] | None = None,
    ) -> None:
        """Erzeugt die Anzeige fuer ein Objekt an der angegebenen Stelle.

        Args:
            target: Das Objekt, dessen Zustand gezeigt wird.
            position: Obere linke Ecke im Fenster.
            on_edit: Bekommt den Namen eines Attributs, wenn darauf geklickt
                wird -- aber nur bei Attributen, die sich aendern lassen.
        """
        self._target = target
        self._on_edit = on_edit
        self._hover: str | None = None
        self._font: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        rows = len(attributes(target))
        self._rect = pygame.Rect(
            position[0],
            position[1],
            Inspector.WIDTH,
            Inspector.CHROME_HEIGHT + Inspector.ROW_HEIGHT * max(1, rows),
        )

    @property
    def target(self) -> object:
        """Das angezeigte Objekt."""
        return self._target

    @property
    def rect(self) -> pygame.Rect:
        """Lage und Groesse im Fenster."""
        return self._rect

    def rows(self) -> list[tuple[str, str]]:
        """Liest die Attribute jetzt -- nicht beim Oeffnen."""
        return attributes(self._target)

    def editable(self) -> set[str]:
        """Liefert die Attribute, die sich aendern lassen."""
        return editable_attributes(self._target)

    def row_rect(self, index: int) -> pygame.Rect:
        """Liefert das Rechteck einer Zeile im Fenster."""
        return pygame.Rect(
            self._rect.left + 6,
            self._rect.top + 22 + index * Inspector.ROW_HEIGHT,
            self._rect.width - 12,
            Inspector.ROW_HEIGHT,
        )

    def attribute_at(self, position: tuple[int, int]) -> str | None:
        """Liefert den Namen des Attributs an dieser Stelle."""
        for index, (name, _) in enumerate(self.rows()):
            if self.row_rect(index).collidepoint(position):
                return name
        return None

    def fit_into(self, width: int, height: int) -> None:
        """Verschiebt die Anzeige, damit sie ganz im Fenster liegt."""
        self._rect.left = max(0, min(self._rect.left, width - self._rect.width))
        self._rect.top = max(0, min(self._rect.top, height - self._rect.height))

    def handle_event(self, event: pygame.event.Event) -> tuple[bool, bool]:
        """Wertet ein Ereignis aus.

        Verbraucht wird nur, was die Anzeige selbst betrifft. Alles andere
        laeuft weiter an die Bedienleiste -- sonst liesse sich waehrend des
        Zusehens nicht weiterschalten.

        Returns:
            Ein Paar aus `verbraucht` und `schliessen`.
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return True, True
            return False, False

        if event.type == pygame.MOUSEMOTION:
            spot: tuple[int, int] = event.pos
            point = (int(spot[0]), int(spot[1]))
            if not self._rect.collidepoint(point):
                self._hover = None
                return False, False
            name = self.attribute_at(point)
            self._hover = name if name in self.editable() else None
            return True, False

        if event.type == pygame.MOUSEBUTTONDOWN:
            position: tuple[int, int] = event.pos
            point = (int(position[0]), int(position[1]))
            if not self._rect.collidepoint(point):
                return False, False

            name = self.attribute_at(point)
            if self._on_edit is not None and name in self.editable():
                # Ein bearbeitbares Attribut anzuklicken oeffnet die Eingabe;
                # die Anzeige bleibt dabei stehen.
                self._on_edit(name)
                return True, False
            return True, True

        return False, False

    def _ensure_fonts(self) -> None:
        """Legt die Schriften an, sobald zum ersten Mal gezeichnet wird."""
        if self._font is not None:
            return
        if not pygame.font.get_init():
            pygame.font.init()
        self._font = pygame.font.Font(None, 18)
        self._small = pygame.font.Font(None, 16)

    def render(self, surface: pygame.Surface) -> None:
        """Zeichnet die Anzeige mit den aktuellen Werten."""
        self._ensure_fonts()
        font, small = self._font, self._small
        if font is None or small is None:
            return

        rows = self.rows()
        self._rect.height = Inspector.CHROME_HEIGHT + Inspector.ROW_HEIGHT * max(
            1, len(rows)
        )

        pygame.draw.rect(surface, _BACKGROUND, self._rect, border_radius=5)
        pygame.draw.rect(surface, _BORDER, self._rect, width=1, border_radius=5)

        heading = small.render(
            f"{type(self._target).__name__} — Zustand", True, _TITLE
        )
        surface.blit(heading, (self._rect.left + 8, self._rect.top + 5))

        veraenderbar = self.editable()
        for index, (name, value) in enumerate(rows):
            zeile = self.row_rect(index)
            offen = name in veraenderbar
            if offen and name == self._hover:
                pygame.draw.rect(surface, _HOVER, zeile, border_radius=3)

            top = zeile.top + 1
            label = font.render(name, True, _EDITABLE if offen else _HINT)
            surface.blit(label, (self._rect.left + 10, top))
            # Der Wert steht rechts; er darf die Beschriftung nicht ueberlaufen.
            room = self._rect.width - 28 - label.get_width()
            shown = font.render(
                _shortened(font, value, room), True, _EDITABLE if offen else _LABEL
            )
            surface.blit(
                shown, shown.get_rect(topright=(self._rect.right - 10, top))
            )

        hinweis = (
            "Farbige Werte lassen sich ändern"
            if veraenderbar
            else "Esc oder Klick schließt"
        )
        footer = small.render(hinweis, True, _LABEL_DISABLED)
        surface.blit(footer, (self._rect.left + 8, self._rect.bottom - 16))

    def __repr__(self) -> str:
        return f"Inspector(target={type(self._target).__name__})"
