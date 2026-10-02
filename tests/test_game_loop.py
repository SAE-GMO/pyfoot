"""Tests fuer den Spielzyklus (Anforderungsdokument 4.10).

PyFoot kennt einen Mechanismus -- `act()` in jedem Durchlauf -- und darauf zwei
Verwendungsarten: den Spielzyklus (`Actor.act()` ueberschreiben) und die
einmalige Anweisungsfolge (`ScriptActor.init()`). Beide muessen nebeneinander
funktionieren.
"""

from __future__ import annotations

from pyfoot import Actor, Image, ScriptActor, World


class Drifter(Actor):
    """Spielakteur: zaehlt, wie oft act() aufgerufen wurde."""

    __slots__ = ("ticks",)

    def __init__(self) -> None:
        super().__init__(image=Image.blank(4, 4))
        self.ticks = 0

    def act(self) -> None:
        self.ticks += 1


class Program(ScriptActor):
    """Anweisungsfolge: init() laeuft einmalig und dauert mehrere Aktionen."""

    __slots__ = ("inits", "steps")

    def __init__(self, steps: int = 5) -> None:
        super().__init__(image=Image.blank(4, 4))
        self.inits = 0
        self.steps = steps

    def init(self) -> None:
        self.inits += 1
        for _ in range(self.steps):
            self.move()


# ----------------------------------------------------------------------
# G1 -- act() ist der Mechanismus
# ----------------------------------------------------------------------


def test_act_wird_in_jedem_durchlauf_aufgerufen() -> None:
    world = World(10, 4, cell_size=4)
    drifter = Drifter()
    world.add_object(drifter, 0, 0)

    for erwartet in range(1, 6):
        world._act_cycle()
        assert drifter.ticks == erwartet


# ----------------------------------------------------------------------
# G2 -- init() ist der erste act(), genau einmal
# ----------------------------------------------------------------------


def test_init_laeuft_genau_einmal_im_ersten_durchlauf() -> None:
    world = World(20, 4, cell_size=4)
    program = Program()
    world.add_object(program, 0, 0)

    assert program.inits == 0

    world._act_cycle()
    assert program.inits == 1, "init() muss im ersten Durchlauf laufen"

    for _ in range(4):
        world._act_cycle()
    assert program.inits == 1, "init() darf sich nicht wiederholen"


def test_akteur_merkt_sich_dass_init_gelaufen_ist() -> None:
    world = World(20, 4, cell_size=4)
    program = Program()
    world.add_object(program, 0, 0)

    assert program.init_done is False
    world._act_cycle()
    assert program.init_done is True


# ----------------------------------------------------------------------
# G3 -- beide Verwendungsarten in derselben Welt
# ----------------------------------------------------------------------


def test_spielakteur_laeuft_neben_einer_anweisungsfolge() -> None:
    """Der Kern von Anforderung G3, ueber mehrere Durchlaeufe nachgewiesen."""
    world = World(30, 4, cell_size=4)
    drifter = Drifter()
    program = Program(steps=5)
    world.add_object(drifter, 0, 0)
    world.add_object(program, 0, 1)

    for durchlauf in range(1, 6):
        world._act_cycle()
        # Die Anweisungsfolge laeuft genau einmal ...
        assert program.inits == 1
        # ... der Spielakteur dagegen in jedem Durchlauf.
        assert drifter.ticks == durchlauf


def test_reihenfolge_im_ersten_durchlauf_haelt_niemanden_auf() -> None:
    """Auch wenn die Anweisungsfolge zuerst drankommt und lange dauert."""
    world = World(30, 4, cell_size=4)
    program = Program(steps=8)
    drifter = Drifter()
    # Anweisungsfolge zuerst einfuegen -- sie ist damit zuerst an der Reihe.
    world.add_object(program, 0, 0)
    world.add_object(drifter, 0, 1)

    world._act_cycle()

    assert program.inits == 1
    assert drifter.ticks == 1, "Der Spielakteur kommt im selben Durchlauf noch dran"


def test_mehrere_anweisungsfolgen_laufen_je_einmal() -> None:
    world = World(30, 6, cell_size=4)
    programs = [Program(steps=2) for _ in range(3)]
    for row, program in enumerate(programs):
        world.add_object(program, 0, row)

    for _ in range(4):
        world._act_cycle()

    assert [p.inits for p in programs] == [1, 1, 1]
