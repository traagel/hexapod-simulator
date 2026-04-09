"""Pose: transform/inverse_transform are mutual inverses; integrate is correct."""

import math

import pytest

from hexapod.core.pose import Pose


def _close(a, b, tol=1e-9):
    return all(abs(x - y) < tol for x, y in zip(a, b))


@pytest.mark.parametrize(
    "pose_args,point",
    [
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


def test_transform_z_passthrough():
    pose = Pose(1.0, 2.0, 0.5)
    assert pose.transform((0.0, 0.0, 7.5))[2] == 7.5
    assert pose.inverse_transform((0.0, 0.0, 7.5))[2] == 7.5


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
