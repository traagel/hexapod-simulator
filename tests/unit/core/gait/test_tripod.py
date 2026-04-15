"""TripodGait state-machine invariants:
  - groups partition all six legs into two sets of three
  - idle gait has walking=False
  - begin_walk + one tick with nonzero twist latches a delta (walking=True)
  - neutral position is outward from the coxa mount
  - early-touchdown reflex locks stance at current arc position, not planned end
"""

from hexapod.core.enums import Segment, Side
from hexapod.core.gait.base import LegPhase
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


def test_idle_gait_not_walking(hexapod: Hexapod):
    g = TripodGait(hexapod, step_length=0.0)
    g.linear_velocity = (0.0, 0.0)
    g.angular_velocity = 0.0
    g.plant_all_from_fk()
    assert g.walking is False
    assert g.is_settled


def test_non_zero_twist_latches_after_first_tick(hexapod: Hexapod):
    g = TripodGait(hexapod)
    g.linear_velocity = (4.0, 0.0)
    g.angular_velocity = 0.0
    g.begin_walk()
    # begin_walk alone plants every leg at STANCE with zero delta; gait is
    # walking but no step is committed yet.
    assert g.walking is True
    assert g.is_settled
    # First tick advances phase; group 0 (local=0) crosses STANCE→SWING and
    # latches a nonzero delta, so the gait is no longer settled.
    g.tick(0.01)
    assert g.is_settled is False


def test_neutral_position_outward_from_mount(hexapod: Hexapod):
    g = TripodGait(hexapod)
    for leg in hexapod.legs:
        nx, ny, nz = g.neutral_position(leg)
        mx, my = leg.coxa.mount
        assert (nx * nx + ny * ny) > (mx * mx + my * my)
        assert nz == g.stance_z


def test_early_touchdown_locks_at_current_swing_position_not_planned_end(
    hexapod: Hexapod,
):
    """When a contact reflex fires mid-swing, the leg must lock its stance
    at WHERE THE FOOT CURRENTLY IS in the lift arc — not at the planned
    landing target (which would drag the foot through the contact point).
    """
    g = TripodGait(hexapod, step_length=4.0, lift_height=3.0, neutral_radius=14)
    g.linear_velocity = (4.0, 0.0)
    g.angular_velocity = 0.0

    key = next(iter(TripodGait.GROUPS[0]))
    g.begin_walk()
    g.tick(0.01)  # fires STANCE→SWING for group 0 via the seeded prev_local=1.0
    assert g.plans[key].phase == LegPhase.SWING

    # Jump phase to mid-swing (local ≈ 0.4, past the 30% early-noise window).
    g.phase = 0.4
    for plan in g.plans.values():
        plan.prev_local = 0.39  # continuous with phase we're jumping to
    # Capture the arc position right before the reflex fires so the
    # comparison has no inter-tick drift.
    local_here = g._local_phase(g.phase, g._group_index(key))
    arc_pos_body = g._swing_interp(g.plans[key], local_here)
    assert arc_pos_body[2] > 0.0, "sanity: foot should be above stance_z mid-swing"

    # Fire the reflex on this exact tick.
    contacts = {k: False for group in TripodGait.GROUPS for k in group}
    contacts[key] = True
    g.tick(0.0, contacts=contacts)  # phase doesn't advance; reflex fires

    plan = g.plans[key]
    assert plan.phase == LegPhase.STANCE
    assert plan.world_lock is not None
    expected_world = hexapod.pose.transform(arc_pos_body, pivot_z=hexapod.height)
    for axis in range(2):  # xy — z is clamped to stance_z by world_lock
        assert abs(plan.world_lock[axis] - expected_world[axis]) < 1e-6


def test_first_cycle_no_teleport(hexapod: Hexapod):
    """begin_walk snapshots the foot's true xy; sample after should return
    that same xy (z is clamped to stance_z — feet land on the ground)."""
    from hexapod.core.kinematics import fk

    g = TripodGait(hexapod, step_length=4.0, lift_height=3.0)
    g.linear_velocity = (4.0, 0.0)
    g.angular_velocity = 0.0

    before = {(leg.segment, leg.side): fk.solve(leg) for leg in hexapod.legs}

    g.begin_walk()
    after = {(leg.segment, leg.side): g.sample(leg) for leg in hexapod.legs}

    for key, pre in before.items():
        post = after[key]
        horizontal = ((post[0] - pre[0]) ** 2 + (post[1] - pre[1]) ** 2) ** 0.5
        assert horizontal < 1e-9, f"leg {key} xy-teleported by {horizontal}"
        assert post[2] == g.stance_z


def test_reflex_ignored_before_any_leg_has_swung(hexapod: Hexapod):
    """Contacts in the very first tick after begin_walk must not force any
    leg into reflex touchdown — every leg starts in STANCE."""
    g = TripodGait(hexapod, step_length=4.0, lift_height=3.0)
    g.linear_velocity = (4.0, 0.0)
    g.begin_walk()
    contacts = {
        (seg, side): True for seg in Segment for side in Side
    }
    g.tick(0.01, contacts=contacts)
    # Group 0 legitimately enters SWING via swing-start edge; that's fine.
    # The key invariant: no leg should be locked via reflex while it was
    # in STANCE — the reflex edge requires phase == SWING.
    # We verify by checking no group-1 leg (which stays STANCE at phase 0)
    # got its world_lock clobbered to a lifted position.
    for key in TripodGait.GROUPS[1]:  # STANCE legs at phase=0
        plan = g.plans[key]
        assert plan.phase == LegPhase.STANCE
        assert plan.world_lock is not None
        assert plan.world_lock[2] == g.stance_z  # not lifted
