"""Die Version steht an zwei Stellen -- sie muessen uebereinstimmen.

Space holt PyFoot ueber den Versions-Tag und prueft danach `__version__`.
Wichen beide voneinander ab, meldete Space eine falsche Version, obwohl die
richtige geholt wurde.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pyfoot

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_version_im_paket_und_in_pyproject_gleich() -> None:
    with PYPROJECT.open("rb") as datei:
        version = tomllib.load(datei)["project"]["version"]
    assert pyfoot.__version__ == version
