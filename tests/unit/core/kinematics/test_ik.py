"""IK invariants: FK(IK(p)) ≈ p for reachable p; clamps gracefully otherwise."""

import math
import random

import pytest

from hexapod.core.hexapod import Hexapod
from hexapod.core.kinematics import fk, ik


def _foot_world(leg) -> tuple[float, float, float]:
    return fk.solve(leg)


@pytest.mark.parametrize("seg_side_idx", list(range(6)))
def test_round_trip_after_bending(hexapod: Hexapod, seg_side_idx: int):
    """Bend each leg into a non-degenerate pose, then verify FK·IK ≈ id.

    Default config leaves the leg fully extended (d == L1+L2), which IK
    must clamp with `eps`. Bending the knee gets us off the singularity.
    """
    leg = list(hexapod.legs)[seg_side_idx]
    leg.femur.angle.rad = 0.4
    leg.tibia.angle.rad = 0.8
    foot = _foot_world(leg)
    ik.apply(leg, foot)
    after = _foot_world(leg)
    assert after == pytest.approx(foot, abs=1e-6)


def test_round_trip_random_reachable(hexapod: Hexapod):
    """Sample targets that are *strictly* inside each leg's workspace, in
    leg-plane polar coordinates so we never poke past L1+L2."""
    rng = random.Random(0xC0FFEE)
    for leg in hexapod.legs:
        mx, my = leg.coxa.mount
        rest = leg.coxa.rest_angle
        L1, L2 = leg.femur.length, leg.tibia.length
        d_min = abs(L1 - L2) + 0.5
        d_max = L1 + L2 - 0.5
        for _ in range(20):
            d = rng.uniform(d_min, d_max)
            theta = rng.uniform(-math.pi / 3, math.pi / 3)  # leg-plane elevation
            r = leg.coxa.length + d * math.cos(theta)  # horizontal from mount
            dz = d * math.sin(theta)
            tx = mx + r * math.cos(rest)
            ty = my + r * math.sin(rest)
            tz = leg.height + dz
            target = (tx, ty, tz)
            ik.apply(leg, target)
            achieved = _foot_world(leg)
            assert achieved == pytest.approx(target, abs=1e-6)


def test_unreachable_does_not_raise(hexapod: Hexapod):
    """Targets outside the workspace must be clamped, not crash."""
    leg = next(iter(hexapod.legs))
    mx, my = leg.coxa.mount
    far = (mx + 10_000.0, my, 0.0)
    ik.solve(leg, far)  # should not raise
    near = (mx + 0.001, my, 0.0)
    ik.solve(leg, near)  # also clamps


def test_round_trip_with_tibia_bend(hexapod: Hexapod):
    """The mechanical tibia bend must round-trip cleanly: FK and IK both
    fold it in, so FK(IK(target)) ≈ target regardless of the bend value."""
    rng = random.Random(0xBEEF)
    for leg in hexapod.legs:
        original_bend = leg.tibia.bend.rad
        try:
            for bend_deg in (0.0, 15.0, 25.0, 40.0):
                leg.tibia.bend.deg = bend_deg
                mx, my = leg.coxa.mount
                rest = leg.coxa.rest_angle
                L1, L2 = leg.femur.length, leg.tibia.length
                d_min = abs(L1 - L2) + 0.5
                d_max = L1 + L2 - 0.5
                for _ in range(5):
                    d = rng.uniform(d_min, d_max)
                    theta = rng.uniform(-math.pi / 4, math.pi / 4)
                    r = leg.coxa.length + d * math.cos(theta)
                    dz = d * math.sin(theta)
                    target = (
                        mx + r * math.cos(rest),
                        my + r * math.sin(rest),
                        leg.height + dz,
                    )
                    ik.apply(leg, target)
                    assert _foot_world(leg) == pytest.approx(target, abs=1e-6)
        finally:
            leg.tibia.bend.rad = original_bend


def test_bend_actually_offsets_tibia_servo_command(hexapod: Hexapod):
    """For a fixed target, increasing the tibia bend must reduce the tibia
    servo angle by the same amount (the bend lives entirely in the IK return)."""
    leg = next(iter(hexapod.legs))
    leg.tibia.bend.deg = 0.0
    mx, my = leg.coxa.mount
    target = (mx + 18.0, my + 0.0, leg.height - 4.0)
    _, _, t0 = ik.solve(leg, target)
    leg.tibia.bend.deg = 25.0
    _, _, t1 = ik.solve(leg, target)
    assert (t0 - t1) == pytest.approx(math.radians(25.0), abs=1e-9)


def test_unreachable_far_extends_toward_target(hexapod: Hexapod):
    """A far target should produce an FK foot in the same xy direction."""
    leg = next(iter(hexapod.legs))
    mx, my = leg.coxa.mount
    direction = leg.coxa.rest_angle
    target = (mx + 1000.0 * math.cos(direction), my + 1000.0 * math.sin(direction), 0.0)
    ik.apply(leg, target)
    foot = _foot_world(leg)
    # The foot should still lie along the same heading from the mount.
    achieved = math.atan2(foot[1] - my, foot[0] - mx)
    assert achieved == pytest.approx(direction, abs=1e-6)
