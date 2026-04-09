"""End-to-end Robot.step behavior — the things the README claims work."""

import math

import pytest

from hexapod.core.enums import Segment, Side
from hexapod.robot import Robot


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
    # Let any in-flight swing finish.
    for _ in range(80):
        robot.step(0.02)
    x_after_stop = robot.hexapod.pose.x
    for _ in range(200):
        robot.step(0.02)
    assert robot.hexapod.pose.x == pytest.approx(x_after_stop, abs=1e-9)


def test_kick_starts_motion_immediately(robot: Robot):
    """Setting twist while idle should produce body translation in the next
    few ticks (not after waiting a full cycle)."""
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
    """The gait's locked stance_world entries must not change between ticks
    while a leg remains in stance. This is the source-of-truth invariant —
    measuring foot world position via pose.transform() after step() mixes
    the pose from tick N+1 with foot coordinates from tick N (pose.integrate
    runs after IK), so we read from gait._stance_world directly.
    """
    robot.set_twist(0.3, 0.0, 0.0)
    for _ in range(30):
        robot.step(0.02)

    prev = dict(robot.gait._stance_world)
    checked = 0
    for _ in range(60):
        robot.step(0.02)
        for k, locked in robot.gait._stance_world.items():
            if k in prev:
                d = math.hypot(locked[0] - prev[k][0], locked[1] - prev[k][1])
                assert d < 1e-9, f"stance_world for {k} drifted by {d}"
                checked += 1
        prev = dict(robot.gait._stance_world)

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
