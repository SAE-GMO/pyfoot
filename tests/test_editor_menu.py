"""Tests fuer Klassenbaum, Kontextmenue und Bildzuweisung (Stufen E5 und E6).

Geprueft werden:
    B1  Klassenbaum mit Vererbungsbeziehung, getrennt nach Welten und Akteuren
    B3  Quelldatei im Editor oeffnen
    B4  neue Unterklasse aus Vorlage
    B5  Bild zuweisen -- als Quelltext, nicht als Nebendatei
    D1  oeffentliche Methoden eines Objekts anzeigen
    D2  Rueckgabewert anzeigen
    D3  Methoden mit Werten sind nicht erforderlich
    E2  die absichtlich fehlenden Methoden duerfen nicht vorgetaeuscht werden
    C1  jeder Eintrag ist mit der Maus erreichbar
    C2  jeder Eintrag ist ueber seine Ziffer erreichbar
"""

from __future__ import annotations

import ast
from pathlib import Path

import pygame
import pytest

from pyfoot import Actor, Image, ScriptActor, World, get_engine
from pyfoot.editor import codegen, source
from pyfoot.editor.menu import ContextMenu, MenuEntry, TextPrompt
from pyfoot.editor.mode import call_member, callable_members
from pyfoot.editor.sidebar import class_tree
from pyfoot.engine import Engine

CELL = 20


class Vehicle(ScriptActor):
    """Eine Grundklasse mit einer offenen Methode."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))

    def honk(self) -> str:
        """Liefert einen Ton."""
        return "tuut"

    def drive(self, distance: int = 1) -> None:
        """Faehrt ein Stueck; der Wert ist vorbelegt."""
        self.move(distance)

    def refuel(self, litres: int) -> None:
        """Braucht einen Wert und taucht deshalb nicht im Menue auf."""

    @property
    def wheels(self) -> int:
        """Anzahl der Raeder."""
        return 4

    def _hidden(self) -> None:
        """Nicht oeffentlich."""


class Lorry(Vehicle):
    """Eine Unterklasse, die die offene Methode schliesst."""

    __slots__ = ()

    def init(self) -> None:
        self.move()


class Breaking(Vehicle):
    """Eine Klasse, deren Methode scheitert."""

    __slots__ = ()

    def init(self) -> None:
        pass

    def stall(self) -> None:
        """Loest bewusst einen Fehler aus."""
        raise RuntimeError("Der Motor ist aus.")


def prepared() -> tuple[Engine, World]:
    """Baut eine Welt mit eingeschalteter Oberflaeche."""
    engine = get_engine()
    engine.enable_ui()
    engine.step_duration = 0.0
    world = World(10, 24, cell_size=CELL)
    engine.set_world(world)
    mode = engine.edit_mode
    assert mode is not None
    mode.enable()
    return engine, world


def key(code: int, letter: str = "") -> pygame.event.Event:
    return pygame.event.Event(
        pygame.KEYDOWN, {"key": code, "mod": 0, "unicode": letter}
    )


# ----------------------------------------------------------------------
# B1 -- der Klassenbaum
# ----------------------------------------------------------------------


def test_der_baum_enthaelt_welten_und_akteure() -> None:
    names = [row.cls.__name__ for row in class_tree()]

    assert "Actor" in names
    assert "World" in names


def test_die_vererbung_zeigt_sich_in_der_tiefe() -> None:
    rows = {row.cls: row for row in class_tree()}

    assert rows[Actor].depth == 0
    assert rows[ScriptActor].depth == 1
    assert rows[Vehicle].depth == 2
    assert rows[Lorry].depth == 3


def test_eine_klasse_steht_unter_ihrer_grundklasse() -> None:
    order = [row.cls for row in class_tree()]

    assert order.index(Vehicle) < order.index(Lorry)


def test_abstrakte_klassen_lassen_sich_nicht_setzen() -> None:
    rows = {row.cls: row for row in class_tree()}

    assert rows[Vehicle].placeable is False, "Vehicle hat eine offene Methode."
    assert rows[Lorry].placeable is True


def test_bausteine_von_pyfoot_lassen_sich_nicht_setzen() -> None:
    for row in class_tree():
        if row.cls.__module__.startswith("pyfoot"):
            assert row.placeable is False, row.cls.__name__


def test_die_ziffern_sind_fortlaufend_vergeben() -> None:
    numbers = [row.number for row in class_tree() if row.number is not None]

    assert numbers == list(range(1, len(numbers) + 1))


def test_nur_setzbare_klassen_bekommen_eine_ziffer() -> None:
    for row in class_tree():
        if row.number is not None:
            assert row.placeable is True


def test_die_ziffern_passen_zur_auswahl_ueber_die_tastatur() -> None:
    """Sonst waehlte die Taste eine andere Klasse als angezeigt."""
    engine, _ = prepared()
    mode = engine.edit_mode
    assert mode is not None
    numbered = {row.number: row.cls for row in class_tree() if row.number is not None}

    mode.select_class_at(2)  # entspricht der Ziffer 3

    assert mode.selected_class is numbered[3]


# ----------------------------------------------------------------------
# D1 bis D3 -- Methoden am Objekt
# ----------------------------------------------------------------------


def test_oeffentliche_methoden_werden_angezeigt() -> None:
    members = callable_members(Lorry())

    assert "honk" in members
    assert "init" in members


def test_methoden_mit_vorbelegtem_wert_zaehlen_dazu() -> None:
    assert "drive" in callable_members(Lorry())


def test_methoden_mit_pflichtwert_erscheinen_nicht() -> None:
    """Anforderung D3: Sie sind in dieser Ausbaustufe nicht vorgesehen."""
    assert "refuel" not in callable_members(Lorry())


def test_nicht_oeffentliche_methoden_erscheinen_nicht() -> None:
    assert "_hidden" not in callable_members(Lorry())


def test_bausteine_von_pyfoot_erscheinen_nicht() -> None:
    """Im Blick sind die Faehigkeiten, die im Unterricht besprochen werden."""
    members = callable_members(Lorry())

    assert "set_location" not in members
    assert "objects_at_offset" not in members


def test_nicht_vorhandene_methoden_werden_nicht_vorgetaeuscht() -> None:
    """Didaktische Auflage E2 -- die Anzeige entsteht allein aus der Klasse."""
    members = callable_members(Lorry())

    assert "turn_right" not in members
    assert all(hasattr(Lorry, name) for name in members)


def test_abfragen_zeigen_ihren_wert() -> None:
    assert call_member(Lorry(), "honk") == "honk() = 'tuut'"


def test_eigenschaften_lassen_sich_ebenfalls_abfragen() -> None:
    assert call_member(Lorry(), "wheels") == "wheels() = 4"


def test_eine_methode_ohne_rueckgabe_meldet_die_ausfuehrung() -> None:
    world = World(10, 10, cell_size=CELL)
    lorry = Lorry()
    world.add_object(lorry, 1, 1)

    assert call_member(lorry, "drive") == "drive() ausgefuehrt."


def test_ein_fehler_beim_aufruf_beendet_nichts() -> None:
    """Ein Probeaufruf darf das Programm nicht abbrechen."""
    result = call_member(Breaking(), "stall")

    assert "RuntimeError" in result
    assert "Der Motor ist aus." in result


# ----------------------------------------------------------------------
# Das Kontextmenue
# ----------------------------------------------------------------------


def test_das_menue_eines_objekts_zeigt_seine_methoden() -> None:
    engine, world = prepared()
    lorry = Lorry()
    world.add_object(lorry, 1, 1)

    engine.open_actor_menu(lorry, (40, 40))

    menu = engine.menu
    assert menu is not None
    labels = [entry.label for entry in menu.entries]
    assert "honk()" in labels
    assert "Entfernen" in labels
    assert "Quelltext öffnen" in labels


def test_ein_eintrag_laesst_sich_mit_der_maus_waehlen() -> None:
    engine, world = prepared()
    lorry = Lorry()
    world.add_object(lorry, 1, 1)
    engine.open_actor_menu(lorry, (40, 40))
    menu = engine.menu
    assert menu is not None

    index = [entry.label for entry in menu.entries].index("honk()")
    rect = menu._row_rect(index)
    menu.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": rect.center, "button": 1}
        )
    )

    assert "tuut" in engine.status


def test_ein_eintrag_laesst_sich_ueber_seine_ziffer_waehlen() -> None:
    """Anforderung C2."""
    called: list[str] = []
    menu = ContextMenu(
        "Probe",
        [
            MenuEntry("erster", lambda: called.append("erster")),
            MenuEntry("zweiter", lambda: called.append("zweiter")),
        ],
        (10, 10),
    )

    used, close = menu.handle_event(key(pygame.K_2))

    assert (used, close) == (True, True)
    assert called == ["zweiter"]


def test_ein_abgeschalteter_eintrag_bewirkt_nichts() -> None:
    called: list[str] = []
    menu = ContextMenu(
        "Probe", [MenuEntry("aus", lambda: called.append("x"), enabled=False)], (0, 0)
    )

    assert menu.choose(0) is False
    assert called == []


def test_esc_schliesst_nur_das_menue() -> None:
    menu = ContextMenu("Probe", [MenuEntry("eins", lambda: None)], (0, 0))

    used, close = menu.handle_event(key(pygame.K_ESCAPE))

    assert (used, close) == (True, True)


def test_esc_beendet_das_fenster_nicht_solange_ein_menue_offen_ist() -> None:
    engine, world = prepared()
    lorry = Lorry()
    world.add_object(lorry, 1, 1)
    engine.open_actor_menu(lorry, (40, 40))
    engine._running = True

    pygame.event.post(key(pygame.K_ESCAPE))
    engine._pump_events()

    assert engine.menu is None
    assert engine._running is True, "Das Fenster darf dabei offen bleiben."


def test_das_menue_bleibt_im_fenster() -> None:
    menu = ContextMenu("Probe", [MenuEntry("eins", lambda: None)], (10_000, 10_000))

    menu.fit_into(640, 480)

    assert menu.rect.right <= 640
    assert menu.rect.bottom <= 480


def test_das_menue_laesst_sich_ohne_bildschirm_zeichnen() -> None:
    """Auflage F2."""
    menu = ContextMenu("Probe", [MenuEntry("eins", lambda: None)], (0, 0))

    menu.render(pygame.Surface((300, 200)))


# ----------------------------------------------------------------------
# Die Texteingabe
# ----------------------------------------------------------------------


def test_die_eingabe_sammelt_zeichen() -> None:
    prompt = TextPrompt("Name:", lambda _: None)

    for letter in "Abc":
        prompt.handle_event(key(ord(letter), letter))

    assert prompt.text == "Abc"


def test_ruecktaste_loescht_ein_zeichen() -> None:
    prompt = TextPrompt("Name:", lambda _: None)
    prompt.handle_event(key(ord("A"), "A"))
    prompt.handle_event(key(pygame.K_BACKSPACE))

    assert prompt.text == ""


def test_eingabe_reicht_den_text_weiter() -> None:
    answers: list[str] = []
    prompt = TextPrompt("Name:", answers.append)
    for letter in "Ufo":
        prompt.handle_event(key(ord(letter), letter))

    used, close = prompt.handle_event(key(pygame.K_RETURN))

    assert (used, close) == (True, True)
    assert answers == ["Ufo"]


def test_leere_eingabe_reicht_nichts_weiter() -> None:
    answers: list[str] = []
    prompt = TextPrompt("Name:", answers.append)

    prompt.handle_event(key(pygame.K_RETURN))

    assert answers == []


def test_esc_bricht_die_eingabe_ab() -> None:
    answers: list[str] = []
    prompt = TextPrompt("Name:", answers.append)
    prompt.handle_event(key(ord("A"), "A"))

    used, close = prompt.handle_event(key(pygame.K_ESCAPE))

    assert (used, close) == (True, True)
    assert answers == []


# ----------------------------------------------------------------------
# B4 -- neue Unterklasse
# ----------------------------------------------------------------------


def test_die_vorlage_ist_gueltiges_python() -> None:
    ast.parse(codegen.render_subclass(Vehicle, "Ufo"))


def test_die_vorlage_schliesst_offene_methoden() -> None:
    text = codegen.render_subclass(Vehicle, "Ufo")

    assert "def init(self) -> None:" in text
    assert '"""Hier stehen die Anweisungen."""' in text


def test_die_vorlage_bindet_die_grundklasse_ein() -> None:
    text = codegen.render_subclass(Vehicle, "Ufo")

    assert f"from {Vehicle.__module__} import Vehicle" in text
    assert "class Ufo(Vehicle):" in text


def test_die_vorlage_ist_wie_die_einstiegsdatei_gebaut() -> None:
    """Aufbau wie `ships/normal_spaceship.py` -- inklusive `__all__`.

    Wer eine neue Klasse anlegt, soll dieselbe Datei vor sich haben wie am
    ersten Tag: Einfuhren oben, `__all__`, Klasse mit `__slots__`, und die
    Methode, in die geschrieben wird.
    """
    text = codegen.render_subclass(Vehicle, "Ufo")

    assert "from __future__ import annotations" in text
    assert '__all__ = ["Ufo"]' in text
    assert "class Ufo(Vehicle):" in text
    assert "__slots__ = ()" in text
    assert "def init(self) -> None:" in text


def test_auch_eine_fertige_grundklasse_bekommt_init() -> None:
    """Sonst entstuende beim Ableiten von `Lorry` eine Klasse ohne `init`.

    `Lorry` fuellt `init` bereits aus, ist also nicht abstrakt -- die Methode
    ist aber genau die, in die geschrieben wird.
    """
    text = codegen.render_subclass(Lorry, "Kipper")

    assert "def init(self) -> None:" in text


def test_der_rumpftext_passt_zur_methode() -> None:
    """Bei einer Welt wird nicht 'Anweisungen' geschrieben."""
    from pyfoot.editor.codegen import STUB_DOCSTRINGS

    assert STUB_DOCSTRINGS["prepare"] == "Hier wird die Welt aufgebaut."


def test_die_vorlage_traegt_slots() -> None:
    """`__slots__` wirkt nur, wenn es jede Klasse der Vererbungskette hat.

    Eine erzeugte Unterklasse ohne die Angabe holt das `__dict__` fuer alle
    Instanzen zurueck -- der Schutz waere damit auch fuer die Grundklassen
    aufgehoben. Wer ein eigenes Attribut braucht, traegt es dort ein.
    """
    text = codegen.render_subclass(Vehicle, "Ufo")

    assert "__slots__ = ()" in text


def test_die_erzeugte_klasse_hat_kein_dict(tmp_path: Path) -> None:
    """Gegenprobe an der wirklich eingebundenen Klasse, nicht nur am Text."""
    path = codegen.create_subclass(Vehicle, "Ufo", folder=tmp_path)
    created = codegen.import_class(path, "Ufo")

    assert not hasattr(created(), "__dict__")


def test_eine_datei_entsteht(tmp_path: Path) -> None:
    path = codegen.create_subclass(Vehicle, "Ufo", folder=tmp_path)

    assert path.name == "ufo.py"
    assert path.is_file()
    ast.parse(path.read_text(encoding="utf-8"))


def test_der_dateiname_wird_umgesetzt(tmp_path: Path) -> None:
    path = codegen.create_subclass(Vehicle, "FastLorry", folder=tmp_path)

    assert path.name == "fast_lorry.py"


def test_ein_ungueltiger_name_wird_abgewiesen(tmp_path: Path) -> None:
    with pytest.raises(codegen.SaveError, match="gueltiger Klassenname"):
        codegen.create_subclass(Vehicle, "3 Ufos", folder=tmp_path)


def test_ein_schluesselwort_wird_abgewiesen(tmp_path: Path) -> None:
    with pytest.raises(codegen.SaveError):
        codegen.create_subclass(Vehicle, "class", folder=tmp_path)


def test_ein_kleiner_anfangsbuchstabe_wird_abgewiesen(tmp_path: Path) -> None:
    with pytest.raises(codegen.SaveError, match="Grossbuchstaben"):
        codegen.create_subclass(Vehicle, "ufo", folder=tmp_path)


def test_eine_bestehende_datei_wird_nicht_ueberschrieben(tmp_path: Path) -> None:
    codegen.create_subclass(Vehicle, "Ufo", folder=tmp_path)

    with pytest.raises(codegen.SaveError, match="bereits eine Datei"):
        codegen.create_subclass(Vehicle, "Ufo", folder=tmp_path)


def test_die_neue_klasse_laesst_sich_verwenden(tmp_path: Path) -> None:
    """Anforderung B4: ohne Nacharbeit lauffaehig."""
    path = codegen.create_subclass(Vehicle, "Ufo", folder=tmp_path)
    namespace: dict[str, object] = {"__name__": "ufo_test"}

    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)

    created = namespace["Ufo"]
    assert isinstance(created, type) and issubclass(created, Vehicle)
    assert not getattr(created, "__abstractmethods__", frozenset())


# ----------------------------------------------------------------------
# B5 -- Bild zuweisen
# ----------------------------------------------------------------------

WITH_IMAGE_CALL = '''"""Eine Beispieldatei."""

from pyfoot import Actor, Image


class Comet(Actor):
    """Ein Akteur mit Bild."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.from_file("alt.png"))
'''

WITHOUT_IMAGE = '''"""Eine Beispieldatei."""

from pyfoot import Actor


class Comet(Actor):
    """Ein Akteur ohne Bild."""

    __slots__ = ()
'''


class Comet(Actor):
    """Die Klasse, der in den Tests ein Bild zugewiesen wird."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))


def test_ein_vorhandener_dateiname_wird_ersetzt(tmp_path: Path) -> None:
    path = tmp_path / "comet.py"
    path.write_text(WITH_IMAGE_CALL, encoding="utf-8")

    codegen.assign_image(Comet, "neu.png", path=path)

    text = path.read_text(encoding="utf-8")
    assert 'Image.from_file("neu.png")' in text
    assert "alt.png" not in text
    ast.parse(text)


def test_ohne_bildaufruf_entsteht_das_merkmal(tmp_path: Path) -> None:
    path = tmp_path / "comet.py"
    path.write_text(WITHOUT_IMAGE, encoding="utf-8")

    codegen.assign_image(Comet, "neu.png", path=path)

    text = path.read_text(encoding="utf-8")
    assert 'IMAGE = "neu.png"' in text
    ast.parse(text)


def test_ein_vorhandenes_merkmal_wird_fortgeschrieben(tmp_path: Path) -> None:
    path = tmp_path / "comet.py"
    path.write_text(WITHOUT_IMAGE, encoding="utf-8")
    codegen.assign_image(Comet, "erst.png", path=path)

    codegen.assign_image(Comet, "dann.png", path=path)

    text = path.read_text(encoding="utf-8")
    assert text.count("IMAGE =") == 1
    assert 'IMAGE = "dann.png"' in text


def test_vor_dem_zuweisen_entsteht_eine_sicherungskopie(tmp_path: Path) -> None:
    path = tmp_path / "comet.py"
    path.write_text(WITH_IMAGE_CALL, encoding="utf-8")

    backup = codegen.assign_image(Comet, "neu.png", path=path)

    assert backup.read_text(encoding="utf-8") == WITH_IMAGE_CALL


def test_das_merkmal_wird_beim_erzeugen_ausgewertet() -> None:
    """Ohne diese Auswertung waere das eingetragene Bild wirkungslos."""

    class Marked(Actor):
        __slots__ = ()
        IMAGE = "nicht_vorhanden.png"

    with pytest.raises(FileNotFoundError):
        Marked()


def test_ohne_merkmal_bleibt_das_bild_leer() -> None:
    class Plain(Actor):
        __slots__ = ()

    assert Plain().image.width == 1


# ----------------------------------------------------------------------
# B3 -- Quelltext oeffnen
# ----------------------------------------------------------------------


@pytest.fixture
def kein_editor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Schaltet **alle** Fundstellen ab, nicht nur den Suchpfad.

    Sonst findet der Test auf einem Rechner mit VS Code eines und startet es
    obendrein wirklich.
    """
    monkeypatch.delenv(source.EDITOR_VARIABLE, raising=False)
    monkeypatch.setattr("pyfoot.editor.source.shutil.which", lambda _: None)
    monkeypatch.setattr("pyfoot.editor.source._from_known_places", lambda: None)
    monkeypatch.setattr("pyfoot.editor.source._from_running_vscode", lambda: None)


def test_ohne_editor_wird_die_stelle_genannt(
    kein_editor: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pyfoot.editor.source.open_with_system", lambda _: False)

    message = source.open_in_editor(Path("beispiel.py"), 42)

    assert "beispiel.py" in message and "42" in message
    assert source.EDITOR_VARIABLE in message, "Der Ausweg muss genannt werden."


def test_ohne_editor_uebernimmt_die_standardanwendung(
    kein_editor: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Fall an der Schule: VS Code ist da, steht aber nicht im Suchpfad."""
    geoeffnet: list[Path] = []

    def merken(path: Path) -> bool:
        geoeffnet.append(path)
        return True

    monkeypatch.setattr("pyfoot.editor.source.open_with_system", merken)

    message = source.open_in_editor(Path("beispiel.py"), 42)

    assert geoeffnet == [Path("beispiel.py")]
    assert "geoeffnet" in message
    assert "42" in message, "Ohne Sprungmarke muss die Zeile dastehen."


def test_mit_vs_code_wird_der_editor_gestartet(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr("pyfoot.editor.source.find_editor", lambda: "code")
    monkeypatch.setattr(
        "pyfoot.editor.source.subprocess.Popen", lambda command: started.append(command)
    )

    message = source.open_in_editor(Path("beispiel.py"), 7)

    assert started and started[0][1:] == ["-r", "-g", "beispiel.py:7"]
    assert "geoeffnet" in message


def test_die_datei_landet_im_offenen_fenster() -> None:
    """`-r` oeffnet im schon laufenden VS Code statt in einem zweiten.

    Ohne den Schalter macht die CLI ein neues Fenster auf; laeuft noch keines,
    startet VS Code mit `-r` trotzdem eines. Beide Faelle sind damit gedeckt.
    """
    befehl = source.command_for("code.cmd", Path("beispiel.py"), 7)

    assert befehl == ["code.cmd", "-r", "-g", "beispiel.py:7"]


def test_ein_anderer_editor_bekommt_nur_die_datei() -> None:
    """`-r` und `-g` versteht nur VS Code.

    Ein ueber PYFOOT_EDITOR eingetragenes Notepad++ hielte `-r` sonst fuer
    eine zu oeffnende Datei und legte ein leeres Blatt dieses Namens an.
    """
    fremder = str(Path("C:/Tools/notepad++.exe"))

    befehl = source.command_for(fremder, Path("beispiel.py"), 7)

    assert befehl == [fremder, "beispiel.py"]


def test_auch_code_insiders_bekommt_die_schalter() -> None:
    befehl = source.command_for("code-insiders.cmd", Path("beispiel.py"), 7)

    assert befehl[1:] == ["-r", "-g", "beispiel.py:7"]


def test_das_laufende_vs_code_hat_vorrang_vor_dem_suchpfad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sonst landete die Datei in einer zweiten, zufaellig installierten Version."""
    installation = tmp_path / "VSCode"
    (installation / "bin").mkdir(parents=True)
    code_exe = installation / "Code.exe"
    code_exe.write_text("", encoding="utf-8")
    laufend = installation / "bin" / "code.cmd"
    laufend.write_text("", encoding="utf-8")
    monkeypatch.delenv(source.EDITOR_VARIABLE, raising=False)
    monkeypatch.setenv("VSCODE_GIT_ASKPASS_NODE", str(code_exe))
    anderes = str(Path("C:/anderes/code.cmd"))
    monkeypatch.setattr("pyfoot.editor.source.shutil.which", lambda _: anderes)

    assert source.find_editor() == str(laufend)


def test_die_eigene_angabe_hat_vorrang(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`PYFOOT_EDITOR` schlaegt alles andere -- der Ausweg fuer jede Schule."""
    eigener = tmp_path / "mein_editor.exe"
    eigener.write_text("", encoding="utf-8")
    monkeypatch.setenv(source.EDITOR_VARIABLE, str(eigener))
    monkeypatch.setattr("pyfoot.editor.source.shutil.which", lambda _: "code")

    assert source.find_editor() == str(eigener)


def test_eine_angabe_in_anfuehrungszeichen_wird_gelesen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Aus dem Explorer kopierte Pfade tragen oft Anfuehrungszeichen."""
    eigener = tmp_path / "mein editor.exe"
    eigener.write_text("", encoding="utf-8")
    monkeypatch.setenv(source.EDITOR_VARIABLE, f'"{eigener}"')

    assert source.find_editor() == str(eigener)


def test_ein_leerer_eintrag_wird_uebergangen(
    kein_editor: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(source.EDITOR_VARIABLE, "   ")

    assert source.find_editor() is None


def test_das_laufende_vs_code_wird_gefunden(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der Fall des entpackten VS Code: nicht im Suchpfad, aber gestartet.

    Absichtlich **ohne** die Vorrichtung `kein_editor` -- die schaltet gerade
    diese Suche ab, die hier geprueft werden soll.
    """
    installation = tmp_path / "VSCode"
    (installation / "bin").mkdir(parents=True)
    code_exe = installation / "Code.exe"
    code_exe.write_text("", encoding="utf-8")
    startbefehl = installation / "bin" / "code.cmd"
    startbefehl.write_text("", encoding="utf-8")
    monkeypatch.delenv(source.EDITOR_VARIABLE, raising=False)
    monkeypatch.setattr("pyfoot.editor.source.shutil.which", lambda _: None)
    monkeypatch.setattr("pyfoot.editor.source._from_known_places", lambda: None)
    monkeypatch.setenv("VSCODE_GIT_ASKPASS_NODE", str(code_exe))

    assert source.find_editor() == str(startbefehl)


def test_ein_fehlstart_wird_gemeldet(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(command: list[str]) -> None:
        raise OSError("geht nicht")

    monkeypatch.setattr("pyfoot.editor.source.find_editor", lambda: "code")
    monkeypatch.setattr("pyfoot.editor.source.subprocess.Popen", failing)

    message = source.open_in_editor(Path("beispiel.py"), 1)

    assert "liess sich nicht starten" in message


def test_die_engine_meldet_das_ergebnis(
    kein_editor: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, _ = prepared()
    monkeypatch.setattr("pyfoot.editor.source.open_with_system", lambda _: False)

    engine.open_source(Lorry)

    assert "Zeile" in engine.status


# ----------------------------------------------------------------------
# B3a -- Doppelklick oeffnet den Editor
# ----------------------------------------------------------------------


def sidebar_row(engine: Engine, wanted: type) -> pygame.Rect:
    """Liefert das Rechteck der Zeile, in der die Klasse steht.

    Der Baum enthaelt beim Lauf der gesamten Testsammlung mehr Klassen, als
    in die Anzeige passen. Deshalb wird gerollt, bis die gesuchte Zeile
    sichtbar ist.
    """
    sidebar = engine.sidebar
    assert sidebar is not None
    sidebar.render(pygame.Surface((sidebar.WIDTH, engine._panel_top())))

    for _ in range(len(sidebar.tree) + 1):
        for row, rect in sidebar.rows:
            if row.cls is wanted:
                return rect
        sidebar.scroll_by(1)
    raise AssertionError(f"{wanted.__name__} steht nicht in der Klassenanzeige.")


def sidebar_click(engine: Engine, rect: pygame.Rect, button: int = 1) -> bool:
    """Stellt einen Klick auf eine Zeile der Klassenanzeige nach."""
    sidebar = engine.sidebar
    assert sidebar is not None
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": (engine.sidebar_left() + rect.centerx, rect.centery), "button": button},
    )
    return sidebar.handle_event(event, engine.sidebar_left())


def test_doppelklick_oeffnet_die_quelldatei(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anforderung B3a."""
    engine, _ = prepared()
    geoeffnet: list[str] = []
    monkeypatch.setattr(
        Engine, "open_source", lambda self, target: geoeffnet.append(target.__name__)
    )
    rect = sidebar_row(engine, Lorry)

    sidebar_click(engine, rect)
    sidebar_click(engine, rect)

    assert geoeffnet == ["Lorry"]


def test_ein_einzelner_klick_oeffnet_nichts(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, _ = prepared()
    geoeffnet: list[str] = []
    monkeypatch.setattr(
        Engine, "open_source", lambda self, target: geoeffnet.append(target.__name__)
    )

    sidebar_click(engine, sidebar_row(engine, Lorry))

    assert geoeffnet == []


def test_ein_einzelner_klick_waehlt_weiterhin_aus() -> None:
    """Der Doppelklick darf die bisherige Auswahl nicht ersetzen."""
    engine, _ = prepared()
    mode = engine.edit_mode
    assert mode is not None

    sidebar_click(engine, sidebar_row(engine, Lorry))

    assert mode.selected_class is Lorry


def test_zwei_klicks_auf_verschiedene_klassen_sind_kein_doppelklick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, _ = prepared()
    geoeffnet: list[str] = []
    monkeypatch.setattr(
        Engine, "open_source", lambda self, target: geoeffnet.append(target.__name__)
    )

    sidebar_click(engine, sidebar_row(engine, Lorry))
    sidebar_click(engine, sidebar_row(engine, Breaking))

    assert geoeffnet == []


def test_ein_dritter_klick_oeffnet_nicht_erneut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sonst startete jeder weitere Klick eine neue Editorinstanz."""
    engine, _ = prepared()
    geoeffnet: list[str] = []
    monkeypatch.setattr(
        Engine, "open_source", lambda self, target: geoeffnet.append(target.__name__)
    )
    rect = sidebar_row(engine, Lorry)

    for _ in range(3):
        sidebar_click(engine, rect)

    assert geoeffnet == ["Lorry"]


def test_der_hinweis_auf_den_doppelklick_steht_im_fenster() -> None:
    engine, _ = prepared()
    sidebar = engine.sidebar
    assert sidebar is not None

    # Zeichnen darf ohne Bildschirm nicht scheitern (Auflage F2).
    sidebar.render(pygame.Surface((sidebar.WIDTH, engine._panel_top())))


# ----------------------------------------------------------------------
# B6 -- Objekt erzeugen
# ----------------------------------------------------------------------


def test_das_klassenmenue_bietet_das_erzeugen_an() -> None:
    """Anforderung B6 -- beschriftet mit dem Python-Ausdruck."""
    engine, _ = prepared()

    engine.open_class_menu(Lorry, (40, 40))

    menu = engine.menu
    assert menu is not None
    assert menu.entries[0].label == "Lorry() erzeugen"
    assert menu.entries[0].enabled is True


def test_das_erzeugen_setzt_ein_objekt_in_die_welt() -> None:
    engine, world = prepared()
    engine.open_class_menu(Lorry, (40, 40))
    menu = engine.menu
    assert menu is not None

    menu.choose(0)

    vorhanden: list[Actor] = world.objects()
    assert len([a for a in vorhanden if isinstance(a, Lorry)]) == 1


def test_das_erzeugte_objekt_ist_ausgewaehlt() -> None:
    """Damit es sich sofort verschieben oder entfernen laesst."""
    engine, world = prepared()
    mode = engine.edit_mode
    assert mode is not None

    engine.create_instance(Lorry)

    assert isinstance(mode.selected_actor, Lorry)


def test_ohne_mauszeiger_entsteht_das_objekt_in_der_mitte() -> None:
    engine, world = prepared()
    mode = engine.edit_mode
    assert mode is not None
    assert mode.hover is None

    created = mode.create_instance(Lorry)

    assert created is not None
    assert (created.x, created.y) == (world.width // 2, world.height // 2)


def test_unter_dem_mauszeiger_entsteht_das_objekt_dort() -> None:
    engine, world = prepared()
    mode = engine.edit_mode
    assert mode is not None
    left, top = engine.world_origin()
    mode.handle_event(
        pygame.event.Event(
            pygame.MOUSEMOTION,
            {"pos": (left + 3 * CELL + 5, top + 2 * CELL + 5), "buttons": (0, 0, 0)},
        )
    )

    created = mode.create_instance(Lorry)

    assert created is not None
    assert (created.x, created.y) == (3, 2)


def test_eine_nicht_erzeugbare_klasse_bietet_den_eintrag_abgeschaltet_an() -> None:
    """Abgeschaltet, nicht verborgen -- sonst bliebe unklar, warum er fehlt."""
    engine, _ = prepared()

    engine.open_class_menu(Vehicle, (40, 40))

    menu = engine.menu
    assert menu is not None
    assert menu.entries[0].label == "Vehicle() erzeugen"
    assert menu.entries[0].enabled is False


def test_ein_abgeschalteter_eintrag_erzeugt_nichts() -> None:
    engine, world = prepared()
    engine.open_class_menu(Vehicle, (40, 40))
    menu = engine.menu
    assert menu is not None
    vorher = world.number_of_objects()

    menu.choose(0)

    assert world.number_of_objects() == vorher


def test_eine_weltklasse_laesst_sich_nicht_erzeugen() -> None:
    engine, world = prepared()
    vorher = world.number_of_objects()

    engine.create_instance(World)

    assert world.number_of_objects() == vorher


def test_das_erzeugen_schaltet_den_bearbeitungsmodus_ein() -> None:
    engine, _ = prepared()
    mode = engine.edit_mode
    assert mode is not None
    mode.enable(False)

    engine.create_instance(Lorry)

    assert mode.enabled is True


def test_die_meldung_nennt_das_feld() -> None:
    engine, _ = prepared()

    engine.create_instance(Lorry)

    assert "Lorry() erzeugt" in engine.status


# ----------------------------------------------------------------------
# B4a -- die neue Klasse steht sofort zur Verfuegung
# ----------------------------------------------------------------------


def test_der_modulname_folgt_der_paketstruktur(tmp_path: Path) -> None:
    """Nur so greifen auch die Einfuhren innerhalb des Pakets."""
    paket = tmp_path / "beispiel" / "teile"
    paket.mkdir(parents=True)
    (tmp_path / "beispiel" / "__init__.py").write_text("", encoding="utf-8")
    (paket / "__init__.py").write_text("", encoding="utf-8")
    datei = paket / "ufo.py"
    datei.write_text("", encoding="utf-8")

    assert codegen.module_name_for(datei) == "beispiel.teile.ufo"


def test_eine_freistehende_datei_behaelt_ihren_namen(tmp_path: Path) -> None:
    datei = tmp_path / "ufo.py"
    datei.write_text("", encoding="utf-8")

    assert codegen.module_name_for(datei) == "ufo"


def test_die_neue_klasse_steht_sofort_im_baum(tmp_path: Path) -> None:
    """Anforderung B4a -- bis E7 erschien sie erst nach einem Neustart."""
    engine, _ = prepared()
    vorher = {row.cls.__name__ for row in class_tree()}
    assert "Zeppelin" not in vorher

    pfad = codegen.create_subclass(Vehicle, "Zeppelin", folder=tmp_path)
    codegen.import_class(pfad, "Zeppelin")

    nachher = {row.cls.__name__ for row in class_tree()}
    assert "Zeppelin" in nachher


def test_die_neue_klasse_haengt_unter_ihrer_grundklasse(tmp_path: Path) -> None:
    engine, _ = prepared()
    pfad = codegen.create_subclass(Vehicle, "Luftschiff", folder=tmp_path)
    codegen.import_class(pfad, "Luftschiff")

    zeilen = {row.cls.__name__: row for row in class_tree()}
    assert zeilen["Luftschiff"].depth == zeilen["Vehicle"].depth + 1
    assert zeilen["Luftschiff"].placeable is True


def test_die_neue_klasse_laesst_sich_sofort_setzen(tmp_path: Path) -> None:
    engine, world = prepared()
    mode = engine.edit_mode
    assert mode is not None
    pfad = codegen.create_subclass(Vehicle, "Ballon", folder=tmp_path)
    erzeugt = codegen.import_class(pfad, "Ballon")
    mode.refresh_classes()

    assert erzeugt in mode.classes
    engine.create_instance(erzeugt)
    vorhanden: list[Actor] = world.objects()
    assert any(type(a) is erzeugt for a in vorhanden)


def test_eine_unbrauchbare_datei_wird_gemeldet(tmp_path: Path) -> None:
    """Die Datei bleibt erhalten -- der Grund wird genannt."""
    kaputt = tmp_path / "kaputt.py"
    kaputt.write_text("das ist kein Python\n", encoding="utf-8")

    with pytest.raises(codegen.SaveError, match="laesst sich aber nicht einbinden"):
        codegen.import_class(kaputt, "Kaputt")

    assert kaputt.is_file()


def test_eine_datei_ohne_die_klasse_wird_gemeldet(tmp_path: Path) -> None:
    ohne = tmp_path / "ohne.py"
    ohne.write_text("wert = 1\n", encoding="utf-8")

    with pytest.raises(codegen.SaveError, match="keine Klasse namens"):
        codegen.import_class(ohne, "Fehlt")


# ----------------------------------------------------------------------
# D4 -- Zustand eines Objekts anzeigen
# ----------------------------------------------------------------------


def test_die_attribute_eines_objekts_werden_gelesen() -> None:
    from pyfoot.editor.menu import attributes

    namen = {name for name, _ in attributes(Lorry())}

    assert {"_x", "_y", "_rotation"} <= namen


def test_auch_eigene_attribute_erscheinen() -> None:
    from pyfoot.editor.menu import attributes

    class Tanker(Vehicle):
        __slots__ = ("fuel",)

        def __init__(self) -> None:
            super().__init__()
            self.fuel = 42

        def init(self) -> None:
            pass

    werte = dict(attributes(Tanker()))
    assert werte["fuel"] == "42"


def test_lange_werte_werden_gekuerzt() -> None:
    from pyfoot.editor.menu import attributes

    class Schwatzhaft(Vehicle):
        __slots__ = ("text",)

        def __init__(self) -> None:
            super().__init__()
            self.text = "x" * 200

        def init(self) -> None:
            pass

    werte = dict(attributes(Schwatzhaft()))
    assert len(werte["text"]) <= 30


def test_der_zustand_wird_bei_jedem_zeichnen_neu_gelesen() -> None:
    """Anforderung D4: Beim Einzelschritt soll man den Werten zusehen."""
    from pyfoot.editor.menu import Inspector

    world = World(10, 10, cell_size=CELL)
    lorry = Lorry()
    world.add_object(lorry, 1, 1)
    inspector = Inspector(lorry, (10, 10))

    vorher = dict(inspector.rows())
    lorry.set_location(7, 3)
    nachher = dict(inspector.rows())

    assert vorher["_x"] == "1"
    assert nachher["_x"] == "7"


def test_das_objektmenue_bietet_das_inspizieren_an() -> None:
    engine, world = prepared()
    lorry = Lorry()
    world.add_object(lorry, 1, 1)

    engine.open_actor_menu(lorry, (40, 40))

    menu = engine.menu
    assert menu is not None
    assert "Inspizieren" in [entry.label for entry in menu.entries]


def test_das_inspizieren_oeffnet_die_anzeige() -> None:
    engine, world = prepared()
    lorry = Lorry()
    world.add_object(lorry, 1, 1)
    engine.open_actor_menu(lorry, (40, 40))
    menu = engine.menu
    assert menu is not None

    menu.choose([e.label for e in menu.entries].index("Inspizieren"))

    assert engine.inspector is not None
    assert engine.inspector.target is lorry


def test_esc_schliesst_die_anzeige() -> None:
    from pyfoot.editor.menu import Inspector

    inspector = Inspector(Lorry(), (10, 10))

    used, close = inspector.handle_event(key(pygame.K_ESCAPE))

    assert (used, close) == (True, True)


def test_ein_klick_in_die_anzeige_schliesst_sie() -> None:
    from pyfoot.editor.menu import Inspector

    inspector = Inspector(Lorry(), (10, 10))
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": inspector.rect.center, "button": 1}
    )

    used, close = inspector.handle_event(event)

    assert (used, close) == (True, True)


def test_die_bedienleiste_bleibt_waehrenddessen_benutzbar() -> None:
    """Sonst liesse sich nicht weiterschalten und dabei zusehen (D4)."""
    from pyfoot.editor.menu import Inspector

    inspector = Inspector(Lorry(), (10, 10))

    used, close = inspector.handle_event(key(pygame.K_SPACE))

    assert (used, close) == (False, False)


def test_ein_klick_daneben_laeuft_durch() -> None:
    from pyfoot.editor.menu import Inspector

    inspector = Inspector(Lorry(), (200, 200))
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (5, 5), "button": 1}
    )

    used, close = inspector.handle_event(event)

    assert (used, close) == (False, False)


def test_die_anzeige_bleibt_im_fenster() -> None:
    from pyfoot.editor.menu import Inspector

    inspector = Inspector(Lorry(), (10_000, 10_000))

    inspector.fit_into(640, 480)

    assert inspector.rect.right <= 640
    assert inspector.rect.bottom <= 480


def test_die_anzeige_laesst_sich_ohne_bildschirm_zeichnen() -> None:
    """Auflage F2."""
    from pyfoot.editor.menu import Inspector

    Inspector(Lorry(), (0, 0)).render(pygame.Surface((400, 400)))


# ----------------------------------------------------------------------
# B7 -- Welt wechseln
# ----------------------------------------------------------------------


class Halle(World):
    """Eine Welt fuer den Weltwechsel."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(12, 12, cell_size=CELL)


class Lager(World):
    """Eine Welt mit Wahlmoeglichkeit im Konstruktor."""

    __slots__ = ("breit",)

    def __init__(self, breit: bool = True) -> None:
        self.breit = breit
        super().__init__(12 if breit else 6, 12, cell_size=CELL)


class Werft(World):
    """Eine zweite Welt, die ihr eigenes Objekt mitbringt."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(8, 8, cell_size=CELL)
        self.add_object(Lorry(), 1, 1)


def test_das_menue_einer_weltklasse_bietet_das_anzeigen_an() -> None:
    engine, _ = prepared()

    engine.open_class_menu(Halle, (40, 40))

    menu = engine.menu
    assert menu is not None
    assert menu.entries[0].label == "Halle() anzeigen"
    assert menu.entries[0].enabled is True


def test_der_weltwechsel_zeigt_die_neue_welt() -> None:
    engine, alte = prepared()

    engine.switch_world(Halle)

    assert engine.world is not alte
    assert isinstance(engine.world, Halle)


def test_das_raumschiff_wird_nicht_mitgenommen() -> None:
    """Entscheidung des Auftraggebers: Jede Welt bringt ihr eigenes mit.

    Das richtige Schiff in die richtige Welt zu setzen ist selbst Lerninhalt.
    """
    engine, alte = prepared()
    alte.add_object(Lorry(), 2, 2)

    engine.switch_world(Halle)

    assert engine.world.number_of_objects() == 0


def test_die_neue_welt_bringt_ihre_eigenen_objekte_mit() -> None:
    engine, _ = prepared()

    engine.switch_world(Werft)

    vorhanden: list[Actor] = engine.world.objects()
    assert [type(a).__name__ for a in vorhanden] == ["Lorry"]


def test_die_titelzeile_folgt_dem_weltwechsel() -> None:
    engine, _ = prepared()

    engine.switch_world(Halle)

    assert engine.caption().endswith("— Halle")


def test_das_fenster_folgt_der_neuen_weltgroesse() -> None:
    engine, _ = prepared()

    engine.switch_world(Halle)

    assert engine._window_size()[1] == 12 * CELL + 82


def test_eine_akteursklasse_wird_nicht_als_welt_gewechselt() -> None:
    engine, alte = prepared()

    engine.switch_world(Lorry)

    assert engine.world is alte


def test_eine_welt_die_werte_braucht_ist_abgeschaltet() -> None:
    class Bedarfswelt(World):
        __slots__ = ()

        def __init__(self, breite: int) -> None:
            super().__init__(breite, 5, cell_size=CELL)

    engine, _ = prepared()
    engine.open_class_menu(Bedarfswelt, (40, 40))

    menu = engine.menu
    assert menu is not None
    assert menu.entries[0].enabled is False


def test_ein_fehler_beim_erzeugen_wird_gemeldet() -> None:
    class Kaputt(World):
        __slots__ = ()

        def __init__(self) -> None:
            raise RuntimeError("geht nicht")

    engine, alte = prepared()

    engine.switch_world(Kaputt)

    assert "geht nicht" in engine.status
    assert engine.world is alte


# ----------------------------------------------------------------------
# B8 -- Klasse loeschen
# ----------------------------------------------------------------------


def eigener_ordner(tmp_path: Path) -> Path:
    """Meldet einen Ordner fuer eigene Klassen an und liefert ihn."""
    ordner = tmp_path / "meine"
    ordner.mkdir(exist_ok=True)
    (ordner / "__init__.py").write_text("", encoding="utf-8")
    codegen.set_class_folders(actors=ordner, worlds=ordner)
    return ordner


def test_eine_selbst_angelegte_klasse_laesst_sich_loeschen(
    tmp_path: Path,
) -> None:
    engine, _ = prepared()
    ordner = eigener_ordner(tmp_path)
    pfad = codegen.create_subclass(Vehicle, "Segler")
    erzeugt = codegen.import_class(pfad, "Segler")

    assert pfad.parent == ordner
    assert codegen.can_delete(erzeugt)[0] is True

    backup = codegen.delete_class(erzeugt)

    assert not pfad.exists()
    assert backup.is_file(), "Auflage F3: keine Datei geht verloren."


def test_eine_geloeschte_klasse_verschwindet_aus_der_anzeige(
    tmp_path: Path,
) -> None:
    engine, _ = prepared()
    eigener_ordner(tmp_path)
    pfad = codegen.create_subclass(Vehicle, "Kutter")
    erzeugt = codegen.import_class(pfad, "Kutter")
    assert "Kutter" in [row.cls.__name__ for row in class_tree()]

    codegen.delete_class(erzeugt)

    assert "Kutter" not in [row.cls.__name__ for row in class_tree()]


def test_der_kursinhalt_laesst_sich_nicht_loeschen(tmp_path: Path) -> None:
    """Der Kern von B8: eine Erlaubnisliste, keine Verbotsliste."""
    eigener_ordner(tmp_path)

    erlaubt, grund = codegen.can_delete(Vehicle)

    assert erlaubt is False
    assert "vorgegebenen Teil" in grund


def test_eine_klasse_mit_mitbewohnern_bleibt_stehen(tmp_path: Path) -> None:
    """In Python teilen sich mehrere Klassen eine Datei -- in Java nicht."""
    ordner = eigener_ordner(tmp_path)
    datei = ordner / "zwei.py"
    datei.write_text(
        "class Eins:\n    pass\n\n\nclass Zwei:\n    pass\n", encoding="utf-8"
    )
    geladen = codegen.import_class(datei, "Eins")

    erlaubt, grund = codegen.can_delete(geladen)

    assert erlaubt is False
    assert "Zwei" in grund
    assert datei.is_file()


def test_ohne_angemeldeten_ordner_ist_nichts_loeschbar() -> None:
    codegen.set_class_folders(actors=None, worlds=None)
    codegen._actor_folder = None
    codegen._world_folder = None

    erlaubt, grund = codegen.can_delete(Vehicle)

    assert erlaubt is False
    assert "kein Ordner" in grund


def test_das_loeschen_fragt_erst_nach(tmp_path: Path) -> None:
    engine, _ = prepared()
    eigener_ordner(tmp_path)
    pfad = codegen.create_subclass(Vehicle, "Barke")
    erzeugt = codegen.import_class(pfad, "Barke")

    engine.delete_class(erzeugt)

    assert pfad.is_file(), "Der erste Druck darf noch nichts loeschen."
    assert "wirklich entfernen" in engine.status

    engine.delete_class(erzeugt)
    assert not pfad.exists()


def test_eine_geschuetzte_klasse_meldet_den_grund(tmp_path: Path) -> None:
    engine, _ = prepared()
    eigener_ordner(tmp_path)

    engine.delete_class(Vehicle)

    assert "laesst sich nicht loeschen" in engine.status


def test_objekte_der_klasse_verlassen_vorher_die_welt(tmp_path: Path) -> None:
    engine, world = prepared()
    eigener_ordner(tmp_path)
    pfad = codegen.create_subclass(Vehicle, "Floss")
    erzeugt = codegen.import_class(pfad, "Floss")
    engine.create_instance(erzeugt)
    assert world.number_of_objects() == 1

    engine.delete_class(erzeugt)
    engine.delete_class(erzeugt)

    assert world.number_of_objects() == 0


def test_das_menue_zeigt_den_eintrag_abgeschaltet(tmp_path: Path) -> None:
    engine, _ = prepared()
    eigener_ordner(tmp_path)

    engine.open_class_menu(Vehicle, (40, 40))

    menu = engine.menu
    assert menu is not None
    loeschen = [e for e in menu.entries if e.label == "Löschen"]
    assert loeschen and loeschen[0].enabled is False


# ----------------------------------------------------------------------
# B6a -- Konstruktor mit Werten
# ----------------------------------------------------------------------


class Fass(Vehicle):
    """Ein Akteur mit einem Wert im Konstruktor."""

    __slots__ = ("_fuellung",)

    def __init__(self, fuellung: float = 0.5) -> None:
        super().__init__()
        self._fuellung = fuellung

    def init(self) -> None:
        pass

    def construction_code(self) -> str:
        return f"Fass({self._fuellung})"


def test_ein_konstruktor_ohne_werte_wird_nicht_abgefragt() -> None:
    from pyfoot.editor.mode import constructor_values

    assert constructor_values(Lorry) is None


def test_ein_konstruktor_mit_vorbelegung_wird_abgefragt() -> None:
    from pyfoot.editor.mode import constructor_values

    assert constructor_values(Fass) == [("fuellung", 0.5)]


def test_ein_konstruktor_mit_objekt_wird_nicht_abgefragt() -> None:
    """Ein Bild laesst sich nicht als Text eintippen."""
    from pyfoot.editor.mode import constructor_values

    class MitBild(Vehicle):
        __slots__ = ()

        def __init__(self, bild: Image = Image.blank(2, 2)) -> None:
            super().__init__()

        def init(self) -> None:
            pass

    assert constructor_values(MitBild) is None


def test_das_menue_kuendigt_die_abfrage_an() -> None:
    engine, _ = prepared()

    engine.open_class_menu(Fass, (40, 40))

    menu = engine.menu
    assert menu is not None
    assert menu.entries[0].label == "Fass(…) erzeugen"


def test_die_abfrage_ist_mit_den_vorgaben_vorbelegt() -> None:
    """Ein Druck auf die Eingabetaste uebernimmt sie dann unveraendert."""
    engine, _ = prepared()

    engine.create_instance(Fass)

    prompt = engine.prompt
    assert prompt is not None
    assert prompt.text == "0.5"
    assert "fuellung" in prompt.question


def test_ein_eingegebener_wert_landet_im_objekt() -> None:
    engine, world = prepared()
    engine.create_instance(Fass)
    prompt = engine.prompt
    assert prompt is not None

    prompt.handle_event(key(pygame.K_BACKSPACE))
    prompt.handle_event(key(ord("9"), "9"))
    prompt.handle_event(key(pygame.K_RETURN))

    vorhanden: list[Actor] = world.objects()
    faesser = [a for a in vorhanden if isinstance(a, Fass)]
    assert len(faesser) == 1
    assert faesser[0].construction_code() == "Fass(0.9)"


def test_ein_unsinniger_wert_wird_abgewiesen() -> None:
    engine, world = prepared()

    engine._place_new(Fass, "keine Zahl")

    assert "keine gültige Werteangabe" in engine.status
    assert world.number_of_objects() == 0


def test_ein_falscher_typ_wird_gemeldet_statt_zu_stuerzen() -> None:
    class Streng(Vehicle):
        __slots__ = ()

        def __init__(self, zahl: int = 1) -> None:
            if not isinstance(zahl, int):
                raise TypeError("zahl muss eine ganze Zahl sein")
            super().__init__()

        def init(self) -> None:
            pass

    engine, world = prepared()

    engine._place_new(Streng, "'Text'")

    assert "TypeError" in engine.status
    assert world.number_of_objects() == 0


def test_eingetippter_code_wird_nicht_ausgefuehrt() -> None:
    """Gelesen werden nur Literale -- kein `eval`."""
    engine, world = prepared()

    engine._place_new(Fass, "__import__('os').getcwd()")

    assert "keine gültige Werteangabe" in engine.status
    assert world.number_of_objects() == 0


# ----------------------------------------------------------------------
# D5 -- Attribute bearbeiten
# ----------------------------------------------------------------------


def test_nur_gesicherte_werte_sind_bearbeitbar() -> None:
    """Der Kern von D5: bearbeitbar ist, was im Quelltext landet."""
    from pyfoot.editor.menu import editable_attributes

    assert editable_attributes(Fass(0.5)) == {"_fuellung"}


def test_ein_akteur_ohne_werte_hat_nichts_bearbeitbares() -> None:
    from pyfoot.editor.menu import editable_attributes

    assert editable_attributes(Lorry()) == set()


def test_die_lage_gehoert_nicht_dazu() -> None:
    """Sie wird durch Ziehen geaendert (A3), nicht durch Eintippen."""
    from pyfoot.editor.menu import editable_attributes

    world = World(10, 10, cell_size=CELL)
    fass = Fass(0.25)
    world.add_object(fass, 3, 4)

    veraenderbar = editable_attributes(fass)
    assert "_x" not in veraenderbar
    assert "_y" not in veraenderbar


def test_ein_teilstueck_zaehlt_nicht_als_treffer() -> None:
    """Die 5 aus einem Zaehler steckt sonst schon in `Fass(0.5)`."""
    from pyfoot.editor.menu import editable_attributes

    class MitZaehler(Fass):
        __slots__ = ("_zaehler",)

        def __init__(self) -> None:
            super().__init__(0.5)
            self._zaehler = 5

    assert editable_attributes(MitZaehler()) == {"_fuellung"}


def test_ein_wert_laesst_sich_aendern() -> None:
    engine, _ = prepared()
    fass = Fass(0.5)

    engine.set_attribute(fass, "_fuellung", "0.9")

    assert fass.construction_code() == "Fass(0.9)"
    assert "im Quelltext" in engine.status


def test_ein_geschuetztes_attribut_bleibt_unveraendert() -> None:
    engine, world = prepared()
    fass = Fass(0.5)
    world.add_object(fass, 2, 2)

    engine.set_attribute(fass, "_x", "7")

    assert fass.x == 2
    assert "lässt sich nicht ändern" in engine.status


def test_ein_anderer_typ_wird_abgewiesen() -> None:
    engine, _ = prepared()
    fass = Fass(0.5)

    engine.set_attribute(fass, "_fuellung", "'viel'")

    assert fass._fuellung == 0.5
    assert "erwartet float" in engine.status


def test_eine_ganze_zahl_gilt_als_kommazahl() -> None:
    engine, _ = prepared()
    fass = Fass(0.5)

    engine.set_attribute(fass, "_fuellung", "1")

    assert fass._fuellung == 1


def test_unsinn_wird_abgewiesen() -> None:
    engine, _ = prepared()
    fass = Fass(0.5)

    engine.set_attribute(fass, "_fuellung", "= 3")

    assert fass._fuellung == 0.5
    assert "kein gültiger Wert" in engine.status


def test_ein_klick_auf_einen_bearbeitbaren_wert_fragt_nach() -> None:
    from pyfoot.editor.menu import Inspector

    engine, world = prepared()
    fass = Fass(0.5)
    world.add_object(fass, 1, 1)
    engine.open_inspector(fass, (10, 10))
    inspector = engine.inspector
    assert inspector is not None

    zeile = [n for n, _ in inspector.rows()].index("_fuellung")
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": inspector.row_rect(zeile).center, "button": 1}
    )
    used, close = inspector.handle_event(event)

    assert (used, close) == (True, False), "Die Anzeige bleibt dabei stehen."
    assert engine.prompt is not None
    assert engine.prompt.text == "0.5"


def test_ein_klick_auf_einen_festen_wert_schliesst_die_anzeige() -> None:
    from pyfoot.editor.menu import Inspector

    engine, world = prepared()
    fass = Fass(0.5)
    world.add_object(fass, 1, 1)
    engine.open_inspector(fass, (10, 10))
    inspector = engine.inspector
    assert inspector is not None

    zeile = [n for n, _ in inspector.rows()].index("_rotation")
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": inspector.row_rect(zeile).center, "button": 1}
    )
    used, close = inspector.handle_event(event)

    assert (used, close) == (True, True)


# ----------------------------------------------------------------------
# Die Oberflaeche darf die Ereignisschleife nicht weiterdrehen
# ----------------------------------------------------------------------


class Hangar(World):
    """Eine Welt, die im Konstruktor selbst ein Raumschiff einsetzt.

    Genau das tut `Level0` im Basisprojekt -- und genau daran blieb der
    Weltwechsel haengen.
    """

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(8, 8, cell_size=CELL)
        # `add_object` ruft `set_location`; bei einem ScriptActor ist das mit
        # `redraws` gekennzeichnet.
        self.add_object(Lorry(), 1, 1)


def zaehlende_schleife(
    monkeypatch: pytest.MonkeyPatch, engine: Engine
) -> list[int]:
    """Zaehlt Durchlaeufe der Ereignisschleife und verhindert ein Haengen.

    Ohne die Entpausierung liefe ein Test, der den Fehler ausloest, endlos.
    """
    zaehler = [0]

    def pump(self: Engine) -> None:
        zaehler[0] += 1
        self._paused = False

    monkeypatch.setattr(Engine, "_pump_events", pump)
    return zaehler


def test_ein_weltwechsel_dreht_die_schleife_nicht_weiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Fehler, den der Auftraggeber gemeldet hat.

    Setzt die neue Welt in ihrem Konstruktor ein Raumschiff ein, lief frueher
    mitten im Konstruktor die Ereignisschleife an. Bei angehaltener
    Simulation blieb sie dort stehen -- der Wechsel schien wirkungslos.
    """
    engine, _ = prepared()
    engine._running = True
    engine._started = True
    assert engine.is_paused() is True
    zaehler = zaehlende_schleife(monkeypatch, engine)

    engine.switch_world(Hangar)

    assert zaehler[0] == 0, "Die Oberflaeche hat die Ereignisschleife weitergedreht."
    assert isinstance(engine.world, Hangar)
    assert engine.is_paused() is True, "Der Wechsel darf die Pause nicht aufheben."


def test_ein_raumschiff_setzen_dreht_die_schleife_nicht_weiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dasselbe beim Setzen mit der Maus -- derselbe Weg ueber `set_location`."""
    engine, world = prepared()
    engine._running = True
    engine._started = True
    mode = engine.edit_mode
    assert mode is not None
    zaehler = zaehlende_schleife(monkeypatch, engine)

    mode.create_instance(Lorry)

    assert zaehler[0] == 0
    assert world.number_of_objects() == 1


def test_die_sperre_wird_danach_wieder_aufgehoben() -> None:
    """Sonst reagierte das Fenster anschliessend gar nicht mehr."""
    engine, _ = prepared()

    with engine.suspended():
        assert engine._suspended is True

    assert engine._suspended is False


def test_die_sperre_vertraegt_verschachtelung() -> None:
    engine, _ = prepared()

    with engine.suspended():
        with engine.suspended():
            pass
        assert engine._suspended is True, "Die aeussere Sperre gilt weiter."

    assert engine._suspended is False


def test_schuelercode_dreht_die_schleife_weiterhin_weiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gegenprobe: Die Sperre gilt nur fuer die Oberflaeche."""
    engine, world = prepared()
    lorry = Lorry()
    # Erst einsetzen, dann die Simulation als laufend kennzeichnen: Sonst
    # bliebe schon das Einsetzen in der Pause stehen -- genau der Fehler,
    # um den es hier geht.
    world.add_object(lorry, 1, 1)
    engine._running = True
    engine._started = True
    zaehler = zaehlende_schleife(monkeypatch, engine)

    lorry.move()

    assert zaehler[0] > 0, "Der Schuelercode muss das Fenster bedienbar halten."


def test_eine_welt_mit_werten_fragt_vor_dem_anzeigen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anforderung B6a gilt auch fuer Welten.

    Sonst waere eine Welt mit Wahlmoeglichkeit -- etwa die Binaerzahl mit
    fester statt schwankender Stellenzahl -- ueber die Oberflaeche nur in
    ihrer Vorgabeversion erreichbar.
    """
    engine, _ = prepared()

    engine.open_class_menu(Lager, (40, 40))
    menu = engine.menu
    assert menu is not None
    assert menu.entries[0].label == "Lager(…) anzeigen"

    engine.switch_world(Lager)

    prompt = engine.prompt
    assert prompt is not None, "Es muss nach den Werten gefragt werden."
    assert prompt.text == "True", "Die Vorgabe steht schon da."


def eintippen(prompt: TextPrompt, text: str) -> None:
    """Loescht die Vorgabe und tippt den Text ein, wie es ein Mensch taete."""
    for _ in range(len(prompt.text)):
        prompt.handle_event(key(pygame.K_BACKSPACE))
    for letter in text:
        prompt.handle_event(key(ord(letter), letter))
    prompt.handle_event(key(pygame.K_RETURN))


def test_der_eingegebene_wert_erreicht_die_welt() -> None:
    engine, _ = prepared()

    engine.switch_world(Lager)
    prompt = engine.prompt
    assert prompt is not None
    eintippen(prompt, "False")

    assert isinstance(engine.world, Lager)
    assert engine.world.breit is False
    assert engine.world.width == 6


def test_die_vorgabe_wird_unveraendert_uebernommen() -> None:
    """Ein Druck auf die Eingabetaste genuegt (Anforderung B6a)."""
    engine, _ = prepared()

    engine.switch_world(Lager)
    prompt = engine.prompt
    assert prompt is not None
    prompt.handle_event(key(pygame.K_RETURN))

    assert isinstance(engine.world, Lager)
    assert engine.world.breit is True


def test_eine_unlesbare_werteangabe_wechselt_die_welt_nicht() -> None:
    engine, alte = prepared()

    engine.switch_world(Lager)
    prompt = engine.prompt
    assert prompt is not None
    eintippen(prompt, "kein Literal")

    assert engine.world is alte
    assert "Werteangabe" in engine.status
