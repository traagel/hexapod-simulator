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


def test_early_touchdown_locks_at_current_swing_position_not_planned_end(
    hexapod: Hexapod,
):
    """Regression: when a contact reflex fires mid-swing, the leg must lock
    its stance at WHERE THE FOOT CURRENTLY IS in the lift arc, not at the
    planned-but-unreached landing target. The old behavior pulled the foot
    down through the contact point.
    """
    g = TripodGait(hexapod, step_length=4.0, lift_height=3.0, neutral_radius=14)
    g.linear_velocity = (4.0, 0.0)
    g.angular_velocity = 0.0

    # Pick a leg in group 0 (in swing during the first half of the cycle).
    key = next(iter(TripodGait.GROUPS[0]))

    # First call latches the swing plan at phase 0 (swing-start).
    g.targets(0.0)
    # Advance to mid-swing (local phase ≈ 0.4 → still in swing, past the
    # 30% noise window). Local phase = phase + group/N = phase + 0 = phase.
    g.targets(0.4)

    # Capture the foot's actual position at this point in the swing arc.
    swing_pos_now = g._swing_at(
        hexapod.legs.get(*key), 0.4, g.neutral_position(hexapod.legs.get(*key))
    )
    assert swing_pos_now[2] > 0.0, "sanity: foot should be above stance_z mid-swing"

    # Fire contact for that leg on the next tick — the reflex should lock
    # the foot AT swing_pos_now, NOT at the planned swing_target_body.
    contacts = {k: False for k in
                ((s, sd) for g_ in TripodGait.GROUPS for (s, sd) in g_)}
    contacts[key] = True
    g.targets(0.42, contacts=contacts)

    locked_world = g._stance_world[key]
    expected_world = hexapod.pose.transform(swing_pos_now)
    # Allow a tiny window because the swing arc advances slightly between
    # phases 0.4 and 0.42.
    for axis in range(3):
        assert abs(locked_world[axis] - expected_world[axis]) < 0.5

    # Crucially, the locked z must be ABOVE stance_z (= 0). The bug locked
    # at the planned end which is at stance_z, dragging the foot down.
    assert locked_world[2] > 0.5, (
        f"reflex locked foot at z={locked_world[2]:.3f} (≤ 0.5); should be "
        f"up in the lift arc, not at the planned ground-level landing"
    )
