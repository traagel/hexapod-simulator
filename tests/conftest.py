"""Shared fixtures.

Tests build a Hexapod from the real config so leg lengths are non-zero
(the default Hexapod() leaves them at 0, which makes IK degenerate).
"""

from pathlib import Path

import pytest

from hexapod.core.gait.tripod import TripodGait
from hexapod.core.hexapod import Hexapod
from hexapod.drivers.sim import SimDriver
from hexapod.robot import Robot

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "hexapod.yaml"


@pytest.fixture
def hexapod() -> Hexapod:
    return Hexapod.from_config(CONFIG_PATH)


@pytest.fixture
def gait(hexapod: Hexapod) -> TripodGait:
    return TripodGait(hexapod, step_length=4.0, lift_height=3.0)


@pytest.fixture
def robot(hexapod: Hexapod, gait: TripodGait) -> Robot:
    r = Robot(hexapod, gait, SimDriver(hexapod), cycle_seconds=0.6)
    r.set_zero_stance(False)  # tests expect gait-active robot
    # Skip past the stand-up transition.
    for _ in range(200):
        r.step(0.02)
    return r
