"""Tests fuer die Gitterwelt."""

from __future__ import annotations

import pytest

from pyfoot import Actor, World


class Rock(Actor):
    """Ein einfacher Akteur fuer Testzwecke."""


class Crate(Actor):
    """Ein zweiter Akteurtyp, um Typfilter zu pruefen."""


def test_size_is_stored() -> None:
    world = World(5, 3, cell_size=20)
    assert world.width == 5
    assert world.height == 3
    assert world.cell_size == 20


@pytest.mark.parametrize(
    "width, height, cell_size",
    [(0, 5, 60), (5, 0, 60), (-1, 5, 60), (5, 5, 0)],
)
def test_invalid_size_is_rejected(
    width: int, height: int, cell_size: int
) -> None:
    with pytest.raises(ValueError):
        World(width, height, cell_size)


def test_add_object_sets_position_and_world() -> None:
    world = World(4, 4)
    rock = Rock()
    world.add_object(rock, 2, 3)

    assert rock.x == 2
    assert rock.y == 3
    assert rock.world is world
    assert world.number_of_objects() == 1


def test_objects_at_filters_by_type() -> None:
    world = World(4, 4)
    rock = Rock()
    crate = Crate()
    world.add_object(rock, 1, 1)
    world.add_object(crate, 1, 1)

    assert len(world.objects_at(1, 1)) == 2
    assert world.objects_at(1, 1, Rock) == [rock]
    assert world.objects_at(1, 1, Crate) == [crate]
    assert world.objects_at(0, 0) == []


def test_remove_object() -> None:
    world = World(4, 4)
    rock = Rock()
    world.add_object(rock, 1, 1)
    world.remove_object(rock)

    assert world.number_of_objects() == 0
    assert rock.has_world is False


def test_removing_unknown_object_raises() -> None:
    world = World(4, 4)
    with pytest.raises(ValueError):
        world.remove_object(Rock())


def test_contains_detects_world_bounds() -> None:
    world = World(3, 2)
    assert world.contains(0, 0)
    assert world.contains(2, 1)
    assert not world.contains(3, 1)
    assert not world.contains(-1, 0)


def test_paint_order_puts_first_class_on_top() -> None:
    world = World(4, 4)
    rock = Rock()
    crate = Crate()
    world.add_object(rock, 0, 0)
    world.add_object(crate, 1, 1)
    world.set_paint_order(Rock, Crate)

    # Zuletzt gezeichnet wird, was obenauf liegen soll.
    assert world._paint_sorted_actors()[-1] is rock


def test_act_cycle_calls_every_actor() -> None:
    calls: list[str] = []

    class Counter(Actor):
        def __init__(self, name: str) -> None:
            super().__init__()
            self._name = name

        def act(self) -> None:
            calls.append(self._name)

    class CountingWorld(World):
        def act(self) -> None:
            calls.append("world")

    world = CountingWorld(3, 3)
    world.add_object(Counter("a"), 0, 0)
    world.add_object(Counter("b"), 1, 0)
    world._act_cycle()

    assert calls[0] == "world"
    assert set(calls[1:]) == {"a", "b"}


def test_show_and_clear_text() -> None:
    world = World(3, 3)
    world.show_text("Hallo", 1, 1)
    assert world.text_at(1, 1) is not None

    world.show_text(None, 1, 1)
    assert world.text_at(1, 1) is None
