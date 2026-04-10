"""Pose: transform/inverse_transform are mutual inverses; integrate is correct."""

import math

import pytest

from hexapod.core.pose import Pose


def _close(a, b, tol=1e-9):
    return all(abs(x - y) < tol for x, y in zip(a, b))


# ── round-trip: transform ↔ inverse_transform ────────────────────────────

@pytest.mark.parametrize(
    "pose_args,point",
    [
        # yaw only (original tests)
        ((0.0, 0.0, 0.0), (1.0, 2.0, 3.0)),
        ((5.0, -3.0, 0.7), (1.0, 2.0, 3.0)),
        ((-2.0, 4.0, -1.2), (0.0, 0.0, 0.5)),
        ((10.0, 10.0, math.pi), (-4.0, 7.0, 2.0)),
    ],
)
def test_transform_inverse_round_trip(pose_args, point):
    pose = Pose(*pose_args)
    assert _close(pose.inverse_transform(pose.transform(point)), point)
    assert _close(pose.transform(pose.inverse_transform(point)), point)


@pytest.mark.parametrize(
    "roll,pitch,yaw,pivot_z,point",
    [
        (0.3, 0.0, 0.0, 12.0, (1.0, 2.0, 3.0)),
        (0.0, 0.4, 0.0, 10.0, (5.0, -1.0, 2.0)),
        (0.2, -0.3, 0.7, 12.0, (1.0, 2.0, 3.0)),
        (-0.1, 0.15, math.pi / 3, 8.0, (-4.0, 7.0, 2.0)),
        (0.5, 0.5, 1.0, 15.0, (0.0, 0.0, 10.0)),
    ],
)
def test_round_trip_with_roll_pitch(roll, pitch, yaw, pivot_z, point):
    pose = Pose(x=3.0, y=-2.0, yaw=yaw, roll=roll, pitch=pitch)
    assert _close(
        pose.inverse_transform(pose.transform(point, pivot_z), pivot_z), point,
    )
    assert _close(
        pose.transform(pose.inverse_transform(point, pivot_z), pivot_z), point,
    )


# ── Z passthrough when roll=pitch=0 ──────────────────────────────────────

def test_transform_z_passthrough_no_tilt():
    pose = Pose(1.0, 2.0, 0.5)
    assert pose.transform((0.0, 0.0, 7.5))[2] == pytest.approx(7.5)
    assert pose.inverse_transform((0.0, 0.0, 7.5))[2] == pytest.approx(7.5)


# ── directional tilt tests ───────────────────────────────────────────────

def test_pitch_forward_tilts_front_down():
    """Positive pitch should lower the +x (front) side."""
    pose = Pose(pitch=0.2)
    pivot = 12.0
    front = pose.transform((5.0, 0.0, pivot), pivot)
    rear  = pose.transform((-5.0, 0.0, pivot), pivot)
    # Front z should be lower than rear z.
    assert front[2] < rear[2]


def test_roll_tilts_sides():
    """Positive roll rotates +y toward +z around the x-axis."""
    pose = Pose(roll=0.2)
    pivot = 12.0
    # Points at the pivot plane but offset in y.
    left  = pose.transform((0.0, 5.0, pivot), pivot)
    right = pose.transform((0.0, -5.0, pivot), pivot)
    assert left[2] > right[2]


def test_no_tilt_at_pivot():
    """A point exactly at the pivot should only move in xy (yaw), not z."""
    pose = Pose(x=1.0, y=2.0, yaw=0.5, roll=0.3, pitch=0.2)
    pivot = 12.0
    result = pose.transform((0.0, 0.0, pivot), pivot)
    assert result[2] == pytest.approx(pivot)


# ── integrate ─────────────────────────────────────────────────────────────

def test_integrate_no_yaw_translates_in_world():
    pose = Pose()
    pose.integrate((1.0, 0.0), 0.0, dt=2.0)
    assert _close((pose.x, pose.y, pose.yaw), (2.0, 0.0, 0.0))


def test_integrate_with_yaw_rotates_into_world():
    pose = Pose(yaw=math.pi / 2)  # body +x points to world +y
    pose.integrate((1.0, 0.0), 0.0, dt=1.0)
    assert _close((pose.x, pose.y), (0.0, 1.0), tol=1e-12)


def test_integrate_angular():
    pose = Pose()
    pose.integrate((0.0, 0.0), 1.5, dt=2.0)
    assert pose.yaw == pytest.approx(3.0)


def test_integrate_does_not_affect_roll_pitch():
    """Roll and pitch are set directly, not integrated."""
    pose = Pose(roll=0.3, pitch=-0.2)
    pose.integrate((1.0, 1.0), 0.5, dt=1.0)
    assert pose.roll == pytest.approx(0.3)
    assert pose.pitch == pytest.approx(-0.2)
