"""Fehler im laufenden Programm melden, ohne das Fenster zu beenden.

Setzt die Anforderungen H1 bis H6 des Editor-Anforderungsdokuments um. Ein
Fehler im Schuelercode -- ein Raumschiff fliegt aus der Welt, ein Name ist
vertippt, ein Index zu gross -- beendete bisher das ganze Programm. Jetzt
haelt die Oberflaeche an und zeigt ein Fehlerfenster:

    Fehler mitten im Lauf: SpaceshipError
    NormalSpaceship wollte von (8, 5) nach (9, 5) fliegen, ...
    ships/normal_spaceship.py, Zeile 23
        self.move()
    [Zur Zeile  E]   [Zuruecksetzen  R]   [Schliessen  Esc]

Alle Fehler werden gleich behandelt, gleich woher sie stammen (H2). Die
Ueberschriften folgen dem Arbeitsblatt zu den Fehlertypen: Ein Fehler faellt
entweder **vor dem Start** auf oder **mitten im Lauf**.

Gezeigt wird die Zeile im **eigenen** Code, nicht die in der Bibliothek, in
der der Fehler technisch ausgeloest wurde (H3). Eigener Code ist, was in den
ueber `set_class_folders` angemeldeten Ordnern liegt.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Callable, NamedTuple

import pygame

__all__ = [
    "ErrorPanel",
    "ErrorReport",
    "HINTS",
    "describe",
    "hint_for",
    "install_error_hook",
    "summary_text",
]

_BACKGROUND = (40, 30, 36)
_BORDER = (196, 84, 92)
_TITLE = (240, 150, 150)
_LABEL = (226, 230, 238)
_HINT = (150, 158, 176)
_CODE_BACKGROUND = (22, 20, 26)
_CODE = (240, 210, 140)
_BUTTON = (58, 52, 64)
_BUTTON_HOVER = (86, 76, 94)
_BUTTON_DISABLED = (44, 40, 48)
_LABEL_DISABLED = (110, 104, 116)

#: Ein Satz auf Deutsch zu den haeufigen Python-Fehlern (H4). Gesucht wird
#: entlang der Vererbung: `UnboundLocalError` bekommt seinen eigenen Satz,
#: nicht den von `NameError`. Eigene Fehlerklassen mit deutscher Meldung --
#: etwa die eines Raumschiffs -- brauchen keinen und bekommen keinen, solange
#: sie nicht von einer der hier genannten Klassen erben.
HINTS: dict[type[BaseException], str] = {
    IndentationError: (
        "Die Einrückung stimmt nicht: Alle Zeilen eines Blocks "
        "müssen gleich weit eingerückt sein."
    ),
    SyntaxError: (
        "Python kann diese Zeile nicht lesen. Fehlt eine Klammer, "
        "ein Doppelpunkt oder ein Anführungszeichen?"
    ),
    UnboundLocalError: "Die Variable wird benutzt, bevor sie einen Wert bekommen hat.",
    NameError: (
        "Diesen Namen kennt Python an dieser Stelle nicht. "
        "Tippfehler? Fehlt ein Import?"
    ),
    AttributeError: (
        "Das Objekt hat kein Attribut und keine Methode dieses Namens. "
        "Tippfehler? Oder ist die Methode noch nicht geschrieben?"
    ),
    TypeError: (
        "Ein Wert hat den falschen Typ, oder die Anzahl der Werte "
        "beim Aufruf stimmt nicht."
    ),
    ZeroDivisionError: "Es wurde durch 0 geteilt.",
    IndexError: (
        "Diese Stelle gibt es nicht. Gezählt wird ab 0; "
        "die letzte Stelle ist len(...) - 1."
    ),
    KeyError: "Diesen Schlüssel gibt es nicht.",
    ValueError: "Der Typ passt, aber der Wert nicht.",
    RecursionError: "Eine Methode ruft sich immer wieder selbst auf.",
    NotImplementedError: "Diese Methode ist noch nicht geschrieben.",
    ModuleNotFoundError: "Dieses Modul gibt es nicht. Stimmt der Name im Import?",
    ImportError: "Der Import klappt nicht. Stimmt der Name der Klasse?",
    FileNotFoundError: "Diese Datei gibt es nicht.",
}


class ErrorReport(NamedTuple):
    """Alles, was zu einem Fehler angezeigt wird."""

    title: str
    name: str
    message: str
    hint: str
    file: Path | None
    line: int | None
    code: str

    def location(self) -> str:
        """Die Fundstelle als `datei, Zeile n` -- leer, wenn es keine gibt."""
        if self.file is None:
            return ""
        return f"{_shown_path(self.file)}, Zeile {self.line}"


def hint_for(error: BaseException) -> str:
    """Liefert den erklaerenden Satz zu einem Fehler; leer, wenn es keinen gibt."""
    for cls in type(error).__mro__:
        if cls in HINTS:
            return HINTS[cls]
    return ""


def _shown_path(path: Path) -> str:
    """Kuerzt einen Pfad auf den Teil ab dem Arbeitsverzeichnis."""
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


def _resolved(filename: str) -> Path | None:
    """Liefert den Pfad zu einem Dateinamen aus der Aufrufkette."""
    if not filename or filename.startswith("<"):
        return None
    try:
        path = Path(filename).resolve()
    except OSError:  # pragma: no cover -- exotische Dateinamen
        return None
    return path if path.is_file() else None


def _own_folders() -> list[Path]:
    """Die Ordner, in denen eigener Code liegt (angemeldet ueber `set_class_folders`)."""
    from .codegen import class_folders

    return [folder.resolve() for folder in class_folders() if folder is not None]


def _library_folders() -> list[Path]:
    """Ordner, deren Zeilen nie als Fundstelle taugen: PyFoot und Python selbst."""
    folders = [Path(__file__).resolve().parent.parent]
    for prefix in {sys.prefix, sys.base_prefix, sys.exec_prefix}:
        folders.append(Path(prefix).resolve())
    return folders


def _inside(path: Path, folders: list[Path]) -> bool:
    """Gibt an, ob die Datei in einem der Ordner liegt."""
    return any(folder == path.parent or folder in path.parents for folder in folders)


def _location(error: BaseException) -> tuple[Path | None, int | None, str]:
    """Sucht die Stelle im eigenen Code, an der der Fehler entstand (H3).

    Reihenfolge:

    1. Ein Syntaxfehler traegt Datei und Zeile selbst -- er entsteht, bevor
       die Datei ueberhaupt laeuft, und steht deshalb in keiner Aufrufkette.
    2. Die **letzte** Zeile der Aufrufkette, die in einem angemeldeten Ordner
       fuer eigene Klassen liegt. Ein `SpaceshipError` wird in der Bibliothek
       ausgeloest -- gemeint ist aber die Zeile mit `self.move()`.
    3. Sonst die letzte Zeile ausserhalb von PyFoot und Python selbst.
    """
    if isinstance(error, SyntaxError):
        path = _resolved(error.filename or "")
        if path is not None:
            return path, error.lineno, (error.text or "").strip()

    frames = traceback.extract_tb(error.__traceback__)
    candidates = [(frame, _resolved(frame.filename)) for frame in frames]
    own = _own_folders()
    library = _library_folders()

    for frame, path in reversed(candidates):
        if path is not None and own and _inside(path, own):
            return path, frame.lineno, (frame.line or "").strip()
    for frame, path in reversed(candidates):
        if path is not None and not _inside(path, library):
            return path, frame.lineno, (frame.line or "").strip()
    return None, None, ""


def describe(error: BaseException) -> ErrorReport:
    """Bereitet einen Fehler fuer Fehlerfenster und Konsole auf."""
    before_start = isinstance(error, SyntaxError)
    message = (error.msg if isinstance(error, SyntaxError) else str(error)) or ""
    file, line, code = _location(error)
    return ErrorReport(
        title="Fehler vor dem Start" if before_start else "Fehler mitten im Lauf",
        name=type(error).__name__,
        message=message,
        hint=hint_for(error),
        file=file,
        line=line,
        code=code,
    )


def summary_text(report: ErrorReport) -> str:
    """Die Zusammenfassung fuer die Konsole (H5).

    Die Fundstelle steht als `datei:zeile` in einer eigenen Zeile. VS Code
    macht daraus im Terminal einen Verweis, der sich mit Strg+Klick oeffnet.
    """
    rule = "=" * 70
    lines = [rule, f"{report.title}: {report.name}"]
    if report.message:
        lines.append(report.message)
    if report.hint:
        lines.append(f"Hinweis: {report.hint}")
    if report.file is not None:
        lines.append("")
        lines.append(f"Stelle: {_shown_path(report.file)}:{report.line}")
        if report.code:
            lines.append(f"    {report.code}")
    lines.append(rule)
    return "\n".join(lines)


_hook_installed = False


def install_error_hook() -> None:
    """Ergaenzt die Fehlerausgabe von Python um die Zusammenfassung (H6).

    Gedacht fuer Fehler, die das Programm beenden -- vor allem beim Start,
    solange noch kein Fenster offen ist. Die gewohnte Ausgabe von Python
    bleibt vollstaendig erhalten; die Zusammenfassung folgt darunter, weil
    die unterste Zeile die ist, die man zuerst liest.
    """
    global _hook_installed
    if _hook_installed:
        return
    previous = sys.excepthook

    def hook(
        kind: type[BaseException], error: BaseException, trace: object
    ) -> None:
        previous(kind, error, trace)  # type: ignore[arg-type]
        if not isinstance(error, Exception):
            return  # Strg+C und Programmende sind keine Fehler.
        try:
            print(summary_text(describe(error)), file=sys.stderr)
        except Exception:  # pragma: no cover -- die Ausgabe darf nie selbst scheitern
            pass

    sys.excepthook = hook
    _hook_installed = True


def _wrapped(font: pygame.font.Font, text: str, room: int) -> list[str]:
    """Bricht einen Text an Wortgrenzen so um, dass jede Zeile passt."""
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for word in paragraph.split(" "):
            candidate = f"{current} {word}" if current else word
            if current and font.size(candidate)[0] > room:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


class ErrorPanel:
    """Das Fehlerfenster ueber der Welt (H1).

    Solange es offen ist, bekommt es **alle** Eingaben: Ein Tastendruck auf
    `Leertaste` soll nicht versehentlich weiterlaufen lassen, was gerade
    gescheitert ist. Die drei Befehle sind mit der Maus und ueber die Tastatur
    erreichbar (C1, C2).
    """

    __slots__ = (
        "_report",
        "_on_open",
        "_on_reset",
        "_rect",
        "_font",
        "_small",
        "_code_font",
        "_lines",
        "_buttons",
        "_hover",
    )

    #: Groesste Breite in Bildpunkten.
    MAX_WIDTH: int = 560

    #: Abstand zum Fensterrand.
    MARGIN: int = 20

    #: Zeilenhoehe des Fliesstexts.
    LINE_HEIGHT: int = 20

    #: Hoehe einer Schaltflaeche.
    BUTTON_HEIGHT: int = 28

    def __init__(
        self,
        report: ErrorReport,
        on_open: Callable[[], None],
        on_reset: Callable[[], None],
    ) -> None:
        """Erzeugt das Fehlerfenster.

        Args:
            report: Der aufbereitete Fehler.
            on_open: Oeffnet die Fundstelle im Editor.
            on_reset: Setzt die Welt zurueck.
        """
        self._report = report
        self._on_open = on_open
        self._on_reset = on_reset
        self._rect = pygame.Rect(0, 0, ErrorPanel.MAX_WIDTH, 160)
        self._font: pygame.font.Font | None = None
        self._small: pygame.font.Font | None = None
        self._code_font: pygame.font.Font | None = None
        self._lines: list[tuple[str, str]] = []
        self._buttons: list[tuple[str, str, str, pygame.Rect]] = []
        self._hover: str | None = None

    @property
    def report(self) -> ErrorReport:
        """Der angezeigte Fehler."""
        return self._report

    @property
    def rect(self) -> pygame.Rect:
        """Lage und Groesse im Fenster."""
        return self._rect

    def can_open(self) -> bool:
        """Gibt an, ob es eine Fundstelle gibt, die sich oeffnen laesst."""
        return self._report.file is not None

    def button_rect(self, action: str) -> pygame.Rect:
        """Liefert die Lage einer Schaltflaeche (`open`, `reset`, `close`).

        Raises:
            KeyError: Wenn es keine Schaltflaeche dieses Namens gibt.
        """
        for name, _, _, rect in self._buttons:
            if name == action:
                return rect
        raise KeyError(f"Keine Schaltflaeche mit dem Namen '{action}'.")

    def _ensure_fonts(self) -> None:
        """Legt die Schriften an."""
        if self._font is not None:
            return
        if not pygame.font.get_init():
            pygame.font.init()
        self._font = pygame.font.Font(None, 22)
        self._small = pygame.font.Font(None, 17)
        self._code_font = pygame.font.Font(None, 19)

    def center_in(self, width: int, height: int) -> None:
        """Berechnet Umbruch und Groesse und stellt das Fenster mittig."""
        self._ensure_fonts()
        font, small = self._font, self._small
        if font is None or small is None:  # pragma: no cover -- Schriften fehlen
            return

        panel_width = max(260, min(ErrorPanel.MAX_WIDTH, width - 2 * ErrorPanel.MARGIN))
        room = panel_width - 24
        report = self._report

        lines: list[tuple[str, str]] = []
        lines.extend(("message", text) for text in _wrapped(font, report.message, room))
        if report.hint:
            lines.extend(("hint", text) for text in _wrapped(small, report.hint, room))
        if report.file is not None:
            lines.append(("gap", ""))
            lines.append(("location", report.location()))
            if report.code:
                lines.append(("code", report.code))
        self._lines = lines

        body = len(lines) * ErrorPanel.LINE_HEIGHT
        panel_height = 34 + body + 16 + ErrorPanel.BUTTON_HEIGHT + 14
        self._rect = pygame.Rect(0, 0, panel_width, panel_height)
        self._rect.center = (width // 2, height // 2)
        self._rect.top = max(0, self._rect.top)

        specs = [
            ("open", "Zur Zeile", "E"),
            ("reset", "Zurücksetzen", "R"),
            ("close", "Schließen", "Esc"),
        ]
        gap = 8
        button_width = (panel_width - 24 - gap * (len(specs) - 1)) // len(specs)
        top = self._rect.bottom - 14 - ErrorPanel.BUTTON_HEIGHT
        self._buttons = []
        for index, (action, label, key) in enumerate(specs):
            rect = pygame.Rect(
                self._rect.left + 12 + index * (button_width + gap),
                top,
                button_width,
                ErrorPanel.BUTTON_HEIGHT,
            )
            self._buttons.append((action, label, key, rect))

    def choose(self, action: str) -> bool:
        """Fuehrt einen Befehl aus.

        Returns:
            True, wenn das Fehlerfenster danach geschlossen wird.
        """
        if action == "open":
            if self.can_open():
                self._on_open()
            return False
        if action == "reset":
            self._on_reset()
            return True
        return action == "close"

    def _action_at(self, position: tuple[int, int]) -> str | None:
        """Liefert den Befehl an dieser Stelle."""
        for action, _, _, rect in self._buttons:
            if rect.collidepoint(position):
                return action
        return None

    def handle_event(self, event: pygame.event.Event) -> tuple[bool, bool]:
        """Wertet ein Ereignis aus.

        Returns:
            Ein Paar aus `verbraucht` und `schliessen`.
        """
        if not self._buttons:
            self.center_in(ErrorPanel.MAX_WIDTH + 2 * ErrorPanel.MARGIN, 400)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return True, True
            if event.key == pygame.K_e:
                return True, self.choose("open")
            if event.key == pygame.K_r:
                return True, self.choose("reset")
            return True, False

        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            spot: tuple[int, int] = event.pos
            point = (int(spot[0]), int(spot[1]))
            action = self._action_at(point)
            if event.type == pygame.MOUSEMOTION:
                self._hover = action
                return True, False
            if action is not None:
                return True, self.choose(action)
            return True, False

        if event.type == pygame.MOUSEBUTTONUP:
            return True, False
        return False, False

    def render(self, surface: pygame.Surface) -> None:
        """Zeichnet das Fehlerfenster."""
        if not self._buttons:
            self.center_in(surface.get_width(), surface.get_height())
        font, small, code_font = self._font, self._small, self._code_font
        if font is None or small is None or code_font is None:  # pragma: no cover
            return

        pygame.draw.rect(surface, _BACKGROUND, self._rect, border_radius=6)
        pygame.draw.rect(surface, _BORDER, self._rect, width=2, border_radius=6)

        heading = font.render(
            f"{self._report.title}: {self._report.name}", True, _TITLE
        )
        surface.blit(heading, (self._rect.left + 12, self._rect.top + 10))

        top = self._rect.top + 34
        for kind, text in self._lines:
            if kind == "code":
                strip = pygame.Rect(
                    self._rect.left + 10, top - 1, self._rect.width - 20, ErrorPanel.LINE_HEIGHT
                )
                pygame.draw.rect(surface, _CODE_BACKGROUND, strip, border_radius=3)
                shown = code_font.render(text, True, _CODE)
                surface.blit(shown, (self._rect.left + 22, top + 2))
            elif kind != "gap":
                chosen = font if kind == "message" else small
                color = _LABEL if kind in ("message", "location") else _HINT
                surface.blit(chosen.render(text, True, color), (self._rect.left + 12, top + 2))
            top += ErrorPanel.LINE_HEIGHT

        for action, label, key, rect in self._buttons:
            enabled = action != "open" or self.can_open()
            if not enabled:
                background = _BUTTON_DISABLED
            elif self._hover == action:
                background = _BUTTON_HOVER
            else:
                background = _BUTTON
            pygame.draw.rect(surface, background, rect, border_radius=4)
            pygame.draw.rect(surface, _BORDER, rect, width=1, border_radius=4)
            color = _LABEL if enabled else _LABEL_DISABLED
            caption = font.render(label, True, color)
            surface.blit(caption, caption.get_rect(midleft=(rect.left + 10, rect.centery)))
            hint = small.render(key, True, _HINT if enabled else _LABEL_DISABLED)
            surface.blit(hint, hint.get_rect(midright=(rect.right - 8, rect.centery)))

    def __repr__(self) -> str:
        return f"ErrorPanel(name={self._report.name!r}, file={self._report.file!r})"
