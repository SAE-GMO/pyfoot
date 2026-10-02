"""Laufzeitsteuerung von PyFoot.

Hier liegt das Ausfuehrungsmodell (Anforderungsdokument 4.6): PyFoot laeuft
einthreadig. Schuelercode darf blockieren und trotzdem sichtbar ablaufen,
weil jede veraendernde Aktion die Ereignisschleife von innen heraus
weiterdreht -- siehe `redraws` und `Engine.update_screen`.
"""

from __future__ import annotations

import functools
import os
import random
import sys
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterator, ParamSpec, TypeVar

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402  (muss nach der Umgebungsvariable importiert werden)

from .input import InputState  # noqa: E402

if TYPE_CHECKING:
    from .actor import Actor
    from .editor.errors import ErrorPanel, ErrorReport
    from .editor.menu import ContextMenu, Inspector, TextPrompt
    from .editor.reload import SourceSignature
    from .editor.mode import EditMode
    from .editor.panel import ControlPanel
    from .editor.sidebar import ClassSidebar
    from .world import World

__all__ = [
    "Engine",
    "SimulationStopped",
    "SimulationReset",
    "redraws",
    "get_engine",
    "set_world",
    "run",
    "stop",
    "update_screen",
    "random_number",
    "enable_ui",
    "disable_ui",
    "ui_enabled",
]

_P = ParamSpec("_P")
_R = TypeVar("_R")

#: Umgebungsvariable, mit der sich die Oberflaeche einschalten laesst, ohne
#: eine Programmdatei zu aendern -- gedacht fuer den Unterricht.
UI_ENVIRONMENT_VARIABLE = "PYFOOT_UI"


class SimulationStopped(Exception):
    """Wird ausgeloest, wenn das Fenster waehrend laufendem Code geschlossen wird.

    Dadurch bricht auch eine Endlosschleife im Schuelercode zuverlaessig ab,
    ohne dass ein zweiter Thread noetig waere.
    """


class SimulationReset(Exception):
    """Wird ausgeloest, wenn die Welt waehrend laufendem Code zurueckgesetzt wird.

    Sie bricht den laufenden Schuelercode ab, damit die Ausgangslage
    wiederhergestellt und von vorn begonnen werden kann. `Engine.run` faengt
    sie ab; im Kurscode taucht sie nicht auf.
    """


def redraws(method: Callable[_P, _R]) -> Callable[_P, _R]:
    """Kennzeichnet eine Aktion, die den Weltzustand veraendert.

    Nach der Ausfuehrung wird die Ereignisschleife einen Schritt weitergedreht:
    Fensterereignisse werden abgeholt, die Welt wird neu gezeichnet und die
    eingestellte Schrittdauer wird abgewartet. So bleibt das Fenster bedienbar,
    obwohl der Schuelercode blockierend und streng von oben nach unten ablaeuft.

    Der Dekorator wird unmittelbar an der Methodendefinition angebracht --
    nicht zur Laufzeit gesetzt --, damit Typpruefer und Editor ihn sehen.
    """

    @functools.wraps(method)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        result = method(*args, **kwargs)
        Engine.instance().update_screen()
        return result

    return wrapper


def _rebuilder_for(world: World) -> Callable[[], World] | None:
    """Liefert eine Funktion, die eine frische Welt derselben Art baut.

    `Zuruecksetzen` soll den Konstruktor erneut aufrufen: Nur so entstehen
    zufaellige Welten neu gewuerfelt, und nur so ist die Ausgangslage
    wirklich die, die im Quelltext steht.

    Braucht der Konstruktor Werte, laesst sich die Welt nicht blind
    nachbauen. Dann liefert diese Funktion `None`, und `reset` stellt die
    Ausgangslage wie bisher aus der Momentaufnahme wieder her.
    """
    from .editor.mode import can_construct
    from .editor.reload import current_class

    cls = type(world)
    if not can_construct(cls):
        return None

    def bauen() -> World:
        # Die Klasse wird bei jedem Aufruf frisch geholt: Wurde ihre Datei
        # inzwischen geaendert und neu eingebunden, entsteht die Welt aus
        # der neuen Version (Editor-Anforderung H7).
        return current_class(cls)()

    return bauen


def _fits_on_screen(width: int, height: int) -> tuple[int, int]:
    """Begrenzt die Fenstergroesse auf das, was der Bildschirm hergibt.

    Eine Welt von 25 mal 25 Feldern waere 1500 Bildpunkte hoch; das Fenster
    reichte damit unter den Bildschirmrand, und die unteren Reihen waeren
    unerreichbar. Passt es nicht, bleibt das Fenster kleiner -- der Rest der
    Welt ist ueber die Bildlaufleisten erreichbar (C7).
    """
    try:
        # `get_desktop_sizes` meldet den Bildschirm. `Info()` taugt dafuer
        # nicht: Sobald ein Fenster offen ist, liefert es dessen Groesse --
        # das Fenster wuerde bei jedem Weltwechsel weiter schrumpfen.
        sizes = pygame.display.get_desktop_sizes()
    except pygame.error:  # pragma: no cover -- ohne Bildschirmtreiber
        return width, height
    if not sizes:  # pragma: no cover -- kein Bildschirm gemeldet
        return width, height
    verfuegbar = (int(sizes[0][0]), int(sizes[0][1]))
    if verfuegbar[0] < Engine.MIN_WINDOW_SIZE[0] or verfuegbar[1] < Engine.MIN_WINDOW_SIZE[1]:
        return width, height
    # Etwas Luft fuer Taskleiste und Fensterrahmen.
    return (min(width, verfuegbar[0] - 60), min(height, verfuegbar[1] - 120))


def _thumb(
    track: pygame.Rect, scroll: int, limit: int, view: int, vertical: bool
) -> pygame.Rect:
    """Berechnet den Schieber einer Bildlaufleiste.

    Seine Laenge zeigt, welcher Anteil der Welt zu sehen ist, seine Lage, wo
    dieser Ausschnitt liegt.
    """
    laenge = track.height if vertical else track.width
    welt = view + limit
    groesse = max(24, int(laenge * view / welt)) if welt else laenge
    groesse = min(groesse, laenge)
    versatz = int((laenge - groesse) * scroll / limit) if limit else 0
    if vertical:
        return pygame.Rect(track.left, track.top + versatz, track.width, groesse)
    return pygame.Rect(track.left + versatz, track.top, groesse, track.height)


def _literal_arguments(arguments: str) -> tuple[object, ...]:
    """Liest eine eingetippte Werteliste wie `0.5, True` ein.

    Gelesen werden **nur Literale**: Eingetippter Code wird nicht ausgefuehrt.
    Benutzt sowohl beim Erzeugen eines Akteurs (B6a) als auch beim Anzeigen
    einer Welt mit Wahlmoeglichkeit (B7).

    Raises:
        ValueError: Wenn die Angabe keine Folge von Literalen ist.
    """
    import ast

    if not arguments.strip():
        return ()
    try:
        gelesen = ast.literal_eval(f"({arguments},)")
    except (ValueError, SyntaxError, TypeError) as error:
        raise ValueError(str(error)) from error
    return gelesen if isinstance(gelesen, tuple) else (gelesen,)


class Engine:
    """Fenster, Ereignisschleife und Taktung von PyFoot.

    Es gibt genau eine Instanz; sie wird ueber `Engine.instance()` geholt.
    """

    __slots__ = (
        "_world",
        "_screen",
        "_clock",
        "_running",
        "_started",
        "_fps_limit",
        "_step_duration",
        "_last_step",
        "_in_act_cycle",
        "_title",
        "_input",
        "_ui_enabled",
        "_panel",
        "_paused",
        "_step_requested",
        "_cycle_requested",
        "_reset_requested",
        "_snapshot",
        "_world_factory",
        "_suspended",
        "_sidebar",
        "_edit_mode",
        "_start_actor",
        "_status",
        "_save_confirmed",
        "_menu",
        "_prompt",
        "_inspector",
        "_pending_world",
        "_pending_factory",
        "_delete_confirmed",
        "_user_size",
        "_world_surface",
        "_error_panel",
        "_source_signature",
        "_saved_files",
        "_status_kind",
        "_scroll",
        "_dragging_scrollbar",
    )

    _instance: Engine | None = None

    DEFAULT_FPS_LIMIT: int = 60
    DEFAULT_STEP_DURATION: float = 0.15

    def __init__(self) -> None:
        self._world: World | None = None
        self._screen: pygame.Surface | None = None
        self._clock = pygame.time.Clock()
        self._running: bool = False
        self._started: bool = False
        self._fps_limit: int = Engine.DEFAULT_FPS_LIMIT
        self._step_duration: float = Engine.DEFAULT_STEP_DURATION
        self._last_step: float = 0.0
        self._in_act_cycle: bool = False
        self._title: str = "PyFoot"
        self._input: InputState = InputState()
        # Die Oberflaeche ist abgeschaltet, solange sie nicht ausdruecklich
        # eingeschaltet wird (Editor-Anforderungsdokument F1).
        self._ui_enabled: bool = bool(os.environ.get(UI_ENVIRONMENT_VARIABLE))
        self._panel: ControlPanel | None = None
        self._paused: bool = False
        self._step_requested: bool = False
        self._cycle_requested: bool = False
        self._reset_requested: bool = False
        self._snapshot: list[tuple[Actor, int, int, int]] = []
        self._world_factory: Callable[[], World] | None = None
        # Waehrend des Zuruecksetzens darf sich die Ereignisschleife nicht
        # weiterdrehen: Sonst geriete das Wiederherstellen selbst in die
        # Pause oder in die Wartezeit der Schrittdauer.
        self._suspended: bool = False
        self._sidebar: ClassSidebar | None = None
        self._edit_mode: EditMode | None = None
        self._start_actor: Actor | None = None
        self._status: str = ""
        self._status_kind: str = "info"
        # Ein Sichern, das von Hand geschriebene Struktur verliert, braucht
        # eine zweite Bestaetigung (siehe `request_save`).
        self._save_confirmed: bool = False
        self._menu: ContextMenu | None = None
        self._prompt: TextPrompt | None = None
        self._inspector: Inspector | None = None
        # Eine Welt, die angezeigt werden soll, sobald der laufende Code
        # abgebrochen ist (siehe `switch_world`).
        self._pending_world: World | None = None
        self._pending_factory: Callable[[], World] | None = None
        self._delete_confirmed: type | None = None
        # Sobald das Fenster von Hand veraendert wurde, bleibt es so --
        # auch nach einem Weltwechsel.
        self._user_size: tuple[int, int] | None = None
        self._world_surface: pygame.Surface | None = None
        # Das offene Fehlerfenster (Editor-Anforderung H1).
        self._error_panel: ErrorPanel | None = None
        # Stand der eigenen Dateien beim letzten Einbinden (H7). Er wird beim
        # ersten Setzen einer Welt aufgenommen und nur nach erfolgreichem
        # Neueinbinden fortgeschrieben.
        self._source_signature: SourceSignature | None = None
        # Stand der Dateien, die die Oberflaeche selbst geschrieben hat. Eine
        # so geaenderte Datei gilt beim naechsten Sichern nicht als von Hand
        # bearbeitet.
        self._saved_files: SourceSignature = {}
        # Verschiebung der Welt im Fenster, wenn sie groesser ist als die
        # Flaeche, die ihr bleibt (Anforderung C7).
        self._scroll: tuple[int, int] = (0, 0)
        self._dragging_scrollbar: str | None = None

    @staticmethod
    def instance() -> Engine:
        """Liefert die einzige Engine-Instanz und legt sie bei Bedarf an."""
        if Engine._instance is None:
            Engine._instance = Engine()
        return Engine._instance

    @staticmethod
    def _reset_for_tests() -> None:
        """Verwirft die Instanz. Nur fuer automatisierte Tests gedacht."""
        if Engine._instance is not None and Engine._instance._screen is not None:
            pygame.display.quit()
        Engine._instance = None

    # ------------------------------------------------------------------
    # Welt
    # ------------------------------------------------------------------

    @property
    def world(self) -> World:
        """Die aktuell dargestellte Welt.

        Raises:
            RuntimeError: Wenn noch keine Welt gesetzt wurde.
        """
        if self._world is None:
            raise RuntimeError(
                "Es wurde noch keine Welt gesetzt. Rufe zuerst pyfoot.set_world(world) auf."
            )
        return self._world

    @property
    def has_world(self) -> bool:
        """Gibt an, ob bereits eine Welt gesetzt wurde."""
        return self._world is not None

    def set_world(self, world: World, *, factory: Callable[[], World] | None = None) -> None:
        """Legt die Welt fest, die dargestellt und simuliert wird.

        Args:
            world: Die anzuzeigende Welt.
            factory: Wie sich eine frische Welt derselben Art bauen laesst.
                Ohne Angabe wird der Konstruktor der Klasse genommen, sofern
                er ohne Werte auskommt. `Zuruecksetzen` ruft ihn dann erneut
                auf -- die Welt entsteht also wirklich neu, statt nur die
                Akteure auf ihre Startfelder zurueckzuschieben.
        """
        from .world import World as _World

        if not isinstance(world, _World):
            raise TypeError("set_world erwartet ein Objekt der Klasse World.")
        self._world = world
        self._world_factory = factory if factory is not None else _rebuilder_for(world)
        self._input.cell_size = world.cell_size
        # Eine neue Welt wird von oben links gezeigt.
        self._scroll = (0, 0)
        self._take_snapshot()
        if self._ui_enabled and self._source_signature is None:
            from .editor.reload import source_signature

            self._source_signature = source_signature()
        # Wie in Greenfoot wartet die Oberflaeche auf den Startbefehl. Ohne
        # Oberflaeche laeuft alles wie bisher unmittelbar los.
        self._paused = self._ui_enabled
        self._open_window()

    @property
    def world_factory(self) -> Callable[[], World] | None:
        """Funktion, die eine frische Welt erzeugt.

        Ist sie gesetzt, baut `Zuruecksetzen` die Welt vollstaendig neu auf.
        Ohne Angabe wird die Ausgangslage aus einer Momentaufnahme
        wiederhergestellt (siehe `reset`).
        """
        return self._world_factory

    @world_factory.setter
    def world_factory(self, factory: Callable[[], World] | None) -> None:
        self._world_factory = factory

    # ------------------------------------------------------------------
    # Taktung
    # ------------------------------------------------------------------

    @property
    def step_duration(self) -> float:
        """Dauer eines sichtbaren Schrittes in Sekunden.

        Bestimmt, wie lange nach jeder Aktion gewartet wird, damit der Ablauf
        im Unterricht nachvollziehbar bleibt. 0 schaltet die Verzoegerung ab.
        """
        return self._step_duration

    @step_duration.setter
    def step_duration(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("Die Schrittdauer darf nicht negativ sein.")
        self._step_duration = seconds

    @property
    def fps_limit(self) -> int:
        """Obergrenze der Bildwiederholrate."""
        return self._fps_limit

    @fps_limit.setter
    def fps_limit(self, value: int) -> None:
        if value <= 0:
            raise ValueError("Die Bildrate muss groesser als 0 sein.")
        self._fps_limit = value

    @property
    def title(self) -> str:
        """Der Fenstertitel ohne den Namen der Welt."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = value
        self._update_caption()

    def caption(self) -> str:
        """Liefert die vollstaendige Beschriftung des Fensters.

        An den Titel wird der Name der angezeigten Welt angehaengt. So ist
        jederzeit erkennbar, in welcher Welt man sich befindet -- besonders,
        nachdem die Welt gewechselt wurde.
        """
        if self._world is None:
            return self._title
        return f"{self._title} — {type(self._world).__name__}"

    def _update_caption(self) -> None:
        """Schreibt die Beschriftung in die Titelzeile des Fensters."""
        if self._screen is not None:
            pygame.display.set_caption(self.caption())

    def is_running(self) -> bool:
        """Gibt an, ob die Simulation laeuft."""
        return self._running

    # ------------------------------------------------------------------
    # Eingabe
    # ------------------------------------------------------------------

    @property
    def input(self) -> InputState:
        """Der Zustand von Maus und Tastatur (Anforderungsdokument 4.10.5)."""
        return self._input

    # ------------------------------------------------------------------
    # Oberflaeche
    # ------------------------------------------------------------------

    def enable_ui(self, enabled: bool = True) -> None:
        """Schaltet die Bedienleiste im Fenster ein oder aus.

        Muss vor `set_world` aufgerufen werden, damit das Fenster gleich in
        der passenden Groesse geoeffnet wird.
        """
        self._ui_enabled = enabled
        if not enabled:
            self._panel = None
            self._paused = False
        if self._world is not None:
            self._paused = enabled
            self._open_window()

    @property
    def ui_enabled(self) -> bool:
        """Gibt an, ob die Bedienleiste angezeigt wird."""
        return self._ui_enabled

    @property
    def panel(self) -> ControlPanel | None:
        """Die Bedienleiste, sofern die Oberflaeche eingeschaltet ist."""
        return self._panel

    def is_paused(self) -> bool:
        """Gibt an, ob die Ausfuehrung angehalten ist."""
        return self._paused

    def pause(self) -> None:
        """Haelt die Ausfuehrung an -- auch mitten in einer Anweisungsfolge."""
        self._paused = True

    def resume(self) -> None:
        """Setzt eine angehaltene Ausfuehrung fort."""
        self._paused = False
        self._last_step = time.monotonic()

    def toggle_pause(self) -> None:
        """Wechselt zwischen Anhalten und Fortsetzen."""
        if self._paused:
            self.resume()
        else:
            self.pause()

    def in_act_cycle(self) -> bool:
        """Gibt an, ob gerade ein Act-Durchlauf ausgefuehrt wird.

        Waehrend eines Durchlaufs laeuft Schuelercode; dann greift der
        Einzelschritt. Ausserhalb greift stattdessen `Durchlauf`.
        """
        return self._in_act_cycle

    def request_step(self) -> None:
        """Laesst genau eine Aktion des laufenden Programms zu."""
        self._step_requested = True

    def request_cycle(self) -> None:
        """Fordert genau einen vollstaendigen Act-Durchlauf an."""
        self._cycle_requested = True

    def request_reset(self) -> None:
        """Fordert an, die Ausgangslage wiederherzustellen."""
        self._save_confirmed = False
        self._reset_requested = True

    @property
    def edit_mode(self) -> EditMode | None:
        """Der Bearbeitungsmodus, sofern die Oberflaeche eingeschaltet ist."""
        return self._edit_mode

    @property
    def sidebar(self) -> ClassSidebar | None:
        """Die Klassenanzeige, sofern die Oberflaeche eingeschaltet ist."""
        return self._sidebar

    @property
    def status(self) -> str:
        """Die zuletzt gemeldete Rueckmeldung der Oberflaeche."""
        return self._status

    @status.setter
    def status(self, text: str) -> None:
        self.set_status(text)

    @property
    def status_kind(self) -> str:
        """Art der Rueckmeldung: `info`, `success`, `warning` oder `error`.

        Die Bedienleiste faerbt danach ein. Gelungenes wird **gruen** gemeldet
        (Anforderung C8): Ohne sichtbare Bestaetigung wurde `Welt sichern`
        mehrfach gedrueckt, weil nicht erkennbar war, ob es geklappt hat.
        """
        return self._status_kind

    def set_status(self, text: str, kind: str = "info") -> None:
        """Meldet etwas in der Bedienleiste."""
        self._status = text
        self._status_kind = kind

    @property
    def start_actor(self) -> Actor | None:
        """Der Akteur, der ueber das Klassenmerkmal `START` eingesetzt wurde.

        Er gehoert nicht in den erzeugten Aufbau, sondern wird beim Sichern
        als `START`-Angabe fortgeschrieben (Editor-Anforderungsdokument A5).
        """
        return self._start_actor

    def request_save(self) -> None:
        """Schreibt den aktuellen Weltaufbau als Quelltext in die Weltklasse.

        Zwei Faelle brauchen einen zweiten Druck, der erste warnt nur:

        - Verliert der Vorgang von Hand geschriebene Struktur -- Schleifen,
          Bedingungen, Berechnungen. Aus einer Schleife ueber 25 Felder wird
          eine Liste mit 25 Zeilen; das soll niemandem versehentlich passieren.
        - Wurde die Weltdatei seit dem Laden **von Hand geaendert** (A4c).
          Gesichert wird der Aufbau im Fenster; er kennt die Aenderung nicht und
          wuerde sie ueberschreiben. `Zuruecksetzen` uebernimmt sie stattdessen.
        """
        from .editor import codegen

        if self._world is None:
            self._status = "Es ist keine Welt gesetzt."
            return

        # Ein geloeschtes Startobjekt ist keines mehr: Dann nimmt das Sichern
        # es auch aus dem Konstruktor (A5c).
        start = self._start_actor
        if start is not None and not (start.has_world and start.world is self._world):
            start = None

        try:
            preview = codegen.save_world(self._world, start, dry_run=True)
            warnungen: list[str] = []
            geaendert = self._edited_by_hand(preview.path)
            if geaendert:
                warnungen.append(
                    f"{preview.path.name} wurde von Hand geändert -- R übernimmt die "
                    "Änderung, Sichern überschreibt sie."
                )
            if preview.flattened:
                warnungen.append(
                    f"prepare() enthaelt eigenen Code ({preview.replaced_lines} Zeilen)."
                )
            if warnungen and not self._save_confirmed:
                self._save_confirmed = True
                self.set_status(
                    "Achtung: " + " ".join(warnungen) + " Nochmal druecken zum Ersetzen.",
                    "warning",
                )
                return

            report = codegen.save_world(self._world, start)
        except codegen.SaveError as error:
            self._save_confirmed = False
            self._report_save_error(error)
            return

        from .editor.reload import file_signature

        geschrieben = file_signature(report.path)
        if geschrieben is not None:
            self._saved_files[str(report.path.resolve())] = geschrieben
        self._save_confirmed = False
        self.set_status(report.summary(), "success")

    def _edited_by_hand(self, path: Path) -> bool:
        """Gibt an, ob eine Datei seit dem Laden von aussen geaendert wurde (A4c).

        Was die Oberflaeche selbst geschrieben hat, zaehlt nicht dazu. Dateien
        ausserhalb der eigenen Ordner werden nicht beobachtet.
        """
        from .editor.reload import file_signature

        if self._source_signature is None:
            return False
        key = str(path.resolve())
        geladen = self._source_signature.get(key)
        if geladen is None:
            return False
        jetzt = file_signature(path)
        return jetzt != geladen and jetzt != self._saved_files.get(key)

    # ------------------------------------------------------------------
    # Menue und Eingabe
    # ------------------------------------------------------------------

    @property
    def menu(self) -> ContextMenu | None:
        """Das offene Kontextmenue, sofern eines offen ist."""
        return self._menu

    @property
    def prompt(self) -> TextPrompt | None:
        """Die offene Texteingabe, sofern eine offen ist."""
        return self._prompt

    def open_menu(self, menu: ContextMenu) -> None:
        """Zeigt ein Kontextmenue an und schliesst ein bereits offenes."""
        if self._screen is not None:
            menu.fit_into(self._screen.get_width(), self._screen.get_height())
        self._menu = menu

    def close_menu(self) -> None:
        """Schliesst das Kontextmenue."""
        self._menu = None

    def open_prompt(self, prompt: TextPrompt) -> None:
        """Zeigt eine Texteingabe an."""
        if self._screen is not None:
            prompt.center_in(self._screen.get_width(), self._screen.get_height())
        self._prompt = prompt

    def close_prompt(self) -> None:
        """Schliesst die Texteingabe."""
        self._prompt = None

    def open_class_menu(self, cls: type, position: tuple[int, int]) -> None:
        """Oeffnet das Kontextmenue einer Klasse."""
        from .editor.mode import build_class_menu

        self.open_menu(build_class_menu(self, cls, position))

    def open_actor_menu(self, actor: Actor | None, position: tuple[int, int]) -> None:
        """Oeffnet das Kontextmenue eines Objekts."""
        from .editor.mode import build_actor_menu

        if actor is None:
            return
        self.open_menu(build_actor_menu(self, actor, position))

    def open_image_menu(self, cls: type, position: tuple[int, int]) -> None:
        """Oeffnet die Auswahl der Bilddateien."""
        from .editor.mode import build_image_menu

        self.open_menu(build_image_menu(self, cls, position))

    @property
    def inspector(self) -> Inspector | None:
        """Die offene Zustandsanzeige, sofern eine offen ist."""
        return self._inspector

    def open_inspector(self, target: object, position: tuple[int, int]) -> None:
        """Zeigt den Zustand eines Objekts an (Anforderungen D4 und D5)."""
        from .editor.menu import Inspector as _Inspector

        inspector = _Inspector(
            target, position, on_edit=lambda name: self.ask_for_attribute(target, name)
        )
        if self._screen is not None:
            inspector.fit_into(self._screen.get_width(), self._screen.get_height())
        self._inspector = inspector

    def ask_for_attribute(self, target: object, name: str) -> None:
        """Fragt nach einem neuen Wert fuer ein Attribut (Anforderung D5)."""
        from .editor.menu import TextPrompt

        self.open_prompt(
            TextPrompt(
                f"{name} — neuer Wert:",
                lambda text: self.set_attribute(target, name, text),
                text=repr(getattr(target, name, None)),
            )
        )

    def set_attribute(self, target: object, name: str, text: str) -> None:
        """Setzt ein Attribut auf einen eingegebenen Wert (Anforderung D5).

        Geaendert wird nur, was beim Sichern der Welt auch im Quelltext
        landet, und nur auf einen Wert desselben Typs -- sonst zerbraeche das
        Objekt an einer Stelle, die mit der Eingabe nichts mehr zu tun hat.
        """
        import ast

        from .editor.menu import editable_attributes

        if name not in editable_attributes(target):
            self._status = f"{name} lässt sich nicht ändern."
            return

        try:
            value = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            self._status = f"'{text}' ist kein gültiger Wert."
            return

        alt = getattr(target, name)
        if isinstance(alt, bool) != isinstance(value, bool) or not isinstance(
            value, type(alt) if not isinstance(alt, float) else (int, float)
        ):
            self._status = (
                f"{name} erwartet {type(alt).__name__}, "
                f"nicht {type(value).__name__}."
            )
            return

        try:
            setattr(target, name, value)
        except Exception as error:
            # Eine Eigenschaft darf den Wert pruefen und ablehnen -- etwa eine
            # Wahrscheinlichkeit ausserhalb von 0 bis 1 (H2).
            self.report_error(error)
            return
        self.set_status(f"{name} = {value!r}. Steht beim Sichern im Quelltext.", "success")

    def close_inspector(self) -> None:
        """Schliesst die Zustandsanzeige."""
        self._inspector = None

    # ------------------------------------------------------------------
    # Fehler melden (Editor-Anforderungen H1 bis H6)
    # ------------------------------------------------------------------

    @property
    def error_panel(self) -> ErrorPanel | None:
        """Das offene Fehlerfenster, sofern eines offen ist."""
        return self._error_panel

    def close_error_panel(self) -> None:
        """Schliesst das Fehlerfenster."""
        self._error_panel = None

    def report_error(self, error: BaseException) -> None:
        """Meldet einen Fehler, ohne das Programm zu beenden (H1, H2).

        Die Ausfuehrung haelt an, das Fenster laeuft weiter. Die Welt bleibt,
        wie sie beim Fehler war -- ein Raumschiff steht auf dem letzten
        gueltigen Feld, denn geprueft wird vor dem Schritt. Dieselbe Meldung
        erscheint auf der Konsole (H5).

        Ohne Oberflaeche gibt es kein Fehlerfenster: Dann wird der Fehler
        weitergereicht wie bisher (Auflage F1). Aufgerufen wird die Methode
        deshalb aus einem `except`-Zweig heraus.
        """
        from .editor.errors import ErrorPanel as _ErrorPanel
        from .editor.errors import describe, summary_text

        if not self._ui_enabled:
            raise error

        report = describe(error)
        traceback_text = "".join(traceback.format_exception(error))
        print(traceback_text + summary_text(report), file=sys.stderr)

        self._paused = True
        self._step_requested = False
        self._cycle_requested = False
        self._menu = None
        self._prompt = None

        panel = _ErrorPanel(
            report,
            on_open=lambda: self.open_error_location(report),
            on_reset=self.request_reset,
        )
        if self._screen is not None:
            panel.center_in(self._screen.get_width(), self._screen.get_height())
        self._error_panel = panel
        self.set_status(
            f"{report.name}: {report.message}" if report.message else report.name, "error"
        )

    def open_error_location(self, report: ErrorReport) -> None:
        """Oeffnet die Fundstelle eines Fehlers im Editor (H1)."""
        from .editor.source import open_in_editor

        if report.file is None:
            self._status = "Zu diesem Fehler gibt es keine Stelle im eigenen Code."
            return
        self._status = open_in_editor(report.file, report.line or 1)

    def _report_save_error(self, error: Exception) -> None:
        """Meldet einen Fehler der Quelltextbearbeitung.

        Eine Rueckmeldung wie „Es gibt bereits eine Datei“ ist ein
        Bedienhinweis und gehoert in die Statuszeile. Steckt dagegen ein
        Fehler im eigenen Code dahinter -- die Datei laesst sich nicht lesen
        oder nicht einbinden --, ist es ein Fehler wie jeder andere und
        erscheint im Fehlerfenster (H2).
        """
        cause = error.__cause__
        if isinstance(cause, Exception) and not isinstance(cause, OSError):
            self.report_error(cause)
            return
        self.set_status(str(error), "warning")

    def call_member(self, target: object, name: str) -> None:
        """Ruft eine Methode ueber das Kontextmenue auf (D1, D2).

        Das Ergebnis steht in der Statuszeile. Ein Fehler erscheint im
        Fehlerfenster -- genauso wie einer im Durchlauf (H2).
        """
        from .editor.mode import describe_result, invoke_member

        try:
            value = invoke_member(target, name)
        except (SimulationReset, SimulationStopped):
            # Kein Fehler: Waehrend des Aufrufs wurde zurueckgesetzt oder das
            # Fenster geschlossen. Die Anforderung bleibt bestehen und wird
            # von der Ereignisschleife ausgefuehrt.
            return
        except Exception as error:
            self.report_error(error)
            return
        self._status = describe_result(name, value)

    # ------------------------------------------------------------------
    # Befehle des Kontextmenues
    # ------------------------------------------------------------------

    def open_source(self, target: type | Actor) -> None:
        """Oeffnet die Quelldatei einer Klasse im Editor (Anforderung B3)."""
        from .editor import codegen
        from .editor.source import open_in_editor

        cls = target if isinstance(target, type) else type(target)
        try:
            path = codegen.source_file(cls)
        except codegen.SaveError as error:
            self._status = str(error)
            return
        self._status = open_in_editor(path, codegen.source_line(cls))

    def create_instance(self, cls: type) -> None:
        """Erzeugt ein einzelnes Objekt einer Klasse (Anforderung B6).

        Nimmt der Konstruktor Werte entgegen, wird zuerst danach gefragt --
        vorbelegt mit den Vorgaben, sodass ein Druck auf die Eingabetaste sie
        unveraendert uebernimmt (Anforderung B6a).
        """
        from .actor import Actor as _Actor
        from .editor.menu import TextPrompt
        from .editor.mode import constructor_values

        if self._edit_mode is None or not issubclass(cls, _Actor):
            return

        werte = constructor_values(cls)
        if werte is None:
            self._place_new(cls)
            return

        namen = ", ".join(name for name, _ in werte)
        vorgabe = ", ".join(repr(value) for _, value in werte)
        self.open_prompt(
            TextPrompt(
                f"{cls.__name__}({namen}) — Werte:",
                lambda text: self._place_new(cls, text),
                text=vorgabe,
            )
        )

    def _place_new(self, cls: type, arguments: str = "") -> None:
        """Erzeugt ein Objekt, gegebenenfalls mit den eingegebenen Werten."""
        from .actor import Actor as _Actor

        if self._edit_mode is None or not issubclass(cls, _Actor):
            return

        try:
            values = _literal_arguments(arguments)
        except ValueError:
            self._status = f"'{arguments}' ist keine gültige Werteangabe."
            return

        try:
            created = self._edit_mode.create_instance(cls, *values)
        except Exception as error:
            self.report_error(error)
            return

        if created is None:
            self._status = f"{cls.__name__} liess sich nicht erzeugen."
            return
        gezeigt = created.construction_code()
        self._status = (
            f"{gezeigt} erzeugt auf ({created.x}, {created.y}) "
            "-- ziehen zum Verschieben, Entf zum Entfernen."
        )

    def remove_actor(self, actor: Actor) -> None:
        """Entfernt einen Akteur aus der Welt."""
        if actor.has_world:
            actor.world.remove_object(actor)
        if self._edit_mode is not None and self._edit_mode.selected_actor is actor:
            self._edit_mode.select_at(-1, -1)
        self._status = f"{type(actor).__name__} entfernt."

    def ask_for_subclass(self, base: type) -> None:
        """Fragt nach dem Namen einer neuen Unterklasse (Anforderung B4)."""
        from .editor.menu import TextPrompt

        self.open_prompt(
            TextPrompt(
                f"Neue Unterklasse von {base.__name__} -- Name:",
                lambda name: self.create_subclass(base, name),
            )
        )

    def create_subclass(self, base: type, name: str) -> None:
        """Legt eine neue Unterklasse als Datei an (Anforderung B4).

        Die Datei wird anschliessend eingebunden, damit die Klasse sofort in
        der Klassenanzeige steht und sich setzen laesst -- ohne Neustart.
        """
        from .editor import codegen

        try:
            path = codegen.create_subclass(base, name)
        except codegen.SaveError as error:
            self._status = str(error)
            return

        try:
            codegen.import_class(path, name)
        except codegen.SaveError as error:
            self._report_save_error(error)
            if self._error_panel is None:
                self._status = f"{path.name} angelegt, aber: {error}"
            return

        if self._edit_mode is not None:
            # Die Nummerierung der Klassen hat sich verschoben.
            self._edit_mode.refresh_classes()
        init = codegen.package_init_for(path)
        eingetragen = (
            f" und in {init.parent.name}/{init.name} eingetragen" if init is not None else ""
        )
        self.set_status(
            f"{path.name} angelegt{eingetragen}. {name} steht jetzt zur Verfügung.", "success"
        )

    def switch_world(self, cls: type) -> None:
        """Erzeugt eine Welt dieser Art und zeigt sie an (Anforderung B7).

        Nimmt der Konstruktor Werte entgegen, wird zuerst danach gefragt --
        wie bei Akteuren (Anforderung B6a). Sonst waere eine Welt mit
        Wahlmoeglichkeit ueber die Oberflaeche nur in ihrer Vorgabeversion
        erreichbar.

        Das bisherige Raumschiff wird **nicht** uebernommen: Die neue Welt
        entsteht so, wie ihr Konstruktor sie vorsieht. Wer ein Schiff braucht,
        setzt selbst eines hinein -- das richtige Schiff in die richtige Welt
        zu bringen ist selbst Lerninhalt.
        """
        from .editor.menu import TextPrompt
        from .editor.mode import constructor_values
        from .world import World as _World

        if not issubclass(cls, _World):
            return

        werte = constructor_values(cls)
        if werte is not None:
            namen = ", ".join(name for name, _ in werte)
            vorgabe = ", ".join(repr(value) for _, value in werte)
            self.open_prompt(
                TextPrompt(
                    f"{cls.__name__}({namen}) — Werte:",
                    lambda text: self._build_world(cls, text),
                    text=vorgabe,
                )
            )
            return
        self._build_world(cls)

    def _build_world(self, cls: type, arguments: str = "") -> None:
        """Baut die Welt auf, gegebenenfalls mit den eingegebenen Werten.

        Wurden eigene Dateien seit dem letzten Einbinden geaendert, werden sie
        vorher neu eingebunden (H7) -- sonst zeigte `Welt anzeigen` nach dem
        Bearbeiten einer Weltdatei den alten Aufbau.
        """
        from .editor.reload import current_class

        try:
            values = _literal_arguments(arguments)
        except ValueError:
            self._status = f"'{arguments}' ist keine gültige Werteangabe."
            return

        # Die Werte gehoeren zur Welt: `Zuruecksetzen` muss sie erneut
        # verwenden, sonst entstuende die Vorgabeversion. Die Klasse wird
        # jedes Mal frisch geholt, damit Aenderungen an ihrer Datei greifen.
        def bauen() -> World:
            klasse: type = current_class(cls)
            gebaut: World = klasse(*values)
            return gebaut

        gezeigt = ", ".join(repr(v) for v in values)
        hinweis = f"{cls.__name__}({gezeigt}) erzeugt und angezeigt."

        def wechseln() -> None:
            # Eine Welt kann in ihrem Konstruktor Akteure einsetzen. Bei einem
            # Raumschiff ist `set_location` mit `redraws` gekennzeichnet -- ohne
            # diesen Schutz bliebe der Wechsel im Konstruktor haengen, solange
            # die Simulation angehalten ist.
            with self.suspended():
                world = bauen()

            if self._in_act_cycle:
                # Mitten im Schuelercode darf die Welt nicht unter ihm
                # ausgetauscht werden -- erst abbrechen, dann wechseln.
                self._pending_world = world
                self._pending_factory = bauen
                self._reset_requested = True
            else:
                self.set_world(world, factory=bauen)
            self._status = hinweis

        try:
            if self._in_act_cycle:
                # Solange Schuelercode laeuft, werden keine Module getauscht.
                wechseln()
            else:
                self._with_fresh_sources(wechseln)
        except Exception as error:
            self.report_error(error)

    def delete_class(self, cls: type) -> None:
        """Entfernt eine selbst geschriebene Klasse (Anforderung B8).

        Der erste Aufruf fragt nach, der zweite fuehrt aus -- wie beim
        Sichern mit Strukturverlust. Vorhandene Objekte dieser Klasse werden
        zuvor aus der Welt genommen.
        """
        from .actor import Actor as _Actor
        from .editor import codegen

        erlaubt, grund = codegen.can_delete(cls)
        if not erlaubt:
            self._delete_confirmed = None
            self._status = grund
            return

        if self._delete_confirmed is not cls:
            self._delete_confirmed = cls
            self.set_status(
                f"{cls.__name__} wirklich entfernen? Nochmal drücken zum Löschen.", "warning"
            )
            return

        if self._world is not None and issubclass(cls, _Actor):
            present: list[Actor] = self._world.objects()
            for actor in present:
                if isinstance(actor, cls):
                    self._world.remove_object(actor)

        if self._edit_mode is not None:
            self._edit_mode.forget(cls)

        try:
            backup = codegen.delete_class(cls)
        except codegen.SaveError as error:
            self._delete_confirmed = None
            self._status = str(error)
            return

        self._delete_confirmed = None
        self._take_snapshot()
        if self._edit_mode is not None:
            self._edit_mode.refresh_classes()
        self.set_status(
            f"{cls.__name__} entfernt. Sicherungskopie: {backup.name}", "success"
        )

    def assign_image(self, cls: type, filename: str) -> None:
        """Weist einer Klasse ein Bild zu (Anforderung B5)."""
        from .editor import codegen

        try:
            codegen.assign_image(cls, filename)
        except codegen.SaveError as error:
            self._report_save_error(error)
            return
        from .editor.reload import own_modules

        if cls.__module__ in own_modules():
            wann = "Sichtbar nach dem Zurücksetzen (R)."
        else:
            wann = "Sichtbar nach einem Neustart."
        self.set_status(f"{filename} für {cls.__name__} eingetragen. {wann}", "success")

    # ------------------------------------------------------------------
    # Zuruecksetzen
    # ------------------------------------------------------------------

    @contextmanager
    def suspended(self) -> Iterator[None]:
        """Haelt die Ereignisschleife an, solange die Oberflaeche selbst arbeitet.

        Aktionen der Oberflaeche -- eine Welt erzeugen, ein Objekt setzen,
        zuruecksetzen -- rufen Methoden auf, die mit `redraws` gekennzeichnet
        sind. Ohne diesen Schutz drehte sich die Ereignisschleife mitten in
        einer solchen Aktion weiter: Bei angehaltener Simulation bliebe sie
        dort haengen, bis jemand `Start` drueckt.

        Der Schutz gilt nur fuer die Oberflaeche. Schuelercode dreht die
        Schleife weiterhin weiter -- genau dafuer ist sie da.
        """
        vorher = self._suspended
        self._suspended = True
        try:
            yield
        finally:
            self._suspended = vorher
            self._last_step = time.monotonic()

    def _take_snapshot(self) -> None:
        """Merkt sich die Ausgangslage der Welt.

        Aufgenommen werden die vorhandenen Akteure mit Feld und Blickrichtung.
        Damit laesst sich die Ausgangslage auch ohne `world_factory`
        wiederherstellen.
        """
        if self._world is None:
            self._snapshot = []
            return
        actors: list[Actor] = self._world.objects()
        self._snapshot = [
            (actor, actor.x, actor.y, actor.rotation) for actor in actors
        ]
        self._start_actor = self._find_start_actor(actors)

    def _find_start_actor(self, actors: list[Actor]) -> Actor | None:
        """Sucht den Akteur, den der Konstruktor ueber `START` eingesetzt hat.

        Startakteur ist nur, was der Konstruktor mit
        `self.add_object(X(), *self.START)` einsetzt -- im Kurs das Raumschiff
        in `Level0`. Gesucht wird der zuletzt hinzugefuegte Akteur dieser
        Klasse auf dem Startfeld; er wird nach dem Aufbau eingesetzt.

        > Befund: Vorher galt **jeder** Akteur auf dem Startfeld als
        > Startakteur. `StartWorld` erbt `START = (0, 0)`; in
        > `Level1PowerUpRow` liegt dort ein PowerUp. Es wurde beim Sichern
        > uebergangen -- und war danach verschwunden, auch ohne jede Aenderung.
        """
        from .editor.codegen import START_ATTRIBUTE, start_classes

        start = getattr(type(self.world), START_ATTRIBUTE, None)
        if not (isinstance(start, tuple) and len(start) == 2):
            return None
        classes = start_classes(type(self.world))
        if classes is None:
            return None
        on_field = [a for a in actors if (a.x, a.y) == start]
        passend = [a for a in on_field if type(a).__name__ in classes]
        if passend:
            return passend[-1]
        # Laesst sich die Klasse nicht ablesen, bleibt es beim zuletzt gesetzten.
        return on_field[-1] if on_field and "" in classes else None

    def _with_fresh_sources(self, action: Callable[[], None]) -> bool:
        """Fuehrt eine Aktion aus -- nach dem Neueinbinden geaenderter Dateien (H7).

        Hat sich keine eigene Datei geaendert, laeuft die Aktion unmittelbar.
        Sonst werden alle eigenen Module verworfen und neu eingebunden, bevor
        die Aktion laeuft. Scheitert das Einbinden oder die Aktion selbst,
        wird der vorherige Stand wiederhergestellt und der Fehler
        weitergereicht: Die angezeigte Welt bleibt dann, wie sie war.

        Der Stand der Dateien wird nur nach Erfolg fortgeschrieben. Ein
        erneutes `Zuruecksetzen` versucht es deshalb wieder -- und meldet den
        Fehler erneut, solange die Datei nicht repariert ist.

        Returns:
            Ob neu eingebunden wurde.
        """
        from .editor import reload as _reload

        if not self._ui_enabled or self._source_signature is None:
            action()
            return False

        signature = _reload.source_signature()
        changed = _reload.changed_files(self._source_signature, signature)
        if not changed:
            action()
            return False

        before = self._status
        _reload.forget_bytecode(_reload.changed_paths(self._source_signature, signature))
        backup = _reload.discard(_reload.own_modules())
        try:
            _reload.import_again(backup.names)
            # Zustandsanzeige und Menue verweisen auf Objekte des alten
            # Stands; sie gelten nicht mehr.
            self._inspector = None
            self._menu = None
            action()
        except BaseException:
            backup.restore()
            raise

        self._source_signature = signature
        self._saved_files = {}
        if self._edit_mode is not None:
            self._edit_mode.reload_classes()
        if self._sidebar is not None:
            self._sidebar.refresh()
        neu = ", ".join(changed[:3]) + (" …" if len(changed) > 3 else "")
        # Hat die Aktion selbst etwas gemeldet, bleibt das dahinter stehen.
        dazu = f" {self._status}" if self._status and self._status != before else ""
        self.set_status(f"Neu eingebunden: {neu}.{dazu}", "success")
        # Eine von Hand angelegte Datei bindet niemand ein, solange sie nicht
        # in der Paketdatei steht. Ohne Hinweis passierte schlicht nichts (B4f).
        fehlend = _reload.unregistered_files()
        if fehlend:
            namen = ", ".join(f"{p.parent.name}/{p.name}" for p in fehlend[:3])
            self._status += f" Nicht eingebunden: {namen} -- Eintrag in __init__.py fehlt."
        return True

    def _perform_reset(self) -> None:
        """Setzt zurueck, wie es die Oberflaeche anfordert (E1, H7, H2).

        Geaenderte eigene Dateien werden dabei neu eingebunden. Ein Fehler --
        in einer Datei oder im Konstruktor der Welt -- beendet das Programm
        nicht, sondern erscheint im Fehlerfenster.
        """
        # Vorab loeschen: Bliebe die Anforderung nach einem Fehler bestehen,
        # loeste die Ereignisschleife sofort das naechste Zuruecksetzen aus --
        # und derselbe Fehler kaeme ohne Ende wieder.
        self._reset_requested = False
        self._error_panel = None
        try:
            if self._pending_world is not None:
                self.reset()
                return
            neu = self._with_fresh_sources(self.reset)
        except Exception as error:
            self.report_error(error)
            return

        if neu and self._world_factory is None:
            # Ohne Bauanleitung stellt `reset` nur die alten Objekte zurueck --
            # sie gehoeren noch zu den alten Klassen.
            self._status += " Die Welt lässt sich nicht neu bauen und zeigt den alten Stand."

    def reset(self) -> None:
        """Stellt die Ausgangslage wieder her und beginnt von vorn.

        Ist eine `world_factory` gesetzt, wird die Welt vollstaendig neu
        erzeugt. Andernfalls werden die Akteure der Momentaufnahme auf ihre
        Startfelder zurueckgesetzt, spaeter hinzugekommene entfernt und die
        Anweisungsfolgen erneut freigegeben.

        Der Zustand innerhalb eigener Akteursklassen -- etwa mitgezaehlte
        Werte -- bleibt dabei erhalten. Wer ihn ebenfalls zuruecksetzen will,
        setzt `world_factory`.
        """
        from .actor import Actor as _Actor
        from .actor import ScriptActor as _ScriptActor

        self._reset_requested = False
        self._step_requested = False
        self._cycle_requested = False

        if self._pending_world is not None:
            # Ein Weltwechsel wartet: Er hat den laufenden Code abgebrochen
            # und wird jetzt ausgefuehrt (Anforderung B7).
            world = self._pending_world
            factory = self._pending_factory
            self._pending_world = None
            self._pending_factory = None
            self.set_world(world, factory=factory)
            return

        with self.suspended():
            if self._world_factory is not None:
                self._world = self._world_factory()
                self._input.cell_size = self._world.cell_size
                self._take_snapshot()
                self._open_window()
                return

            world = self.world
            remembered = {id(actor) for actor, _, _, _ in self._snapshot}
            current: list[Actor] = world.objects()
            for actor in current:
                if id(actor) not in remembered:
                    world.remove_object(actor)

            remaining: list[Actor] = world.objects()
            present = {id(actor) for actor in remaining}
            for actor, x, y, rotation in self._snapshot:
                if id(actor) not in present:
                    world.add_object(actor, x, y)
                # Unmittelbar setzen: die Version von `ScriptActor` wuerde die
                # Ereignisschleife weiterdrehen und damit erneut hier landen.
                _Actor.set_location(actor, x, y)
                actor.rotation = rotation
                if isinstance(actor, _ScriptActor):
                    actor._reset_init()

            world.clear_texts()

    # ------------------------------------------------------------------
    # Fenster
    # ------------------------------------------------------------------

    def _window_size(self) -> tuple[int, int]:
        """Berechnet die Fenstergroesse aus Welt, Klassenanzeige und Leiste."""
        world = self.world
        width = world.width * world.cell_size
        height = world.height * world.cell_size
        if not self._ui_enabled:
            return width, height

        from .editor.panel import ControlPanel as _ControlPanel
        from .editor.sidebar import ClassSidebar as _ClassSidebar

        return _fits_on_screen(
            max(width + _ClassSidebar.WIDTH, _ControlPanel.MIN_WIDTH),
            height + _ControlPanel.HEIGHT,
        )

    #: Kleinste Fenstergroesse. Darunter waeren die Bedienelemente unbrauchbar.
    MIN_WINDOW_SIZE: tuple[int, int] = (420, 240)

    def _open_window(self) -> None:
        """Oeffnet das Fenster passend zur Groesse der aktuellen Welt.

        Hat der Benutzer die Groesse von Hand veraendert, bleibt sie erhalten
        -- auch wenn eine andere Welt angezeigt wird. Die Welt wird dann in
        der vorhandenen Flaeche zentriert und noetigenfalls beschnitten.
        """
        if not pygame.display.get_init():
            pygame.display.init()
        if not pygame.font.get_init():
            pygame.font.init()

        size = self._user_size if self._user_size is not None else self._window_size()
        self._screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self._world_surface = None
        self._update_caption()
        # Die sichtbare Flaeche hat sich geaendert: Eine Verschiebung, die
        # jetzt zu weit ginge, wird zurechtgerueckt (C7).
        self.scroll_to(*self._scroll)

        if not self._ui_enabled:
            self._panel = None
            self._sidebar = None
            self._edit_mode = None
            return

        from .editor.mode import EditMode as _EditMode
        from .editor.panel import ControlPanel as _ControlPanel
        from .editor.sidebar import ClassSidebar as _ClassSidebar

        if self._panel is None:
            self._panel = _ControlPanel(self, size[0])
        if self._sidebar is None:
            self._sidebar = _ClassSidebar(self, size[1])
        if self._edit_mode is None:
            self._edit_mode = _EditMode(self)
        self._layout()

    def _layout(self) -> None:
        """Richtet Bedienleiste und Klassenanzeige auf die Fenstergroesse aus."""
        if self._screen is None:
            return
        if self._panel is not None:
            self._panel.resize(self._screen.get_width())
        if self._sidebar is not None:
            self._sidebar.resize(self._panel_top())

    def resize_window(self, size: tuple[int, int]) -> None:
        """Nimmt eine vom Benutzer geaenderte Fenstergroesse an.

        Ab jetzt bestimmt sie die Groesse -- ein Weltwechsel setzt sie nicht
        mehr zurueck.
        """
        width = max(size[0], Engine.MIN_WINDOW_SIZE[0])
        height = max(size[1], Engine.MIN_WINDOW_SIZE[1])
        self._user_size = (width, height)
        self._screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self._layout()
        self.scroll_to(*self._scroll)

    # ------------------------------------------------------------------
    # Ereignisschleife
    # ------------------------------------------------------------------

    def _pump_events(self) -> None:
        """Holt die Fensterereignisse ab und haelt das Fenster bedienbar.

        Ereignisse der Bedienleiste werden dort verbraucht; alle uebrigen
        gehen an den Eingabezustand, den Schuelercode abfragen kann.
        """
        self._input.origin = self.world_origin()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                continue
            if event.type == pygame.VIDEORESIZE:
                self.resize_window(event.size)
                if self._error_panel is not None and self._screen is not None:
                    self._error_panel.center_in(
                        self._screen.get_width(), self._screen.get_height()
                    )
                continue

            try:
                self._dispatch_event(event)
            except (SimulationReset, SimulationStopped):
                raise
            except Exception as error:
                # Jede Aktion der Oberflaeche kann eigenen Code ausfuehren --
                # einen Konstruktor, eine Methode, eine Eigenschaft. Ein Fehler
                # darin erscheint im Fehlerfenster (H2).
                self.report_error(error)

    def _dispatch_event(self, event: pygame.event.Event) -> None:
        """Reicht ein Fensterereignis an den zustaendigen Teil der Oberflaeche."""
        panel_top = self._panel_top()
        sidebar_left = self.sidebar_left()
        # Das Fehlerfenster bekommt alles: Ein Druck auf die Leertaste
        # soll nicht weiterlaufen lassen, was gerade gescheitert ist.
        if self._error_panel is not None:
            used, close = self._error_panel.handle_event(event)
            if close:
                self.close_error_panel()
            if used:
                return

        # Eine offene Eingabe oder ein offenes Menue bekommt alles zuerst:
        # Sonst liefe ein Tastendruck versehentlich in die Bedienleiste,
        # und `Esc` beendete das Fenster statt nur das Menue.
        if self._prompt is not None:
            used, close = self._prompt.handle_event(event)
            if close:
                self.close_prompt()
            if used:
                return
        elif self._menu is not None:
            used, close = self._menu.handle_event(event)
            if close:
                self.close_menu()
            if used:
                return

        # Die Zustandsanzeige verbraucht nur, was sie selbst betrifft:
        # Waehrenddessen soll sich weiterhin schrittweise fortschalten
        # lassen, um den Werten beim Aendern zuzusehen.
        if self._inspector is not None:
            used, close = self._inspector.handle_event(event)
            if close:
                self.close_inspector()
            if used:
                return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._running = False
            return
        if self._panel is not None and self._panel.handle_event(event, panel_top):
            return
        if self._sidebar is not None and self._sidebar.handle_event(event, sidebar_left):
            return
        # Vor dem Bearbeitungsmodus: Ein Klick auf die Bildlaufleiste soll
        # nicht als Klick in die Welt gelten (C7).
        if self._handle_scroll_event(event):
            return
        if self._edit_mode is not None and self._edit_mode.handle_event(event):
            return
        self._input.handle(event)

    def _panel_top(self) -> int:
        """Liefert die obere Kante der Bedienleiste im Fenster.

        Die Leiste haengt am **unteren Fensterrand**, nicht an der Hoehe der
        Welt: Sonst rutschte sie beim Vergroessern des Fensters mitten in die
        Flaeche.
        """
        if self._screen is None:
            return 0
        if self._panel is None:
            return self._screen.get_height()

        from .editor.panel import ControlPanel as _ControlPanel

        return max(0, self._screen.get_height() - _ControlPanel.HEIGHT)

    def sidebar_left(self) -> int:
        """Liefert die linke Kante der Klassenanzeige im Fenster."""
        if self._screen is None or self._sidebar is None:
            return self._screen.get_width() if self._screen is not None else 0

        from .editor.sidebar import ClassSidebar as _ClassSidebar

        return self._screen.get_width() - _ClassSidebar.WIDTH

    #: Dicke einer Bildlaufleiste in Bildpunkten.
    SCROLLBAR_SIZE: int = 12

    @property
    def scroll(self) -> tuple[int, int]:
        """Verschiebung der Welt im Fenster, in Bildpunkten."""
        return self._scroll

    def scroll_limits(self) -> tuple[int, int]:
        """Groesste Verschiebung; 0, wenn die Welt ganz in die Flaeche passt."""
        if self._world is None or self._screen is None:
            return 0, 0
        view_width, view_height = self.world_view()
        world_width = self._world.width * self._world.cell_size
        world_height = self._world.height * self._world.cell_size
        return (
            max(0, world_width - view_width),
            max(0, world_height - view_height),
        )

    def scroll_to(self, x: int, y: int) -> None:
        """Verschiebt die Welt; ausserhalb der Grenzen wird begrenzt."""
        limit_x, limit_y = self.scroll_limits()
        self._scroll = (max(0, min(int(x), limit_x)), max(0, min(int(y), limit_y)))

    def scroll_by(self, dx: int, dy: int) -> None:
        """Verschiebt die Welt um die angegebene Strecke."""
        self.scroll_to(self._scroll[0] + dx, self._scroll[1] + dy)

    def scrollbars(self) -> dict[str, pygame.Rect]:
        """Liefert die sichtbaren Bildlaufleisten samt ihrer Schieber.

        Enthalten sind die Schluessel `vertical`, `horizontal` und die
        zugehoerigen Schieber `vertical_thumb`, `horizontal_thumb`. Passt die
        Welt in die Flaeche, fehlt die jeweilige Leiste.
        """
        if self._world is None or self._screen is None:
            return {}
        view_width, view_height = self.world_view()
        limit_x, limit_y = self.scroll_limits()
        size = Engine.SCROLLBAR_SIZE
        bars: dict[str, pygame.Rect] = {}

        height = view_height - (size if limit_x else 0)
        width = view_width - (size if limit_y else 0)
        if limit_y and height > 0:
            bars["vertical"] = pygame.Rect(view_width - size, 0, size, height)
            bars["vertical_thumb"] = _thumb(
                bars["vertical"], self._scroll[1], limit_y, view_height, vertical=True
            )
        if limit_x and width > 0:
            bars["horizontal"] = pygame.Rect(0, view_height - size, width, size)
            bars["horizontal_thumb"] = _thumb(
                bars["horizontal"], self._scroll[0], limit_x, view_width, vertical=False
            )
        return bars

    def _scroll_from_thumb(self, name: str, position: tuple[int, int]) -> None:
        """Rechnet die Lage eines gezogenen Schiebers in eine Verschiebung um."""
        bars = self.scrollbars()
        track = bars.get(name)
        thumb = bars.get(f"{name}_thumb")
        if track is None or thumb is None:
            return
        limit_x, limit_y = self.scroll_limits()
        if name == "vertical":
            room = max(1, track.height - thumb.height)
            anteil = (position[1] - track.top - thumb.height // 2) / room
            self.scroll_to(self._scroll[0], round(anteil * limit_y))
        else:
            room = max(1, track.width - thumb.width)
            anteil = (position[0] - track.left - thumb.width // 2) / room
            self.scroll_to(round(anteil * limit_x), self._scroll[1])

    def _handle_scroll_event(self, event: pygame.event.Event) -> bool:
        """Wertet Mausrad und Bildlaufleisten aus (Anforderung C7).

        Returns:
            True, wenn das Ereignis verbraucht wurde.
        """
        limit_x, limit_y = self.scroll_limits()
        if not (limit_x or limit_y):
            return False
        view_width, view_height = self.world_view()
        schritt = self._world.cell_size if self._world is not None else 20

        if event.type == pygame.MOUSEWHEEL:
            spot = pygame.mouse.get_pos()
            if spot[0] >= view_width or spot[1] >= view_height:
                return False
            seitwaerts = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) or not limit_y
            if seitwaerts:
                self.scroll_by(-event.y * schritt - event.x * schritt, 0)
            else:
                self.scroll_by(-event.x * schritt, -event.y * schritt)
            return True

        if event.type == pygame.MOUSEBUTTONUP:
            war = self._dragging_scrollbar is not None
            self._dragging_scrollbar = None
            return war

        if event.type == pygame.MOUSEMOTION and self._dragging_scrollbar is not None:
            spot = event.pos
            self._scroll_from_thumb(self._dragging_scrollbar, (int(spot[0]), int(spot[1])))
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            spot = event.pos
            point = (int(spot[0]), int(spot[1]))
            for name in ("vertical", "horizontal"):
                track = self.scrollbars().get(name)
                if track is not None and track.collidepoint(point):
                    # Ein Klick neben den Schieber springt dorthin; danach
                    # laesst er sich weiterziehen.
                    self._dragging_scrollbar = name
                    self._scroll_from_thumb(name, point)
                    return True
        return False

    def world_view(self) -> tuple[int, int]:
        """Liefert die Flaeche, die der Welt bleibt: links neben der Anzeige,
        oberhalb der Leiste."""
        if self._screen is None:
            return 0, 0
        return self.sidebar_left(), self._panel_top()

    def world_origin(self) -> tuple[int, int]:
        """Liefert die obere linke Ecke der Welt im Fenster.

        Die Welt steht mittig in der ihr verbleibenden Flaeche. Ist sie
        groesser als diese, bestimmt die Verschiebung, welcher Ausschnitt zu
        sehen ist -- dafuer gibt es die Bildlaufleisten (C7).
        """
        if self._screen is None or self._world is None:
            return 0, 0
        width, height = self.world_view()
        world_width = self._world.width * self._world.cell_size
        world_height = self._world.height * self._world.cell_size
        limit_x, limit_y = self.scroll_limits()
        left = -self._scroll[0] if limit_x else max(0, (width - world_width) // 2)
        top = -self._scroll[1] if limit_y else max(0, (height - world_height) // 2)
        return left, top

    def _render(self) -> None:
        """Zeichnet Welt und Bedienleiste in das Fenster."""
        if self._screen is None or self._world is None:
            return

        world_width = self._world.width * self._world.cell_size
        world_height = self._world.height * self._world.cell_size
        left, top = self.world_origin()
        view_width, view_height = self.world_view()

        self._screen.fill((12, 14, 24))

        # Die Welt wird auf eine eigene Flaeche gezeichnet und dann in das
        # Fenster geblendet. Nur so laesst sie sich beschneiden, wenn das
        # Fenster kleiner ist als sie.
        if (
            self._world_surface is None
            or self._world_surface.get_size() != (world_width, world_height)
        ):
            self._world_surface = pygame.Surface((world_width, world_height))

        self._world._render_to(self._world_surface)
        if self._edit_mode is not None:
            self._edit_mode.render_overlay(self._world_surface)

        self._screen.set_clip((0, 0, view_width, view_height))
        self._screen.blit(self._world_surface, (left, top))
        if left > 0 or top > 0:
            # Ist das Fenster groesser als die Welt, zeigt ein Rahmen, wo sie
            # aufhoert. Ohne ihn saehe eine kleine Welt in einem grossen
            # Fenster nach einer leeren Flaeche aus.
            pygame.draw.rect(
                self._screen,
                (60, 66, 82),
                (left - 1, top - 1, world_width + 2, world_height + 2),
                width=1,
            )
        self._screen.set_clip(None)
        self._render_scrollbars()

        if self._sidebar is not None and view_height > 0:
            self._sidebar.render(
                self._screen.subsurface(
                    (self.sidebar_left(), 0, self._sidebar.WIDTH, view_height)
                )
            )

        if self._panel is not None:
            from .editor.panel import ControlPanel as _ControlPanel

            self._panel.render(
                self._screen.subsurface(
                    (
                        0,
                        self._panel_top(),
                        self._screen.get_width(),
                        _ControlPanel.HEIGHT,
                    )
                )
            )

        # Zustandsanzeige, Menue und Eingabe liegen ueber allem anderen.
        if self._inspector is not None:
            self._inspector.render(self._screen)
        if self._menu is not None:
            self._menu.render(self._screen)
        if self._prompt is not None:
            self._prompt.render(self._screen)
        if self._error_panel is not None:
            self._error_panel.render(self._screen)

        pygame.display.flip()

    #: Farben der Bildlaufleisten. Dunkel gehalten wie die uebrige Oberflaeche.
    SCROLLBAR_TRACK = (26, 29, 38)
    SCROLLBAR_THUMB = (86, 94, 112)

    def _render_scrollbars(self) -> None:
        """Zeichnet die Bildlaufleisten am Rand des Weltausschnitts (C7)."""
        if self._screen is None:
            return
        bars = self.scrollbars()
        for name in ("vertical", "horizontal"):
            track = bars.get(name)
            thumb = bars.get(f"{name}_thumb")
            if track is None or thumb is None:
                continue
            pygame.draw.rect(self._screen, Engine.SCROLLBAR_TRACK, track)
            pygame.draw.rect(
                self._screen, Engine.SCROLLBAR_THUMB, thumb.inflate(-4, -4), border_radius=4
            )

    def _check_requests(self) -> None:
        """Wertet die Anforderungen der Bedienleiste aus.

        Raises:
            SimulationStopped: Wenn das Fenster geschlossen wurde.
            SimulationReset: Wenn die Ausgangslage wiederhergestellt werden soll.
        """
        if self._reset_requested:
            raise SimulationReset("Die Welt wird zurueckgesetzt.")
        # Nur abbrechen, wenn die Simulation lief und inzwischen beendet wurde.
        # Wurde sie nie gestartet, ist der Aufruf ein regulaerer Einzelschritt.
        if self._started and not self._running:
            raise SimulationStopped(
                "Das Fenster wurde geschlossen, die Ausfuehrung wird abgebrochen."
            )

    def update_screen(self) -> None:
        """Dreht die Ereignisschleife einen Schritt weiter.

        Wird nach jeder mit `redraws` gekennzeichneten Aktion aufgerufen und
        kann aus langen Rechenschleifen heraus auch von Hand aufgerufen werden,
        damit das Fenster waehrenddessen bedienbar bleibt.

        Hier greift auch der Einzelschritt: Ist die Ausfuehrung angehalten,
        kehrt der Aufruf erst zurueck, wenn fortgesetzt oder ein Schritt
        angefordert wurde. Damit haelt eine laufende `init` an, ohne dass ein
        zweiter Thread noetig waere (Editor-Anforderungsdokument C3).

        Raises:
            SimulationStopped: Wenn das Fenster inzwischen geschlossen wurde.
            SimulationReset: Wenn die Welt zurueckgesetzt werden soll.
        """
        if self._screen is None or self._suspended:
            # Ohne Fenster (etwa in automatisierten Tests) gibt es nichts zu tun.
            return

        # Die Wartezeit wird nur eingehalten, solange die Simulation laeuft.
        # Ohne laufende Simulation wird genau einmal gezeichnet.
        deadline = self._last_step + self._step_duration
        first_pass = True
        while first_pass or (self._running and time.monotonic() < deadline):
            self._pump_events()
            self._render()
            self._clock.tick(self._fps_limit)
            first_pass = False
            self._check_requests()

        self._wait_while_paused()

        self._last_step = time.monotonic()
        self._check_requests()

    def _wait_while_paused(self) -> None:
        """Haelt an, solange die Ausfuehrung angehalten ist.

        Kehrt zurueck, sobald fortgesetzt oder ein Einzelschritt angefordert
        wurde. Der angeforderte Schritt wird dabei verbraucht.
        """
        while self._paused and self._running:
            if self._step_requested:
                self._step_requested = False
                return
            self._pump_events()
            self._render()
            self._clock.tick(self._fps_limit)
            self._check_requests()

    def run(self) -> None:
        """Startet die Simulation und laeuft, bis das Fenster geschlossen wird."""
        if self._world is None:
            raise RuntimeError(
                "Es wurde noch keine Welt gesetzt. Rufe zuerst pyfoot.set_world(world) auf."
            )
        if self._screen is None:
            self._open_window()

        self._running = True
        self._started = True
        self._last_step = time.monotonic()
        try:
            while self._running:
                try:
                    self._main_loop()
                except SimulationReset:
                    # Der laufende Code wurde abgebrochen; die Ausgangslage
                    # wird wiederhergestellt und es geht von vorn los.
                    if self._ui_enabled:
                        self._perform_reset()
                    else:
                        self.reset()
        except SimulationStopped:
            # Regulaeres Ende: das Fenster wurde waehrend einer Aktion geschlossen.
            pass
        finally:
            self._running = False

    def _main_loop(self) -> None:
        """Fuehrt Durchlauf um Durchlauf aus, bis das Fenster geschlossen wird.

        Ist die Ausfuehrung angehalten, wird nur gezeichnet -- ausser es wurde
        ein einzelner Durchlauf angefordert.
        """
        while self._running:
            self._pump_events()
            self._check_requests()
            if not self._running:
                break

            if self._paused and not self._cycle_requested:
                self._render()
                self._clock.tick(self._fps_limit)
                continue

            self._cycle_requested = False
            try:
                self._act_cycle()
            except (SimulationReset, SimulationStopped):
                raise
            except Exception as error:
                # Ein Fehler im Schuelercode beendet das Programm nicht mehr:
                # Die Ausfuehrung haelt an, das Fehlerfenster zeigt ihn (H1).
                # Ohne Oberflaeche wird er weitergereicht wie bisher (F1).
                self.report_error(error)
            self._render()
            self._clock.tick(self._fps_limit)

    def _act_cycle(self) -> None:
        """Fuehrt genau einen Act-Durchlauf aus.

        Der Rekursionsschutz stellt sicher, dass aus einer Aktion heraus kein
        weiterer Act-Durchlauf startet (Anforderungsdokument 4.6, Auflage 2).
        """
        if self._in_act_cycle:
            return
        self._in_act_cycle = True
        # Klicks und Tastendruecke gelten jeweils fuer einen Durchlauf.
        self._input.begin_cycle()
        try:
            self.world._act_cycle()
        finally:
            self._in_act_cycle = False

    def stop(self) -> None:
        """Beendet die Simulation."""
        self._running = False

    def quit(self) -> None:
        """Beendet die Simulation und schliesst das Fenster."""
        self.stop()
        if self._screen is not None:
            pygame.display.quit()
            self._screen = None


# ----------------------------------------------------------------------
# Bequeme Modulfunktionen
# ----------------------------------------------------------------------


def get_engine() -> Engine:
    """Liefert die Laufzeitsteuerung."""
    return Engine.instance()


def set_world(world: World) -> None:
    """Legt die Welt fest, die dargestellt und simuliert wird."""
    Engine.instance().set_world(world)


def run() -> None:
    """Startet die Simulation."""
    Engine.instance().run()


def stop() -> None:
    """Beendet die Simulation."""
    Engine.instance().stop()


def update_screen() -> None:
    """Zeichnet neu und haelt das Fenster bedienbar.

    Aus langen Rechenschleifen heraus aufrufen, die keine Aktion ausloesen.
    """
    Engine.instance().update_screen()


def enable_ui(enabled: bool = True) -> None:
    """Schaltet die Bedienleiste im Fenster ein.

    Vor `set_world` aufrufen. Ohne diesen Aufruf verhaelt sich PyFoot wie
    bisher; die Kommandozeile bleibt gleichwertig (Editor-Anforderungsdokument
    2.1). Alternativ laesst sich die Umgebungsvariable `PYFOOT_UI` setzen.
    """
    Engine.instance().enable_ui(enabled)


def disable_ui() -> None:
    """Schaltet die Bedienleiste wieder ab."""
    Engine.instance().enable_ui(False)


def ui_enabled() -> bool:
    """Gibt an, ob die Bedienleiste angezeigt wird."""
    return Engine.instance().ui_enabled


def random_number(limit: int) -> int:
    """Liefert eine Zufallszahl von 0 bis einschliesslich `limit` - 1."""
    if limit <= 0:
        raise ValueError("Die Obergrenze muss groesser als 0 sein.")
    return random.randrange(limit)
