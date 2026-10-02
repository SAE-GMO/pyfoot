"""Tests fuer das Ausfuehrungsmodell (Anforderungsdokument 4.6).

Geprueft wird der Kern von PyFoot: Schuelercode laeuft blockierend und
sequenziell, dreht dabei aber die Ereignisschleife von innen heraus weiter,
ohne dass ein zweiter Thread noetig ist.
"""

from __future__ import annotations

import pytest

from pyfoot import ScriptActor, World
from pyfoot.engine import Engine, SimulationStopped, redraws


class Probe(ScriptActor):
    """Ein Akteur, der eine feste Anweisungsfolge abarbeitet."""

    def init(self) -> None:
        self.move()
        self.move()
        self.turn(90)
        self.move()


def _engine_with_world(world: World) -> Engine:
    """Bereitet eine Engine mit Fenster und ohne Wartezeiten vor."""
    engine = Engine.instance()
    engine.set_world(world)
    engine.step_duration = 0.0
    return engine


def test_redraws_repaints_after_every_action(monkeypatch: pytest.MonkeyPatch) -> None:
    world = World(6, 6, cell_size=10)
    probe = Probe()
    world.add_object(probe, 0, 0)
    engine = _engine_with_world(world)

    calls = 0
    original = Engine.update_screen

    def counting(self: Engine) -> None:
        nonlocal calls
        calls += 1
        original(self)

    # Gepatcht wird die Klasse, nicht die Instanz: Engine nutzt __slots__,
    # Instanzattribute lassen sich also gar nicht nachtraeglich setzen.
    monkeypatch.setattr(Engine, "update_screen", counting)

    world._act_cycle()

    # Vier gekennzeichnete Aktionen: move, move, turn, move
    assert calls == 4
    assert (probe.x, probe.y) == (2, 1)


def test_action_does_not_start_new_act_cycle() -> None:
    """Der Rekursionsschutz nach Anforderungsdokument 4.6, Auflage 2."""
    cycles = 0

    class CountingWorld(World):
        def _act_cycle(self) -> None:
            nonlocal cycles
            cycles += 1
            super()._act_cycle()

    world = CountingWorld(6, 6, cell_size=10)
    world.add_object(Probe(), 0, 0)
    engine = _engine_with_world(world)

    engine._act_cycle()

    # Trotz vier zwischenzeitlicher Neuzeichnungen genau ein Durchlauf.
    assert cycles == 1


def test_nested_act_cycle_is_suppressed() -> None:
    world = World(4, 4, cell_size=10)
    engine = _engine_with_world(world)

    cycles = 0

    class Recursive(ScriptActor):
        def init(self) -> None:
            nonlocal cycles
            cycles += 1
            # Ein Versuch, von innen heraus einen weiteren Durchlauf zu starten.
            engine._act_cycle()

    world.add_object(Recursive(), 0, 0)
    engine._act_cycle()

    assert cycles == 1


def test_closed_window_aborts_student_code() -> None:
    world = World(6, 6, cell_size=10)
    engine = _engine_with_world(world)

    steps = 0

    class Endless(ScriptActor):
        def init(self) -> None:
            nonlocal steps
            while True:
                steps += 1
                if steps == 3:
                    # Entspricht dem Schliessen des Fensters durch die Nutzerin.
                    engine.stop()
                self.turn(90)

    world.add_object(Endless(), 0, 0)
    engine._running = True
    engine._started = True

    with pytest.raises(SimulationStopped):
        world._act_cycle()

    assert steps == 3


def test_update_screen_without_window_does_nothing() -> None:
    engine = Engine.instance()
    # Kein set_world, also kein Fenster: der Aufruf darf nichts ausloesen.
    engine.update_screen()


def test_update_screen_before_start_does_not_abort() -> None:
    world = World(4, 4, cell_size=10)
    engine = _engine_with_world(world)
    # Simulation wurde nie gestartet: das ist ein regulaerer Einzelschritt.
    engine.update_screen()


def test_redraws_passes_return_value_through() -> None:
    class Calculator:
        @redraws
        def double(self, value: int) -> int:
            return value * 2

    world = World(4, 4, cell_size=10)
    _engine_with_world(world)

    assert Calculator().double(21) == 42


def test_set_and_get_world() -> None:
    engine = Engine.instance()
    assert engine.has_world is False
    with pytest.raises(RuntimeError):
        engine.world

    world = World(3, 3, cell_size=10)
    engine.set_world(world)
    assert engine.world is world


def test_invalid_timing_values_are_rejected() -> None:
    engine = Engine.instance()
    with pytest.raises(ValueError):
        engine.step_duration = -1.0
    with pytest.raises(ValueError):
        engine.fps_limit = 0


def test_random_number_is_within_range() -> None:
    from pyfoot import random_number

    for _ in range(200):
        assert 0 <= random_number(5) < 5

    with pytest.raises(ValueError):
        random_number(0)
