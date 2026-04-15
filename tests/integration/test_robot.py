"""End-to-end Robot.step behavior — the things the README claims work."""

import math

import pytest

from hexapod.core.enums import Segment, Side
from hexapod.core.gait.base import LegPhase
from hexapod.robot import Robot, RobotMode


def test_idle_robot_does_not_slide(robot: Robot):
    """No twist, many ticks → body pose stays put. The classic slide bug."""
    for _ in range(200):
        robot.step(0.02)
    assert robot.hexapod.pose.x == pytest.approx(0.0, abs=1e-9)
    assert robot.hexapod.pose.y == pytest.approx(0.0, abs=1e-9)
    assert robot.hexapod.pose.yaw == pytest.approx(0.0, abs=1e-9)


def test_twist_then_stop_then_idle_does_not_drift(robot: Robot):
    robot.set_twist(0.5, 0.0, 0.0)
    for _ in range(50):
        robot.step(0.02)
    robot.stop()
    # Let any in-flight swing finish and the robot settle to STANDING.
    for _ in range(150):
        robot.step(0.02)
    x_after_stop = robot.hexapod.pose.x
    assert robot.mode == RobotMode.STANDING
    for _ in range(200):
        robot.step(0.02)
    assert robot.hexapod.pose.x == pytest.approx(x_after_stop, abs=1e-9)


def test_kick_starts_motion_immediately(robot: Robot):
    """Setting twist while STANDING should produce body translation within
    the next few ticks (not after waiting a full cycle)."""
    assert robot.mode == RobotMode.STANDING
    robot.set_twist(0.5, 0.0, 0.0)
    moved = False
    for _ in range(40):
        robot.step(0.02)
        if abs(robot.hexapod.pose.x) > 1e-6:
            moved = True
            break
    assert moved


def test_forward_twist_translates_forward(robot: Robot):
    robot.set_twist(0.5, 0.0, 0.0)
    for _ in range(300):
        robot.step(0.02)
    assert robot.hexapod.pose.x > 0.5


def test_stance_world_position_locked_while_translating(robot: Robot):
    """While a leg is in STANCE, its world_lock must not drift between ticks.
    This is the source-of-truth invariant for foot world position.
    """
    robot.set_twist(0.3, 0.0, 0.0)
    for _ in range(30):
        robot.step(0.02)

    def stance_locks():
        return {
            k: plan.world_lock
            for k, plan in robot.gait.plans.items()
            if plan.phase == LegPhase.STANCE and plan.world_lock is not None
        }

    prev = stance_locks()
    checked = 0
    for _ in range(60):
        robot.step(0.02)
        now = stance_locks()
        for k, locked in now.items():
            if k in prev:
                d = math.hypot(locked[0] - prev[k][0], locked[1] - prev[k][1])
                assert d < 1e-9, f"stance world_lock for {k} drifted by {d}"
                checked += 1
        prev = now

    assert checked > 20


def test_unreachable_foot_target_does_not_crash(robot: Robot):
    """Wildly out-of-reach one-shot foot target must not crash the loop;
    IK clamps it to the workspace and the leg ends up with finite angles."""
    leg_key = (Segment.FRONT, Side.LEFT)
    leg = robot.hexapod.legs.get(*leg_key)
    robot.set_foot_target(leg_key, (10_000.0, 0.0, 0.0))
    robot.step(0.02)  # must not raise
    after = (leg.coxa.angle.rad, leg.femur.angle.rad, leg.tibia.angle.rad)
    assert all(math.isfinite(x) for x in after)


def test_state_dto_round_trips_through_json_format(robot: Robot):
    from hexapod.api.dto import RobotState

    robot.set_twist(0.2, 0.0, 0.1)
    state = robot.step(0.02)
    again = RobotState.from_dict(state.to_dict())
    assert again == state


def test_subscribe_called_each_step(robot: Robot):
    seen: list = []
    unsub = robot.subscribe(lambda s: seen.append(s.t))
    robot.step(0.02)
    robot.step(0.02)
    unsub()
    robot.step(0.02)
    assert len(seen) == 2


# ── state-machine regression tests ────────────────────────────────────────


def test_walk_start_after_body_teleport_no_snap(robot: Robot):
    """After teleporting the body, pressing W must not snap any foot to
    neutral. The old land_all() lie caused exactly this."""
    from hexapod.core.kinematics import fk

    robot.set_body_pose(5.0, 5.0, 1.0)
    robot.step(0.02)  # absorbs the teleport and re-plants feet

    before = {(leg.segment, leg.side): fk.solve(leg) for leg in robot.hexapod.legs}

    robot.set_twist(0.5, 0.0, 0.0)
    robot.step(0.02)  # drain twist → _enter_walking → tick(dt)

    after = {(leg.segment, leg.side): fk.solve(leg) for leg in robot.hexapod.legs}

    # Each foot's body-frame displacement this tick should be on the order
    # of one phase step (≈ dt/cycle_seconds * step_length), not a full snap
    # to neutral (which would be many units for a teleported body).
    for key, pre in before.items():
        dx = after[key][0] - pre[0]
        dy = after[key][1] - pre[1]
        horizontal = math.hypot(dx, dy)
        assert horizontal < 1.0, f"{key} jumped by {horizontal} on walk-start"


def test_stop_settles_to_standing_mode(robot: Robot):
    robot.set_twist(0.5, 0.0, 0.0)
    for _ in range(30):
        robot.step(0.02)
    assert robot.mode == RobotMode.WALKING
    robot.stop()
    settled = False
    for _ in range(200):
        robot.step(0.02)
        if robot.mode == RobotMode.STANDING:
            settled = True
            break
    assert settled


def test_mid_walk_twist_change_holds_latched_delta(robot: Robot):
    """Legs already in SWING keep their latched delta; only the next
    STANCE→SWING picks up the new twist."""
    robot.set_twist(0.5, 0.0, 0.0)
    for _ in range(10):
        robot.step(0.02)

    # Snapshot latched deltas of any SWING legs.
    swing_before = {
        k: plan.latched_delta
        for k, plan in robot.gait.plans.items()
        if plan.phase == LegPhase.SWING
    }

    robot.set_twist(0.0, 0.5, 0.0)  # hard turn sideways
    robot.step(0.02)  # drain, then tick

    # Legs that remained in SWING should have the same latched_delta.
    for k, delta_before in swing_before.items():
        plan = robot.gait.plans[k]
        if plan.phase == LegPhase.SWING:
            assert plan.latched_delta == delta_before, (
                f"{k} re-latched mid-swing"
            )


def test_mode_sequence_under_scripted_commands(robot: Robot):
    """End-to-end: robot fixture already walked ZERO_STANCE → STANDING.
    From STANDING, set_twist → WALKING; stop + settle → STANDING;
    set_zero_stance(True) → TRANSITION → ZERO_STANCE.
    """
    assert robot.mode == RobotMode.STANDING
    robot.set_twist(0.5, 0.0, 0.0)
    robot.step(0.02)
    assert robot.mode == RobotMode.WALKING

    robot.stop()
    for _ in range(200):
        robot.step(0.02)
        if robot.mode == RobotMode.STANDING:
            break
    assert robot.mode == RobotMode.STANDING

    robot.set_zero_stance(True)
    assert robot.mode == RobotMode.TRANSITION
    for _ in range(200):
        robot.step(0.02)
    assert robot.mode == RobotMode.ZERO_STANCE


def test_height_change_while_standing_keeps_feet_planted(robot: Robot):
    """Changing body height must re-anchor stance feet so they don't snap
    to wherever the stale lock reprojects to."""
    assert robot.mode == RobotMode.STANDING
    old_locks = {
        k: plan.world_lock for k, plan in robot.gait.plans.items()
    }
    robot.set_body_height(robot.hexapod.height + 2.0)
    # After relock, world_locks should be close to the previous values in xy
    # (feet were already at those positions); z is always stance_z.
    for k, plan in robot.gait.plans.items():
        assert plan.phase == LegPhase.STANCE
        assert plan.world_lock is not None
        assert abs(plan.world_lock[0] - old_locks[k][0]) < 0.1
        assert abs(plan.world_lock[1] - old_locks[k][1]) < 0.1
