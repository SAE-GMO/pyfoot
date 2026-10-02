"""Die Bedienleiste unterhalb der Welt.

Setzt die Anforderungen C1 bis C4 des Editor-Anforderungsdokuments um: Jede
Funktion ist als Schaltflaeche mit der Maus **und** ueber die Tastatur
erreichbar. Die Tastenbelegung steht im Fenster.

Die Leiste zeichnet sich selbst mit pygame; es kommt keine Abhaengigkeit
hinzu (Editor-Anforderungsdokument 2.2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

if TYPE_CHECKING:
    from ..engine import Engine

__all__ = ["Button", "ControlPanel"]

#: Farben der Leiste. Bewusst dunkel gehalten, damit sie sich von der Welt
#: absetzt, ohne im Unterricht zu blenden.
_BACKGROUND = (26, 29, 38)
_SEPARATOR = (60, 66, 82)
_LABEL = (226, 230, 238)
_HINT = (128, 136, 152)
_BUTTON = (52, 58, 74)
_BUTTON_HOVER = (72, 80, 102)
_BUTTON_ACTIVE = (58, 118, 178)
_BUTTON_DISABLED = (38, 42, 54)
_LABEL_DISABLED = (96, 102, 116)
_WARNING = (240, 176, 96)
#: Gelungenes wird gruen gemeldet, Fehlgeschlagenes rot (Anforderung C8).
_SUCCESS = (126, 214, 150)
_ERROR = (240, 130, 130)

#: Farbe je Art der Rueckmeldung; alles Uebrige bleibt unauffaellig.
STATUS_COLORS: dict[str, tuple[int, int, int]] = {
    "success": _SUCCESS,
    "warning": _WARNING,
    "error": _ERROR,
    "info": _HINT,
}


class Button:
    """Eine Schaltflaeche der Bedienleiste."""

    __slots__ = ("_action", "_label", "_key_hint", "_keys", "_rect")

    def __init__(
        self,
        action: str,
        label: str,
        key_hint: str,
        keys: tuple[int, ...],
        rect: pygame.Rect,
    ) -> None:
        """Erzeugt eine Schaltflaeche.

        Args:
            action: Name der ausgeloesten Funktion.
            label: Beschriftung im Fenster.
            key_hint: Anzeige der Taste, etwa 'Leer'.
            keys: Tastencodes, die dieselbe Funktion ausloesen.
            rect: Lage und Groesse im Fenster.
        """
        self._action = action
        self._label = label
        self._key_hint = key_hint
        self._keys = keys
        self._rect = rect

    @property
    def action(self) -> str:
        """Name der ausgeloesten Funktion."""
        return self._action

    @property
    def label(self) -> str:
        """Beschriftung im Fenster."""
        return self._label

    @property
    def key_hint(self) -> str:
        """Anzeige der zugehoerigen Taste."""
        return self._key_hint

    @property
    def keys(self) -> tuple[int, ...]:
        """Tastencodes, die dieselbe Funktion ausloesen."""
        return self._keys

    @property
    def rect(self) -> pygame.Rect:
        """Lage und Groesse im Fenster."""
        return self._rect

    def __repr__(self) -> str:
        return f"Button(action={self._action!r}, label={self._label!r})"


class ControlPanel:
    """Zeichnet die Bedienleiste und wertet ihre Ereignisse aus."""

    __slots__ = (
        "_engine",
        "_buttons",
        "_slider",
        "_width",
        "_hover",
        "_dragging_slider",
        "_font",
        "_small_font",
    )

    #: Hoehe der Leiste in Bildpunkten. Die unterste Zeile traegt die
    #: Rueckmeldungen der Oberflaeche, etwa das Ergebnis des Sicherns.
    HEIGHT: int = 82

    #: Kleinste Fensterbreite, damit alle Schaltflaechen nebeneinander passen.
    MIN_WIDTH: int = 640

    #: Schrittdauern von langsam nach schnell. Der Regler waehlt daraus aus.
    SPEED_STEPS: tuple[float, ...] = (
        1.0,
        0.7,
        0.5,
        0.35,
        0.25,
        0.15,
        0.1,
        0.06,
        0.03,
        0.0,
    )

    def __init__(self, engine: Engine, width: int) -> None:
        """Legt die Leiste fuer ein Fenster der angegebenen Breite an."""
        self._engine = engine
        self._width = width
        self._hover: str | None = None
        self._dragging_slider = False
        self._font: pygame.font.Font | None = None
        self._small_font: pygame.font.Font | None = None
        self._buttons: list[Button] = []
        self._slider = pygame.Rect(0, 0, 0, 0)
        self._layout(width)

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------

    def _layout(self, width: int) -> None:
        """Berechnet die Lage aller Bedienelemente.

        Die Rechtecke sind auf die Leiste bezogen, nicht auf das Fenster.
        """
        self._width = width
        top = 10
        height = 26
        left = 10
        gap = 6

        # Die Beschriftungen erscheinen im Fenster und sind deshalb -- anders
        # als Bezeichner und Kommentare -- in richtigem Deutsch gehalten.
        specs: list[tuple[str, str, str, tuple[int, ...], int]] = [
            ("play", "Start", "Leer", (pygame.K_SPACE,), 74),
            ("cycle", "Durchlauf", "D", (pygame.K_d,), 92),
            ("step", "Schritt", "S", (pygame.K_s,), 78),
            ("reset", "Zurücksetzen", "R", (pygame.K_r,), 118),
        ]

        self._buttons = []
        for action, label, key_hint, keys, button_width in specs:
            rect = pygame.Rect(left, top, button_width, height)
            self._buttons.append(Button(action, label, key_hint, keys, rect))
            left += button_width + gap

        # Der Geschwindigkeitsregler nimmt den restlichen Platz ein. Rechts
        # bleibt Raum fuer die Zustandsanzeige.
        slider_left = left + 58  # Platz fuer die Beschriftung
        slider_width = max(80, width - slider_left - 96)
        self._slider = pygame.Rect(slider_left, top + 8, slider_width, 10)

    def resize(self, width: int) -> None:
        """Passt die Leiste an eine neue Fensterbreite an."""
        self._layout(width)

    @property
    def buttons(self) -> list[Button]:
        """Die Schaltflaechen der Leiste."""
        return list(self._buttons)

    @property
    def slider(self) -> pygame.Rect:
        """Lage des Geschwindigkeitsreglers innerhalb der Leiste."""
        return self._slider

    def button(self, action: str) -> Button:
        """Liefert die Schaltflaeche zu einer Funktion.

        Raises:
            KeyError: Wenn es keine Schaltflaeche dieses Namens gibt.
        """
        for candidate in self._buttons:
            if candidate.action == action:
                return candidate
        raise KeyError(f"Keine Schaltflaeche mit dem Namen '{action}'.")

    # ------------------------------------------------------------------
    # Zustand
    # ------------------------------------------------------------------

    def _actions(self) -> dict[str, Callable[[], None]]:
        """Ordnet jedem Namen die auszufuehrende Funktion zu."""
        engine = self._engine
        return {
            "play": engine.toggle_pause,
            "cycle": engine.request_cycle,
            "step": engine.request_step,
            "reset": engine.request_reset,
        }

    def is_enabled(self, action: str) -> bool:
        """Gibt an, ob eine Funktion im aktuellen Zustand etwas bewirkt.

        Anforderung C4: Im Fenster muss erkennbar sein, welches Bedienelement
        gerade greift. `Durchlauf` und `Schritt` setzen eine angehaltene
        Simulation voraus.
        """
        engine = self._engine
        if action in ("cycle", "step"):
            return engine.is_paused()
        return True

    def label_for(self, action: str) -> str:
        """Liefert die aktuelle Beschriftung einer Schaltflaeche."""
        if action == "play":
            return "Start" if self._engine.is_paused() else "Pause"
        return self.button(action).label

    def speed_index(self) -> int:
        """Liefert die Stufe, die der eingestellten Schrittdauer entspricht."""
        duration = self._engine.step_duration
        distances = [abs(step - duration) for step in ControlPanel.SPEED_STEPS]
        return distances.index(min(distances))

    def set_speed_index(self, index: int) -> None:
        """Stellt die Schrittdauer auf die angegebene Stufe."""
        steps = ControlPanel.SPEED_STEPS
        bounded = max(0, min(len(steps) - 1, index))
        self._engine.step_duration = steps[bounded]

    def _speed_from_position(self, x: int) -> int:
        """Rechnet eine Position auf dem Regler in eine Stufe um."""
        steps = len(ControlPanel.SPEED_STEPS)
        relative = (x - self._slider.left) / max(1, self._slider.width)
        return max(0, min(steps - 1, int(relative * steps)))

    # ------------------------------------------------------------------
    # Ereignisse
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event, offset_y: int) -> bool:
        """Wertet ein Fensterereignis aus.

        Args:
            event: Das Ereignis.
            offset_y: Obere Kante der Leiste im Fenster.

        Returns:
            True, wenn das Ereignis zur Leiste gehoerte und verbraucht wurde.
        """
        if event.type == pygame.KEYDOWN:
            return self._handle_key(event.key)
        if event.type in (
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
        ):
            return self._handle_mouse(event, offset_y)
        return False

    def _handle_key(self, key: int) -> bool:
        """Fuehrt die Funktion aus, die zu einer Taste gehoert."""
        if key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_PAGEUP):
            self.set_speed_index(self.speed_index() + 1)
            return True
        if key in (pygame.K_MINUS, pygame.K_KP_MINUS, pygame.K_PAGEDOWN):
            self.set_speed_index(self.speed_index() - 1)
            return True

        for candidate in self._buttons:
            if key in candidate.keys:
                if not self.is_enabled(candidate.action):
                    return True
                self._actions()[candidate.action]()
                return True
        return False

    def _handle_mouse(self, event: pygame.event.Event, offset_y: int) -> bool:
        """Wertet Mausereignisse innerhalb der Leiste aus."""
        position: tuple[int, int] = event.pos
        local = (int(position[0]), int(position[1]) - offset_y)
        inside: bool = 0 <= local[1] < ControlPanel.HEIGHT

        if event.type == pygame.MOUSEBUTTONUP:
            was_dragging = self._dragging_slider
            self._dragging_slider = False
            return was_dragging or inside

        if event.type == pygame.MOUSEMOTION:
            if self._dragging_slider:
                self.set_speed_index(self._speed_from_position(local[0]))
                return True
            self._hover = self._action_at(local) if inside else None
            return inside

        if not inside:
            return False

        # Der Griffbereich des Reglers ist grosszuegiger als seine Zeichnung,
        # damit er sich auch am Beamer treffen laesst.
        if self._slider.inflate(0, 16).collidepoint(local):
            self._dragging_slider = True
            self.set_speed_index(self._speed_from_position(local[0]))
            return True

        action = self._action_at(local)
        if action is not None and self.is_enabled(action):
            self._actions()[action]()
        return True

    def _action_at(self, local: tuple[int, int]) -> str | None:
        """Liefert die Funktion, die an dieser Stelle liegt."""
        for candidate in self._buttons:
            if candidate.rect.collidepoint(local):
                return candidate.action
        return None

    # ------------------------------------------------------------------
    # Zeichnen
    # ------------------------------------------------------------------

    def _ensure_fonts(self) -> None:
        """Legt die Schriften an, sobald zum ersten Mal gezeichnet wird."""
        if self._font is not None:
            return
        if not pygame.font.get_init():
            pygame.font.init()
        self._font = pygame.font.Font(None, 22)
        self._small_font = pygame.font.Font(None, 17)

    def render(self, surface: pygame.Surface) -> None:
        """Zeichnet die Leiste auf die uebergebene Flaeche."""
        self._ensure_fonts()
        font = self._font
        small = self._small_font
        if font is None or small is None:
            return

        surface.fill(_BACKGROUND)
        pygame.draw.line(surface, _SEPARATOR, (0, 0), (surface.get_width(), 0))

        for candidate in self._buttons:
            self._render_button(surface, candidate, font, small)

        self._render_slider(surface, font, small)
        self._render_state(surface, small)
        self._render_status(surface, small)

    def _render_button(
        self,
        surface: pygame.Surface,
        button: Button,
        font: pygame.font.Font,
        small: pygame.font.Font,
    ) -> None:
        """Zeichnet eine einzelne Schaltflaeche samt Tastenhinweis."""
        enabled = self.is_enabled(button.action)
        if not enabled:
            background = _BUTTON_DISABLED
        elif button.action == "play" and not self._engine.is_paused():
            background = _BUTTON_ACTIVE
        elif self._hover == button.action:
            background = _BUTTON_HOVER
        else:
            background = _BUTTON

        pygame.draw.rect(surface, background, button.rect, border_radius=4)
        pygame.draw.rect(surface, _SEPARATOR, button.rect, width=1, border_radius=4)

        color = _LABEL if enabled else _LABEL_DISABLED
        text = font.render(self.label_for(button.action), True, color)
        surface.blit(text, text.get_rect(center=button.rect.center))

        hint = small.render(button.key_hint, True, _HINT if enabled else _LABEL_DISABLED)
        surface.blit(hint, hint.get_rect(midtop=(button.rect.centerx, button.rect.bottom + 3)))

    def _render_slider(
        self, surface: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font
    ) -> None:
        """Zeichnet den Geschwindigkeitsregler."""
        label = font.render("Tempo", True, _LABEL)
        surface.blit(label, label.get_rect(midright=(self._slider.left - 10, self._slider.centery)))

        pygame.draw.rect(surface, _BUTTON, self._slider, border_radius=5)
        steps = len(ControlPanel.SPEED_STEPS)
        index = self.speed_index()
        filled = pygame.Rect(
            self._slider.left,
            self._slider.top,
            int(self._slider.width * (index + 1) / steps),
            self._slider.height,
        )
        pygame.draw.rect(surface, _BUTTON_ACTIVE, filled, border_radius=5)

        knob_x = self._slider.left + int(self._slider.width * (index + 0.5) / steps)
        pygame.draw.circle(surface, _LABEL, (knob_x, self._slider.centery), 7)

        hint = small.render("+ / -", True, _HINT)
        surface.blit(hint, hint.get_rect(midtop=(self._slider.centerx, self._slider.bottom + 6)))

    def _render_state(self, surface: pygame.Surface, small: pygame.font.Font) -> None:
        """Zeigt an, ob die Simulation laeuft oder angehalten ist."""
        state = "angehalten" if self._engine.is_paused() else "läuft"
        color = _HINT if self._engine.is_paused() else _LABEL
        text = small.render(state, True, color)
        surface.blit(
            text, text.get_rect(midright=(surface.get_width() - 12, self._slider.centery))
        )

    def _render_status(self, surface: pygame.Surface, small: pygame.font.Font) -> None:
        """Zeigt die letzte Rueckmeldung der Oberflaeche an.

        Hier landet vor allem das Ergebnis des Sicherns. Gelungenes steht
        **gruen** und mit einem Haken davor (Anforderung C8): Ohne sichtbare
        Bestaetigung wurde `Welt sichern` mehrfach gedrueckt, weil nicht
        erkennbar war, ob es geklappt hat.
        """
        message = self._engine.status
        if not message:
            return
        kind = self._engine.status_kind
        color = STATUS_COLORS.get(kind, _HINT)
        left = 12
        top = ControlPanel.HEIGHT - 20

        if kind == "success":
            # Ein Haken aus zwei Strichen -- gezeichnet, nicht geschrieben:
            # Die eingebaute Schrift kennt das Hakenzeichen nicht.
            pygame.draw.lines(
                surface,
                color,
                False,
                [(left, top + 7), (left + 4, top + 11), (left + 11, top + 2)],
                width=2,
            )
            left += 18

        # Lange Meldungen -- etwa ein Fehler samt Dateiname -- duerfen nicht
        # aus der Leiste herauslaufen.
        from .menu import _shortened

        gekuerzt = _shortened(small, message, surface.get_width() - left - 12)
        surface.blit(small.render(gekuerzt, True, color), (left, top))

    def __repr__(self) -> str:
        return f"ControlPanel(width={self._width}, buttons={len(self._buttons)})"
