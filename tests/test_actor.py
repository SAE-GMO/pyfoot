"""Tests fuer Akteure und das Gitter-Bewegungsmodell."""

from __future__ import annotations

import pytest

from pyfoot import EAST, NORTH, SOUTH, WEST, Actor, ScriptActor, World


class Probe(Actor):
    """Ein einfacher Akteur fuer Testzwecke."""


class Cargo(Actor):
    """Ein zweiter Akteurtyp fuer Typfilter."""


def test_initial_values() -> None:
    probe = Probe()
    assert probe.x == 0
    assert probe.y == 0
    assert probe.rotation == EAST
    assert probe.has_world is False


def test_world_access_without_world_raises() -> None:
    with pytest.raises(RuntimeError):
        Probe().world


@pytest.mark.parametrize(
    "rotation, expected",
    [(EAST, (1, 0)), (SOUTH, (0, 1)), (WEST, (-1, 0)), (NORTH, (0, -1))],
)
def test_direction_gives_step_offset(
    rotation: int, expected: tuple[int, int]
) -> None:
    probe = Probe(rotation=rotation)
    assert probe.direction_offset() == expected


def test_diagonal_direction_raises() -> None:
    probe = Probe()
    probe.rotation = 45
    with pytest.raises(ValueError):
        probe.direction_offset()


def test_movement_in_all_directions() -> None:
    world = World(9, 9)
    probe = Probe()
    world.add_object(probe, 4, 4)

    probe.move()
    assert (probe.x, probe.y) == (5, 4)

    probe.rotation = SOUTH
    probe.move(2)
    assert (probe.x, probe.y) == (5, 6)

    probe.rotation = WEST
    probe.move()
    assert (probe.x, probe.y) == (4, 6)

    probe.rotation = NORTH
    probe.move(3)
    assert (probe.x, probe.y) == (4, 3)


def test_backward_movement() -> None:
    world = World(9, 9)
    probe = Probe()
    world.add_object(probe, 4, 4)
    probe.move(-2)
    assert (probe.x, probe.y) == (2, 4)


def test_rotation_stays_within_0_to_359() -> None:
    probe = Probe()
    probe.turn(90)
    assert probe.rotation == 90
    probe.turn(300)
    assert probe.rotation == 30
    probe.turn(-30)
    assert probe.rotation == 0
    probe.turn(-90)
    assert probe.rotation == 270


def test_find_object_on_neighbour_cell() -> None:
    world = World(5, 5)
    probe = Probe()
    cargo = Cargo()
    world.add_object(probe, 2, 2)
    world.add_object(cargo, 3, 2)

    assert probe.object_at_offset(1, 0, Cargo) is cargo
    assert probe.object_at_offset(0, 0, Cargo) is None
    assert probe.objects_at_offset(1, 0) == [cargo]


def test_detect_edge() -> None:
    world = World(5, 5)
    probe = Probe()
    world.add_object(probe, 0, 2)
    assert probe.is_at_edge()

    probe.set_location(2, 2)
    assert not probe.is_at_edge()

    probe.set_location(4, 2)
    assert probe.is_at_edge()


def test_script_actor_runs_init_exactly_once() -> None:
    class Program(ScriptActor):
        def __init__(self) -> None:
            super().__init__()
            self.runs = 0

        def init(self) -> None:
            self.runs += 1

    world = World(4, 4)
    program = Program()
    world.add_object(program, 0, 0)

    assert program.init_done is False
    world._act_cycle()
    world._act_cycle()
    world._act_cycle()

    assert program.runs == 1
    assert program.init_done is True


def test_script_actor_moves_like_an_actor() -> None:
    class Program(ScriptActor):
        def init(self) -> None:
            self.move()
            self.turn(90)
            self.move(2)

    world = World(6, 6)
    program = Program()
    world.add_object(program, 1, 1)
    world._act_cycle()

    assert (program.x, program.y) == (2, 3)
    assert program.rotation == SOUTH
