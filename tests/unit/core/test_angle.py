import math

import pytest

from hexapod.core.angle import Angle


def test_default_zero():
    assert Angle().rad == 0.0
    assert Angle().deg == 0.0


def test_rad_deg_consistent():
    a = Angle.from_deg(90)
    assert a.rad == pytest.approx(math.pi / 2)
    assert a.deg == pytest.approx(90)


def test_setter_round_trip():
    a = Angle()
    a.deg = 45
    assert a.rad == pytest.approx(math.pi / 4)
    a.rad = math.pi
    assert a.deg == pytest.approx(180)
