"""Tests fuer Farben und Bilder."""

from __future__ import annotations

import pytest

from pyfoot import Color, Image


def test_colour_components_are_stored() -> None:
    colour = Color(10, 20, 30, 40)
    assert (colour.red, colour.green, colour.blue, colour.alpha) == (10, 20, 30, 40)


def test_alpha_defaults_to_opaque() -> None:
    assert Color(1, 2, 3).alpha == 255


@pytest.mark.parametrize("value", [-1, 256])
def test_invalid_colour_components_are_rejected(value: int) -> None:
    with pytest.raises(ValueError):
        Color(value, 0, 0)


def test_colours_are_comparable() -> None:
    assert Color(1, 2, 3) == Color(1, 2, 3)
    assert Color(1, 2, 3) != Color(3, 2, 1)
    assert len({Color(1, 2, 3), Color(1, 2, 3)}) == 1


def test_predefined_colours() -> None:
    assert Color.WHITE.as_tuple() == (255, 255, 255, 255)
    assert Color.RED.as_tuple() == (255, 0, 0, 255)


def test_with_alpha_leaves_original_unchanged() -> None:
    original = Color(1, 2, 3)
    faded = original.with_alpha(50)
    assert faded.alpha == 50
    assert original.alpha == 255


def test_blank_image_has_requested_size() -> None:
    image = Image.blank(30, 20)
    assert (image.width, image.height) == (30, 20)


def test_mirroring_keeps_size() -> None:
    image = Image.blank(30, 20)
    assert (image.mirror_horizontally().width, image.mirror_horizontally().height) == (
        30,
        20,
    )
    assert image.mirror_vertically().height == 20


def test_scaling() -> None:
    image = Image.blank(30, 20).scaled(60, 40)
    assert (image.width, image.height) == (60, 40)


def test_rotation_by_zero_returns_same_image() -> None:
    image = Image.blank(30, 20)
    assert image.rotated(0) is image
    assert image.rotated(360) is image


def test_rotation_by_90_swaps_edges() -> None:
    rotated_image = Image.blank(30, 20).rotated(90)
    assert (rotated_image.width, rotated_image.height) == (20, 30)


def test_text_image_is_larger_than_zero() -> None:
    image = Image.from_text("Hallo", 20, Color.WHITE)
    assert image.width > 0
    assert image.height > 0


@pytest.mark.parametrize("value", [-1, 256])
def test_invalid_transparency_is_rejected(value: int) -> None:
    with pytest.raises(ValueError):
        Image.blank(4, 4).with_transparency(value)


def test_copy_is_independent() -> None:
    original = Image.blank(10, 10)
    copy_of_image = original.copy()
    assert copy_of_image is not original
    assert (copy_of_image.width, copy_of_image.height) == (10, 10)


def test_missing_file_raises_clear_error() -> None:
    with pytest.raises(FileNotFoundError):
        Image.from_file("gibt-es-nicht-12345.png")
