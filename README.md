# PyFoot

Eine Lernumgebung fuer den Programmierunterricht: eine Gitterwelt auf Basis von
pygame, in der Akteure stehen und sich bewegen. Konzeptionell angeregt von
**Greenfoot**, aber eigenstaendig geschrieben.

> Dies ist **Teil 1 von drei**. Teil 2 ist das Basisprojekt
> [pyfoot-space](https://github.com/SAE-GMO/pyfoot-space), Teil 3 die
> Kursdokumentation mit Arbeitsblaettern (privat, auf Anfrage).

## Was PyFoot ist -- und was nicht

PyFoot ist **themenfrei**. Es kennt Akteure, Welten, Bilder und Farben, aber
weder Raumschiffe noch Unterrichtsaufgaben. Wer hier liest, soll nicht erkennen,
dass es einen Weltraumkurs gibt.

## Idee

```python
from pyfoot import ScriptActor, World, run, set_world


class Probe(ScriptActor):
    def init(self) -> None:
        self.move()
        self.turn(90)
        self.move()


world = World(8, 8)
world.add_object(Probe(), 0, 0)
set_world(world)
run()
```

Der Ablauf ist sichtbar verlangsamt, sodass sich der Weg mitverfolgen laesst.

## Warum das ohne Threads funktioniert

pygame besitzt keine eigene Ereignisschleife im Hintergrund. Ein blockierendes
`init()` mit Wartezeiten wuerde das Fenster daher normalerweise einfrieren.
PyFoot loest das einthreadig: Jede veraendernde Aktion ist mit `@redraws`
gekennzeichnet und dreht nach ihrer Ausfuehrung die Ereignisschleife einen
Schritt weiter -- Ereignisse abholen, neu zeichnen, Schrittdauer abwarten.

Das ist gegenueber einem Arbeitsthread im Vorteil, weil Haltepunkte im Debugger
normal funktionieren, Ausnahmen mit korrekter Rueckverfolgung auf die
Schuelerzeile zeigen und keine Sperren gegen Wettlaufsituationen noetig sind.

**Bekannte Grenze:** Lange reine Rechenschleifen ohne Aktion loesen kein
Neuzeichnen aus; das Fenster reagiert dann waehrenddessen nicht. Fuer diesen
Fall gibt es `update_screen()`, das sich von Hand aufrufen laesst.

## Module

| Modul | Aufgabe |
| --- | --- |
| `engine.py` | Fenster, Ereignisschleife, Ausfuehrungsmodell, Taktung |
| `world.py` | Gitterwelt, Akteursverwaltung, Zeichnen |
| `actor.py` | `Actor`, `ScriptActor`, Richtungskonstanten |
| `image.py` | Bilder laden, spiegeln, drehen, Text als Bild |
| `color.py` | Farben |
| `input.py` | Maus- und Tastatureingabe |
| `diagram.py` | PlantUML-Klassendiagramme aus dem Quelltext |
| `editor/panel.py` | Bedienleiste unter der Welt |
| `editor/sidebar.py` | Klassenbaum am rechten Rand |
| `editor/mode.py` | Bearbeitungsmodus: setzen, verschieben, entfernen |
| `editor/menu.py` | Kontextmenue und Texteingabe |
| `editor/codegen.py` | Quelltext schreiben: Weltaufbau, Unterklasse, Bild |
| `editor/source.py` | Quelldateien im Editor oeffnen |

## Die Oberflaeche

Die Oberflaeche ist eine **Ergaenzung, kein Ersatz**. Ohne ausdrueckliches
Einschalten verhaelt sich PyFoot unveraendert, und jedes Programm laeuft
weiterhin von der Kommandozeile.

### Das Fenster

Das Fenster laesst sich in der Groesse ziehen und maximieren. Die
Bedienleiste haengt dabei am unteren Rand, die Klassenanzeige am rechten; die
Welt steht mittig in der Flaeche, die uebrig bleibt, und wird beschnitten,
wenn das Fenster kleiner ist als sie.

**Eine von Hand gewaehlte Groesse bleibt erhalten** -- auch wenn eine andere
Welt angezeigt wird. Solange nicht von Hand veraendert wurde, richtet sich
das Fenster nach der Welt.

### Die Bedienleiste

Unter der Welt laesst sich eine Leiste einblenden, mit der sich das Programm
anhalten, Aktion fuer Aktion weiterschalten und zuruecksetzen laesst.

```python
from pyfoot import enable_ui

enable_ui()        # vor set_world aufrufen
```

Wer die Oberflaeche einschalten will, ohne eine Datei zu aendern, setzt die
Umgebungsvariable `PYFOOT_UI`:

```bash
$env:PYFOOT_UI = "1"
```

| Schaltflaeche | Taste | Wirkung |
| --- | --- | --- |
| Start / Pause | `Leertaste` | anhalten und fortsetzen, auch mitten in `init` |
| Durchlauf | `D` | ein vollstaendiger Act-Durchlauf |
| Schritt | `S` | genau eine Aktion der Anweisungsfolge |
| Zuruecksetzen | `R` | Ausgangslage wiederherstellen |
| Tempo | `+` / `-` | Schrittdauer einstellen |

Jede Funktion ist mit der Maus **und** ueber die Tastatur erreichbar.
Ausgegraute Schaltflaechen bewirken im aktuellen Zustand nichts.

Dass Anhalten und Einzelschritt ohne zweiten Thread mitten in eine laufende
`init` greifen, ist dieselbe Eigenschaft wie oben: Der Wartepunkt liegt in
`update_screen`, das nach jeder Aktion ohnehin durchlaufen wird.

`Zuruecksetzen` stellt die Ausgangslage aus einer Momentaufnahme wieder her.
Der Zustand innerhalb eigener Akteursklassen bleibt dabei erhalten. Wer die
Welt vollstaendig neu aufbauen will, setzt eine Fabrik:

```python
get_engine().world_factory = lambda: MyWorld()
```

### Der Klassenbaum

Rechts stehen die Klassen des laufenden Programms als Vererbungsbaum, zuerst
die Akteure, dann die Welten. Die Einrueckung zeigt, wer von wem erbt.

Setzen laesst sich nur, was ohne Werte erzeugbar ist -- diese Klassen tragen
eine Ziffer und ihr Bild. Abstrakte Klassen und die Bauteile von PyFoot
stehen ebenfalls im Baum, aber blass: Sie zeigen die Herkunft, sind aber
keine Spielfiguren.

### Welten bearbeiten

`Bearbeiten` schaltet den Bearbeitungsmodus ein; danach gehoert der
Weltausschnitt der Maus.

| Bedienung | Taste | Wirkung |
| --- | --- | --- |
| Bearbeiten | `B` | Bearbeitungsmodus ein und aus |
| Klick auf eine Klasse | `1` bis `9` | Klasse waehlen, die gesetzt wird |
| Klick auf ein leeres Feld | -- | Objekt setzen; die Auswahl bleibt bestehen |
| Umschalt + Klick | -- | auch auf ein belegtes Feld setzen |
| Klick auf ein Objekt, ziehen | -- | auswaehlen und verschieben |
| Doppelklick auf eine Klasse | -- | ihre Quelldatei im Editor oeffnen |
| Rechtsklick | -- | Kontextmenue oeffnen |
| -- | `Entf` | ausgewaehltes Objekt entfernen |
| Welt sichern | `W` | Aufbau als Quelltext schreiben |

### Die Kontextmenues

Ein Rechtsklick oeffnet ein Menue; jeder Eintrag traegt eine Ziffer, `Esc`
schliesst es wieder -- und nur es, das Fenster bleibt offen.

**Auf einer Klasse im Baum:**

| Eintrag | Wirkung |
| --- | --- |
| `PowerUp()` erzeugen | setzt ein einzelnes Objekt in die Welt -- unter den Mauszeiger, sonst in die Mitte. Es ist danach ausgewaehlt und laesst sich sofort ziehen. |
| `Level0()` anzeigen | **bei einer Weltklasse:** erzeugt diese Welt und zeigt sie an |
| Quelltext oeffnen | startet `code -g datei:zeile`. PyFoot bringt keinen eigenen Texteditor mit; findet sich VS Code nicht, nennt die Meldung Pfad und Zeile. |
| Unterklasse anlegen… | fragt nach dem Namen und legt eine Datei aus einer Vorlage an |
| Bild zuweisen… | zeigt die Bilddateien aus den bekannten Bildordnern (nur bei Akteuren) |
| Löschen | entfernt eine selbst geschriebene Klasse samt Datei |

Der erste Eintrag traegt den Ausdruck, den man auch selbst schreiben wuerde --
Greenfoot zeigt an dieser Stelle `new X()`. Klassen, die sich nicht ohne Werte
erzeugen lassen, zeigen ihn abgeschaltet statt ihn zu verbergen: So bleibt
erkennbar, warum er nicht greift.

### Die Welt wechseln

`Level0() anzeigen` erzeugt eine neue Welt dieser Art und stellt sie dar. Der
Name der Welt steht danach in der Titelzeile.

**Das bisherige Raumschiff wird nicht uebernommen.** Jede Welt bringt ihr
eigenes mit, so wie ihr Konstruktor es vorsieht -- wer sein Schiff mitnehmen
will, setzt ein neues Exemplar hinein. Laeuft gerade Schuelercode, wird es
zuvor abgebrochen; die Welt wird nicht unter ihm ausgetauscht.

### Eine Klasse loeschen

Geloescht wird **nur, was zum eigenen Bereich gehoert** -- also in einem der
ueber `set_class_folders` angemeldeten Ordner liegt. Das ist eine
Erlaubnisliste: Was nicht dort steht, ist geschuetzt, ohne dass jemand eine
Verbotsliste pflegen muesste.

Zwei weitere Bedingungen:

- **Die Klasse muss allein in ihrer Datei stehen.** In Java gilt eine Klasse
  je Datei, in Python nicht -- eine einzelne aus einer geteilten Datei
  herauszuschneiden hinterliesse einen unklaren Rest. Was die Oberflaeche
  selbst anlegt, steht immer allein.
- **Der erste Befehl fragt nach, der zweite fuehrt aus**, wie beim Sichern mit
  Strukturverlust.

Die Datei wird nicht geloescht, sondern zur Sicherungskopie umbenannt (Auflage
F3). Vorhandene Objekte der Klasse verlassen zuvor die Welt, und das Modul
wird entladen, damit die Klasse aus dem Baum verschwindet.

**Auf einem Objekt in der Welt:** seine oeffentlichen Methoden, dazu
`Inspizieren`, `Quelltext oeffnen` und `Entfernen`. Ein Aufruf zeigt seinen
Rueckgabewert in der Statuszeile; scheitert er, wird der Fehler dort gemeldet,
statt das Programm zu beenden.

Angezeigt wird nur, was die Klasse wirklich mitbringt und ohne Werte
aufrufbar ist. Beides zusammen ist wichtig: Die Anzeige entsteht allein durch
Nachsehen in der Klasse und kann deshalb keine Methode vortaeuschen, die es
nicht gibt.

### Eine Unterklasse anlegen

Die erzeugte Datei ist ohne Nacharbeit lauffaehig und besteht die
Typpruefung. Offene Methoden der Grundklasse werden als Rumpf angelegt:

```python
"""Ufo -- neue Klasse, erzeugt von der Oberflaeche.

Hier kann eine Beschreibung stehen.
"""

from __future__ import annotations

from space import Spaceship


class Ufo(Spaceship):
    """Beschreibung."""

    def init(self) -> None:
        """Hier stehen die Anweisungen."""
```

Eingebunden wird ueber den **kuerzesten** Weg, ueber den die Grundklasse
erreichbar ist -- also `from space import Spaceship`, nicht ueber das
Untermodul. `__slots__` fehlt bewusst: Sonst liessen sich in der neuen Klasse
keine eigenen Werte ergaenzen.

Die Datei wird anschliessend eingebunden: Die Klasse steht **sofort** im Baum
und laesst sich setzen, ohne Neustart. Scheitert das Einbinden, bleibt die
Datei erhalten und der Grund steht in der Statuszeile.

### Ein Objekt inspizieren

`Inspizieren` zeigt den Zustand eines Objekts -- alle Attribute mit ihren
aktuellen Werten:

```
NormalSpaceship — Zustand
  _init_done                False
  _power_ups                 5000
  _rotation                     0
  _x                            0
  _y                            5
```

Die Werte werden bei jedem Bild neu gelesen, und die Bedienleiste bleibt
benutzbar. Zusammen mit dem Einzelschritt laesst sich damit **zusehen**, wie
sich ein Wert Anweisung fuer Anweisung aendert. `Esc` oder ein Klick auf einen
festen Wert schliesst die Anzeige.

**Farbig abgesetzte Werte lassen sich aendern.** Bearbeitbar ist nur, was beim
Sichern der Welt auch im Quelltext landet -- also im Ausdruck aus
`construction_code()` vorkommt:

```
RandomPowerUp — Zustand
  _probability                0.9      <- farbig, aenderbar
  _rotation                     0
  _x                            4
```

Der Grund ist das Leitprinzip: Der Quelltext ist die einzige Wahrheit. Ein
Wert, der nur zur Laufzeit existierte, waere beim naechsten Zuruecksetzen
wieder weg -- ihn bearbeitbar zu machen taeuschte Dauerhaftigkeit vor.

Die Lage eines Objekts gehoert deshalb **nicht** dazu: Sie wird durch Ziehen
geaendert. Ein neuer Wert muss vom selben Typ sein wie der alte, und gelesen
werden nur Literale -- eingetippter Code wird nicht ausgefuehrt.

### Werte beim Erzeugen uebergeben

Nimmt der Konstruktor Werte entgegen, fragt die Oberflaeche vor dem Erzeugen
danach. Der Menueeintrag kuendigt das an:

| Klasse | Eintrag |
| --- | --- |
| `PowerUp` | `PowerUp() erzeugen` |
| `RandomPowerUp` | `RandomPowerUp(…) erzeugen` |

Die Eingabe ist mit den Vorgaben vorbelegt -- ein Druck auf die Eingabetaste
uebernimmt sie unveraendert. Auch hier werden nur Literale gelesen.

### Ein Bild zuweisen

Auch das wird Quelltext, keine Nebendatei. Laedt die Klasse ihr Bild bereits
im Konstruktor, wird dort der Dateiname fortgeschrieben:

```python
super().__init__(image=Image.from_file("asteroid.png"))
```

Andernfalls entsteht das Klassenmerkmal `IMAGE`, das `Actor` beim Erzeugen
auswertet. Es laesst sich ebenso von Hand setzen:

```python
class Comet(Actor):
    IMAGE = "comet.png"
```

### Welt sichern

`Welt sichern` schreibt den Aufbau als Methode `prepare()` in die Quelldatei
der Weltklasse:

```python
def prepare(self) -> None:
    """Von der Oberflaeche erzeugt. Darf von Hand bearbeitet werden."""
    self.add_object(PowerUp(), 3, 3)
    self.add_object(Asteroid(), 6, 0)
```

Das ist bewusst **Quelltext und keine Nebendatei**: Er laesst sich lesen,
verstehen und von Hand weiterbearbeiten.

Gearbeitet wird ueber den Syntaxbaum, nicht mit Zeichenkettensuche. Eine
vorhandene `prepare()` wird ersetzt, **alles andere bleibt unangetastet**;
fehlende Einfuhren kommen dazu. Vor jedem Schreibvorgang entsteht eine
Sicherungskopie `<datei>.py.bak`, und geschrieben wird ueber eine
Zwischendatei -- schlaegt etwas fehl, bleibt das Original unveraendert.

Drei Punkte, die dabei wichtig sind:

**Werte im Konstruktor gehen nicht verloren.** Ein Akteur sagt selbst, wie er
entsteht:

```python
def construction_code(self) -> str:
    return f"{type(self).__name__}({self._probability})"
```

Ohne diese Methode heisst es schlicht `PowerUp()`. Akteure, die zwingend
Werte brauchen -- etwa ein Hinweistext --, werden uebergangen und im Bericht
genannt.

**Vor dem Verlust von Struktur wird gewarnt.** Baut sich `prepare()` mit einer
Schleife auf, wuerde daraus eine lange flache Liste. Der erste Druck warnt
dann und nennt die Zeilenzahl; erst der zweite schreibt.

**Das Startfeld wird fortgeschrieben, nicht gesetzt.** Fuehrt eine Weltklasse
ein Merkmal `START`, so benennt es das Feld, auf dem ein von aussen
uebergebener Akteur eingesetzt wird. Dieser Akteur gehoert nicht in
`prepare()` -- sonst stuende er doppelt in der Welt. Wird er verschoben,
aendert sich stattdessen die `START`-Angabe. `START` ist dabei eine
Vereinbarung ueber einen Namen, kein Wissen ueber ein bestimmtes Thema.

## Wie PyFoot zu Space kommt

PyFoot wird **nicht installiert**, sondern mit dem Projekt Space ausgeliefert.
An der Schule hat niemand Administratorrechte; eine mitgelieferte Kopie laesst
sich dagegen jederzeit austauschen.

Space legt in seiner `pyproject.toml` fest, welche PyFoot-Version es braucht,
und holt genau diese mit `python tools\get_pyfoot.py` -- als Archiv des
passenden Versions-Tags (`v0.1.0` usw.) von GitHub. Eine neue Version von
PyFoot heisst deshalb:

1. `__version__` in `pyfoot/__init__.py` und `version` in `pyproject.toml`
   erhoehen (ein Test prueft, dass beide gleich sind),
2. den Tag `v<version>` setzen und veroeffentlichen,
3. in Space die Version eintragen und die Tests laufen lassen.

Zum Entwickeln uebernimmt Space den Stand dieses Ordners direkt, ohne Tag:
`python tools\get_pyfoot.py --local` (im Ordner pyfoot-space).

**Bewusst kein ZIP-Archiv:** Aus einem Archiv koennen weder mypy noch Pylance
die Typangaben lesen -- die Typpruefung meldete dann faelschlich "keine
Fehler". Gemessen und verworfen.

Voraussetzung zum Ausfuehren ist Python 3.11 oder neuer und `pygame`.

## Beispiele starten

```bash
python example_minimal.py
```

```bash
python example_controls.py
```

## Tests und Typpruefung

```bash
python -m pytest
```

```bash
python tools\check_project.py
```

**Auf GitHub** laeuft beides bei jedem Push und jedem Pull Request
automatisch (`.github/workflows/tests.yml`), unter Windows mit Python 3.11 und
3.13. Ein zweiter Job legt pyfoot-space daneben, uebernimmt diesen Stand von
PyFoot mit `--local` und laesst dessen Tests laufen -- so faellt ein Bruch in
Space auf, bevor eine neue Version getaggt wird. Mit `--ci` liefert
`check_project.py` den Rueckgabewert von mypy, damit ein Typfehler den Lauf
rot faerbt; lokal bleibt die Pruefung nicht blockierend.

## Namensgebung

Alle Bezeichner -- Klassen, Methoden, Variablen, Module -- sind englisch.
Kommentare und Docstrings sind deutsch.

## Abhaengigkeiten

| Paket | Wofuer | Lizenz |
| --- | --- | --- |
| [pygame](https://www.pygame.org) | Grafik und Fenster, zur Laufzeit | LGPL-2.1 |
| [mypy](https://mypy-lang.org) | Typpruefung, nur fuer die Entwicklung | MIT |
| [pytest](https://pytest.org) | Tests, nur fuer die Entwicklung | MIT |

pygame wird nur eingebunden, nicht veraendert oder mitgeliefert; die LGPL
erlaubt das unter jeder Lizenz.

## Vorbilder

Inspiriert von -- uebernommen wurden Ideen, kein Quelltext:

1. **Karel J. Robot** (Joseph Bergin, Mark Stehlik, Jim Roberts, Richard
   Pattis): ein Roboter in einer Gitterwelt als Einstieg ins Programmieren
2. **Greenfoot** (Michael Kölling u. a.): Welt und Akteure, der
   `act()`-Zyklus
3. **pyGreenfoot**: eine Umsetzung dieser Idee in Python mit pygame
4. **Python-Spacebug** ([inf-schule.de](https://inf-schule.de), heute
   gepflegt von der Universitaet Trier): Missionen im Weltraum -- das Thema
   des Basisprojekts [pyfoot-space](https://github.com/SAE-GMO/pyfoot-space)

## Entstehung

Kurskonzept und Aufgaben stammen von Jörg Schaede, aufbauend auf den
genannten Vorbildern. Der Quelltext entstand mit Unterstuetzung des
KI-Assistenten Claude (Anthropic). Alle Inhalte wurden vom Autor geprueft und
werden von ihm verantwortet.

## Lizenz

(c) 2026 Jörg Schaede -- **MIT**, siehe `LICENSE`.
