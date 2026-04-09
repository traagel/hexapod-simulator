"""TripodGait invariants:
  - groups partition all six legs into two sets of three
  - idle gait (zero twist) is_active is False
  - non-zero twist latches a delta after one swing-start
"""

from hexapod.core.enums import Segment, Side
from hexapod.core.gait.tripod import TripodGait
from hexapod.core.hexapod import Hexapod


def test_groups_partition_all_legs():
    union: set = set()
    for group in TripodGait.GROUPS:
        assert union.isdisjoint(group)
        union |= group
    expected = {(seg, side) for seg in Segment for side in Side}
    assert union == expected
    assert len(TripodGait.GROUPS) == 2
    assert all(len(g) == 3 for g in TripodGait.GROUPS)


def test_idle_gait_not_active(hexapod: Hexapod):
    g = TripodGait(hexapod, step_length=0.0)
    g.linear_velocity = (0.0, 0.0)
    g.angular_velocity = 0.0
    g.targets(0.0)
    assert g.is_active is False


def test_non_zero_twist_becomes_active_after_swing_start(hexapod: Hexapod):
    g = TripodGait(hexapod)
    g.linear_velocity = (4.0, 0.0)
    g.angular_velocity = 0.0
    # First call latches initial state for group 0 (which is at local phase 0).
    g.targets(0.0)
    assert g.is_active is True


def test_neutral_position_outward_from_mount(hexapod: Hexapod):
    g = TripodGait(hexapod)
    for leg in hexapod.legs:
        nx, ny, nz = g.neutral_position(leg)
        mx, my = leg.coxa.mount
        # Neutral foot should be farther from origin than the mount.
        assert (nx * nx + ny * ny) > (mx * mx + my * my)
        assert nz == g.stance_z
