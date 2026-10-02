"""Der Bearbeitungsmodus: Objekte setzen, auswaehlen, verschieben, entfernen.

Setzt die Anforderungen A1 bis A3 des Editor-Anforderungsdokuments um. Der
Modus ist abschaltbar; solange er aus ist, gehoeren alle Mausereignisse dem
Schuelercode (Auflage F1).

Bedienung im Weltausschnitt:
    Klick auf ein leeres Feld      setzt ein Objekt der gewaehlten Klasse
    Umschalt + Klick               setzt auch auf ein belegtes Feld
    Klick auf ein Objekt           waehlt es aus und beginnt das Ziehen
    Ziehen                         verschiebt das ausgewaehlte Objekt
    Rechtsklick                    oeffnet das Kontextmenue des Objekts
    Entf                           entfernt das ausgewaehlte Objekt
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Callable

import pygame

from .menu import ContextMenu, MenuEntry

if TYPE_CHECKING:
    from ..actor import Actor
    from ..engine import Engine

__all__ = [
    "EditMode",
    "build_actor_menu",
    "build_class_menu",
    "build_image_menu",
    "call_member",
    "callable_members",
    "can_construct",
    "describe_result",
    "invoke_member",
    "placeable_classes",
]


def can_construct(cls: type) -> bool:
    """Gibt an, ob sich die Klasse ohne Werte erzeugen laesst.

    Gilt fuer Akteure wie fuer Welten: Nur solche Klassen lassen sich mit
    einem Klick setzen beziehungsweise anzeigen. Abstrakte Klassen -- etwa
    eine Grundklasse mit offener Methode -- gehoeren nicht dazu.
    """
    if inspect.isabstract(cls):
        return False
    try:
        parameters = list(inspect.signature(cls).parameters.values())
    except (TypeError, ValueError):  # pragma: no cover -- exotische Klassen
        return False
    return all(
        parameter.default is not inspect.Parameter.empty
        or parameter.kind
        in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for parameter in parameters
    )


def placeable_classes() -> list[type[Actor]]:
    """Sammelt alle Akteursklassen, die sich setzen lassen.

    Gefunden wird, was das laufende Programm eingebunden hat. Klassen aus
    PyFoot selbst bleiben aussen vor: Sie sind Bauteile, keine Spielfiguren.

    Die Reihenfolge stimmt mit der Klassenanzeige ueberein -- sonst passten
    die Ziffern 1 bis 9 nicht zu dem, was im Fenster steht.
    """
    from .sidebar import class_tree

    return [row.cls for row in class_tree() if row.placeable]  # type: ignore[misc]


#: Werte, die sich gefahrlos aus einer Eingabe lesen lassen.
LITERAL_TYPES = (int, float, str, bool, type(None), tuple, list)


def constructor_values(cls: type) -> list[tuple[str, object]] | None:
    """Liefert die Werte, die der Konstruktor entgegennimmt.

    Beruecksichtigt werden nur Konstruktoren, deren Vorbelegungen sich als
    Text schreiben und wieder einlesen lassen -- Zahlen, Zeichenketten,
    Wahrheitswerte. Ein Konstruktor, der ein Objekt erwartet, laesst sich so
    nicht abfragen; dort wird ohne Rueckfrage mit den Vorbelegungen erzeugt.

    Returns:
        Die Paare aus Name und Vorbelegung, oder None, wenn sich nicht
        danach fragen laesst.
    """
    try:
        parameters = list(inspect.signature(cls).parameters.values())
    except (TypeError, ValueError):  # pragma: no cover -- exotische Klassen
        return None

    values: list[tuple[str, object]] = []
    for parameter in parameters:
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if parameter.default is inspect.Parameter.empty:
            return None
        if not isinstance(parameter.default, LITERAL_TYPES):
            return None
        values.append((parameter.name, parameter.default))
    return values or None


def callable_members(target: object) -> list[str]:
    """Sammelt die oeffentlichen Methoden, die sich ohne Werte aufrufen lassen.

    Anforderung D1. Gezeigt wird nur, was die Klasse tatsaechlich mitbringt --
    die im Kurs absichtlich fehlenden Methoden duerfen nicht den Eindruck
    erwecken, es gebe sie (didaktische Auflage E2).

    Die Bauteile von PyFoot selbst bleiben aussen vor; im Blick sind die
    Faehigkeiten, die im Unterricht besprochen werden.
    """
    cls = type(target)
    names: list[str] = []

    for name in dir(cls):
        if name.startswith("_"):
            continue
        owner = next((base for base in cls.__mro__ if name in vars(base)), None)
        if owner is None or owner is object or owner.__module__.startswith("pyfoot"):
            continue

        member = vars(owner)[name]
        if isinstance(member, property):
            names.append(name)
            continue
        if not callable(member):
            continue

        try:
            signature = inspect.signature(member)
        except (TypeError, ValueError):  # pragma: no cover -- exotische Methoden
            continue
        required = [
            parameter
            for parameter in list(signature.parameters.values())[1:]
            if parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if required:
            continue
        names.append(name)

    return sorted(names)


def invoke_member(target: object, name: str) -> object:
    """Ruft eine Methode auf -- oder liest eine Eigenschaft -- und liefert den Wert.

    Fehler werden **nicht** abgefangen: Die Oberflaeche meldet sie im
    Fehlerfenster, wie jeden anderen Fehler auch (Anforderung H2).
    """
    member = getattr(type(target), name, None)
    if isinstance(member, property):
        return getattr(target, name)
    return getattr(target, name)()


def describe_result(name: str, value: object) -> str:
    """Beschreibt das Ergebnis eines Aufrufs fuer die Statuszeile (D2)."""
    if value is None:
        return f"{name}() ausgefuehrt."
    return f"{name}() = {value!r}"


def call_member(target: object, name: str) -> str:
    """Ruft eine Methode auf und beschreibt das Ergebnis (Anforderung D2).

    Ein Fehler beim Aufruf ist ein zulaessiges Ergebnis -- er wird als Text
    geliefert, nicht weitergereicht. Die Oberflaeche selbst ruft ueber
    `Engine.call_member` auf und zeigt Fehler im Fehlerfenster; diese Version
    bleibt fuer Aufrufe ohne Fenster.
    """
    try:
        value = invoke_member(target, name)
    except Exception as error:
        return f"{name}: {type(error).__name__}: {error}"
    return describe_result(name, value)


def build_class_menu(engine: Engine, cls: type, position: tuple[int, int]) -> ContextMenu:
    """Baut das Kontextmenue einer Klasse (Anforderungen B3 bis B8).

    Akteure und Welten bekommen verschiedene erste Eintraege: Ein Akteur wird
    in die Welt gesetzt, eine Welt **ersetzt** die angezeigte.
    """
    from ..actor import Actor as _Actor
    from ..world import World as _World
    from . import codegen

    entries: list[MenuEntry] = []

    # Der Eintrag traegt den Ausdruck, den Schueler:innen auch selbst
    # schreiben wuerden -- Greenfoot zeigt an dieser Stelle `new X()`.
    if issubclass(cls, _World):
        # Nimmt der Konstruktor Werte entgegen, wird danach gefragt -- die
        # drei Punkte kuendigen das an, wie beim Erzeugen eines Akteurs.
        mit_werten = constructor_values(cls) is not None
        entries.append(
            MenuEntry(
                f"{cls.__name__}(…) anzeigen" if mit_werten else f"{cls.__name__}() anzeigen",
                lambda: engine.switch_world(cls),
                enabled=can_construct(cls),
            )
        )
    else:
        # Nimmt der Konstruktor Werte entgegen, wird danach gefragt -- die
        # drei Punkte kuendigen das an (Anforderung B6a).
        mit_werten = constructor_values(cls) is not None
        entries.append(
            MenuEntry(
                f"{cls.__name__}(…) erzeugen" if mit_werten else f"{cls.__name__}() erzeugen",
                lambda: engine.create_instance(cls),
                enabled=issubclass(cls, _Actor) and can_construct(cls),
            )
        )

    entries.append(MenuEntry("Quelltext öffnen", lambda: engine.open_source(cls)))
    entries.append(
        MenuEntry("Unterklasse anlegen…", lambda: engine.ask_for_subclass(cls))
    )
    if issubclass(cls, _Actor):
        entries.append(
            MenuEntry(
                "Bild zuweisen…",
                lambda: engine.open_image_menu(cls, position),
                enabled=bool(codegen.available_images()),
            )
        )
    entries.append(
        MenuEntry(
            "Löschen",
            lambda: engine.delete_class(cls),
            enabled=codegen.can_delete(cls)[0],
        )
    )
    return ContextMenu(cls.__name__, entries, position)


def build_actor_menu(engine: Engine, actor: Actor, position: tuple[int, int]) -> ContextMenu:
    """Baut das Kontextmenue eines Objekts (Anforderungen D1 bis D3)."""

    def calling(name: str) -> Callable[[], None]:
        # Eigene Funktion je Eintrag, damit alle denselben Namen nicht teilen.
        return lambda: engine.call_member(actor, name)

    entries = [MenuEntry(f"{name}()", calling(name)) for name in callable_members(actor)]
    entries.append(
        MenuEntry("Inspizieren", lambda: engine.open_inspector(actor, position))
    )
    entries.append(MenuEntry("Quelltext öffnen", lambda: engine.open_source(actor)))
    entries.append(MenuEntry("Entfernen", lambda: engine.remove_actor(actor)))
    return ContextMenu(type(actor).__name__, entries, position)


def build_image_menu(engine: Engine, cls: type, position: tuple[int, int]) -> ContextMenu:
    """Baut das Menue mit den verfuegbaren Bildern (Anforderung B5)."""
    from . import codegen

    def choosing(filename: str) -> Callable[[], None]:
        return lambda: engine.assign_image(cls, filename)

    entries = [
        MenuEntry(filename, choosing(filename))
        for filename in codegen.available_images()
    ]
    return ContextMenu(f"Bild für {cls.__name__}", entries, position)


class EditMode:
    """Verwaltet Auswahl und Bearbeitung im Weltausschnitt."""

    __slots__ = (
        "_engine",
        "_enabled",
        "_selected_class",
        "_selected_actor",
        "_dragging",
        "_classes",
        "_previews",
        "_hover",
    )

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._enabled = False
        self._selected_class: type[Actor] | None = None
        self._selected_actor: Actor | None = None
        self._dragging = False
        self._classes: list[type[Actor]] = []
        self._previews: dict[type[Actor], Actor | None] = {}
        self._hover: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # Zustand
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Gibt an, ob der Bearbeitungsmodus eingeschaltet ist."""
        return self._enabled

    def enable(self, enabled: bool = True) -> None:
        """Schaltet den Bearbeitungsmodus ein oder aus."""
        self._enabled = enabled
        if enabled:
            self.refresh_classes()
        else:
            self._selected_actor = None
            self._dragging = False
            self._hover = None

    def toggle(self) -> None:
        """Wechselt zwischen Bearbeiten und Ausfuehren."""
        self.enable(not self._enabled)

    def refresh_classes(self) -> None:
        """Sucht die setzbaren Klassen erneut zusammen."""
        self._classes = placeable_classes()
        if self._selected_class not in self._classes:
            self._selected_class = self._classes[0] if self._classes else None

    def reload_classes(self) -> None:
        """Uebernimmt die Klassen nach dem Neueinbinden geaenderter Dateien (H7).

        Auswahl und Musterbilder verweisen sonst auf die alten Klassen. Die
        gewaehlte Klasse bleibt gewaehlt, sofern es sie unter ihrem Namen
        noch gibt.
        """
        name = self._selected_class.__name__ if self._selected_class else None
        self._previews.clear()
        self._selected_actor = None
        self._dragging = False
        self._classes = placeable_classes()
        same = [cls for cls in self._classes if cls.__name__ == name]
        if same:
            self._selected_class = same[0]
        else:
            self._selected_class = self._classes[0] if self._classes else None

    def forget(self, cls: type) -> None:
        """Gibt alle Verweise auf eine Klasse auf.

        Noetig vor dem Loeschen: Solange die Oberflaeche die Klasse noch
        festhaelt, bliebe sie im laufenden Programm bestehen und stuende
        weiter in der Anzeige.
        """
        if self._selected_class is cls:
            self._selected_class = None
        self._classes = [c for c in self._classes if c is not cls]
        self._previews.pop(cls, None)  # type: ignore[arg-type]
        actor = self._selected_actor
        if actor is not None and isinstance(actor, cls):
            self._selected_actor = None

    @property
    def classes(self) -> list[type[Actor]]:
        """Die Klassen, die sich setzen lassen."""
        return list(self._classes)

    @property
    def selected_class(self) -> type[Actor] | None:
        """Die Klasse, die beim Klick gesetzt wird."""
        return self._selected_class

    def select_class(self, cls: type[Actor] | None) -> None:
        """Waehlt die Klasse, die beim Klick gesetzt wird.

        Die Auswahl bleibt bestehen, bis eine andere getroffen wird -- so
        lassen sich mehrere Objekte hintereinander setzen (Anforderung A1).
        """
        self._selected_class = cls

    def select_class_at(self, index: int) -> None:
        """Waehlt die Klasse an der angegebenen Stelle der Liste."""
        if 0 <= index < len(self._classes):
            self._selected_class = self._classes[index]

    @property
    def selected_actor(self) -> Actor | None:
        """Das ausgewaehlte Objekt in der Welt."""
        return self._selected_actor

    @property
    def hover(self) -> tuple[int, int] | None:
        """Das Feld unter dem Mauszeiger."""
        return self._hover

    def preview(self, cls: type[Actor]) -> Actor | None:
        """Liefert ein Musterobjekt der Klasse, um ihr Bild zu zeigen.

        Laesst sich die Klasse nicht erzeugen, wird nichts geliefert -- das
        Bild fehlt dann, die Auswahl bleibt aber moeglich.
        """
        if cls not in self._previews:
            try:
                self._previews[cls] = cls()
            except Exception:
                # Eine Klasse mit eigenwilligem Konstruktor darf die
                # Oberflaeche nicht zum Absturz bringen.
                self._previews[cls] = None
        return self._previews[cls]

    # ------------------------------------------------------------------
    # Bearbeiten
    # ------------------------------------------------------------------

    def place(
        self, x: int, y: int, values: tuple[object, ...] = ()
    ) -> Actor | None:
        """Setzt ein Objekt der gewaehlten Klasse auf das Feld (x, y).

        Args:
            x: Spalte.
            y: Zeile.
            values: Werte fuer den Konstruktor; ohne Angabe seine Vorgaben.
        """
        cls = self._selected_class
        if cls is None or not self._engine.has_world:
            return None
        world = self._engine.world
        if not world.contains(x, y):
            return None
        # Die Werte stammen aus der Eingabe; ihr Typ steht erst zur Laufzeit
        # fest. Passt er nicht, meldet der Konstruktor selbst den Fehler --
        # die Oberflaeche faengt ihn ab und zeigt ihn an.
        actor = cls(*values)  # type: ignore[arg-type]
        # `add_object` ruft `set_location` auf; bei einem Raumschiff ist das
        # mit `redraws` gekennzeichnet und wuerde die Ereignisschleife
        # weiterdrehen -- mitten im Setzen.
        with self._engine.suspended():
            world.add_object(actor, x, y)
        # Ein Akteur darf sich beim Einfuegen selbst wieder entfernen.
        self._selected_actor = actor if actor.has_world else None
        return self._selected_actor

    def create_instance(self, cls: type[Actor], *values: object) -> Actor | None:
        """Erzeugt ein einzelnes Objekt der Klasse (Anforderung B6).

        Das Objekt entsteht auf dem Feld unter dem Mauszeiger; steht der
        Zeiger nicht ueber der Welt, in der Mitte. Danach ist es ausgewaehlt
        und laesst sich sofort verschieben oder entfernen.

        Args:
            cls: Die zu erzeugende Klasse.
            values: Werte fuer den Konstruktor; ohne Angabe seine Vorgaben.
        """
        if not self._engine.has_world:
            return None
        if not self._enabled:
            self.enable()

        world = self._engine.world
        target = self._hover or (world.width // 2, world.height // 2)
        self.select_class(cls)
        return self.place(*target, values=values)

    def remove_selected(self) -> bool:
        """Entfernt das ausgewaehlte Objekt (Anforderung A2)."""
        actor = self._selected_actor
        if actor is None or not actor.has_world:
            return False
        actor.world.remove_object(actor)
        self._selected_actor = None
        return True

    def select_at(self, x: int, y: int) -> Actor | None:
        """Waehlt das oberste Objekt auf dem Feld (x, y) aus."""
        from ..actor import Actor as _Actor

        if not self._engine.has_world:
            return None
        found: list[_Actor] = self._engine.world.objects_at(x, y)
        self._selected_actor = found[-1] if found else None
        return self._selected_actor

    def move_selected(self, x: int, y: int) -> bool:
        """Verschiebt das ausgewaehlte Objekt auf das Feld (x, y) (A3)."""
        from ..actor import Actor as _Actor

        actor = self._selected_actor
        if actor is None or not self._engine.has_world:
            return False
        if not self._engine.world.contains(x, y):
            return False
        if (actor.x, actor.y) == (x, y):
            return False
        # Unmittelbar setzen: die Version von `ScriptActor` wuerde die
        # Ereignisschleife weiterdrehen, was beim Ziehen stoert.
        _Actor.set_location(actor, x, y)
        return True

    # ------------------------------------------------------------------
    # Ereignisse
    # ------------------------------------------------------------------

    def cell_at(self, position: tuple[int, int]) -> tuple[int, int] | None:
        """Rechnet eine Fensterposition in ein Feld um; None ausserhalb."""
        if not self._engine.has_world:
            return None
        world = self._engine.world
        left, top = self._engine.world_origin()
        x = (position[0] - left) // world.cell_size
        y = (position[1] - top) // world.cell_size
        if position[0] < left or position[1] < top or not world.contains(x, y):
            return None
        return x, y

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Wertet ein Ereignis im Weltausschnitt aus.

        Returns:
            True, wenn das Ereignis verbraucht wurde.
        """
        if not self._enabled:
            return False
        if event.type == pygame.KEYDOWN:
            return self._handle_key(event)
        if event.type in (
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
        ):
            return self._handle_mouse(event)
        return False

    def _handle_key(self, event: pygame.event.Event) -> bool:
        """Tastenbedienung: loeschen und Klasse waehlen."""
        if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            return self.remove_selected()
        if pygame.K_1 <= event.key <= pygame.K_9:
            self.select_class_at(event.key - pygame.K_1)
            return True
        return False

    def _handle_mouse(self, event: pygame.event.Event) -> bool:
        """Mausbedienung: setzen, auswaehlen, ziehen, entfernen."""
        position: tuple[int, int] = event.pos
        cell = self.cell_at((int(position[0]), int(position[1])))

        if event.type == pygame.MOUSEMOTION:
            self._hover = cell
            if self._dragging and cell is not None:
                self.move_selected(*cell)
                return True
            return cell is not None

        if cell is None:
            return False

        if event.type == pygame.MOUSEBUTTONUP:
            was_dragging = self._dragging
            self._dragging = False
            return was_dragging or event.button == 1

        if event.button == 3:
            # Rechtsklick oeffnet das Kontextmenue des getroffenen Objekts
            # (Anforderungen D1 bis D3); `Entfernen` steht darin.
            if self.select_at(*cell) is not None:
                self._engine.open_actor_menu(
                    self._selected_actor, (int(position[0]), int(position[1]))
                )
            return True

        if event.button != 1:
            return False

        stacking = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        occupied = bool(self._engine.world.objects_at(*cell))

        if occupied and not stacking:
            self.select_at(*cell)
            self._dragging = self._selected_actor is not None
        else:
            self.place(*cell)
        return True

    # ------------------------------------------------------------------
    # Zeichnen
    # ------------------------------------------------------------------

    #: Farben der Hervorhebungen im Weltausschnitt.
    HOVER_COLOR = (120, 180, 255)
    SELECTION_COLOR = (255, 210, 90)

    def render_overlay(self, surface: pygame.Surface) -> None:
        """Zeichnet Hervorhebungen ueber den Weltausschnitt."""
        if not self._enabled or not self._engine.has_world:
            return
        world = self._engine.world
        size = world.cell_size

        if self._hover is not None:
            rect = pygame.Rect(self._hover[0] * size, self._hover[1] * size, size, size)
            pygame.draw.rect(surface, EditMode.HOVER_COLOR, rect, width=2)

        actor = self._selected_actor
        if actor is not None and actor.has_world:
            rect = pygame.Rect(actor.x * size, actor.y * size, size, size)
            pygame.draw.rect(surface, EditMode.SELECTION_COLOR, rect, width=3)

    def __repr__(self) -> str:
        name = self._selected_class.__name__ if self._selected_class else "-"
        return f"EditMode(enabled={self._enabled}, selected={name})"
