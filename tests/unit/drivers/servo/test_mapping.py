"""ServoMap loading and per-joint angle conversions."""

import math
from pathlib import Path

import pytest

from hexapod.drivers.servo.mapping import (
    JOINT_NAMES,
    LEG_NAMES,
    NUM_CHANNELS,
    JointServo,
    ServoMap,
)
from hexapod.drivers.servo.profile import ServoProfile

REPO = Path(__file__).resolve().parents[4]
CONFIG = REPO / "config" / "hexapod.yaml"


def _profile() -> ServoProfile:
    return ServoProfile(
        name="t",
        frequency_hz=50,
        pulse_min_us=500,
        pulse_max_us=2500,
        angle_min_deg=-90,
        angle_max_deg=90,
    )


# ── JointServo ────────────────────────────────────────────────────────────


def test_joint_servo_zero_is_center():
    js = JointServo(channel=0, profile=_profile())
    assert js.angle_rad_to_pulse_us(0.0) == 1500


def test_inverted_flips_direction():
    js = JointServo(channel=0, profile=_profile(), inverted=True)
    # +90° inverted lands on -90° → pulse_min
    assert js.angle_rad_to_pulse_us(math.radians(90)) == 500
    assert js.angle_rad_to_pulse_us(math.radians(-90)) == 2500


def test_trim_offsets_input_angle():
    js = JointServo(channel=0, profile=_profile(), trim_deg=10.0)
    # 0 rad + 10° trim → linear: (10 - (-90)) / 180 * 2000 + 500 = 1611.11 → 1611
    expected = round(500 + (100 / 180) * 2000)
    assert js.angle_rad_to_pulse_us(0.0) == expected


def test_trim_then_invert_order():
    """Trim is applied BEFORE inversion (matches the docstring contract)."""
    js = JointServo(channel=0, profile=_profile(), trim_deg=5.0, inverted=True)
    # 0° + 5° trim → 5° → invert → -5° → pulse
    expected_deg = -5.0
    expected = _profile().angle_deg_to_pulse_us(expected_deg)
    assert js.angle_rad_to_pulse_us(0.0) == expected


# ── ServoMap.from_config ──────────────────────────────────────────────────


def test_loads_eighteen_distinct_channels():
    sm = ServoMap.from_config(CONFIG)
    assert len(sm.joints) == NUM_CHANNELS
    channels = sorted(js.channel for js in sm.joints.values())
    assert channels == list(range(NUM_CHANNELS))


def test_every_leg_and_joint_present():
    sm = ServoMap.from_config(CONFIG)
    for leg in LEG_NAMES:
        for joint in JOINT_NAMES:
            assert sm.get(leg, joint) is not None


def test_inversion_pattern_is_consistent_across_legs():
    """All legs of the same side must agree on inversion per joint type
    (mechanical assemblies are mirror-symmetric across the body's xz plane)."""
    sm = ServoMap.from_config(CONFIG)
    for joint in JOINT_NAMES:
        left_flags = {sm.get(leg, joint).inverted
                      for leg in ("front_left", "mid_left", "rear_left")}
        right_flags = {sm.get(leg, joint).inverted
                       for leg in ("front_right", "mid_right", "rear_right")}
        assert len(left_flags) == 1, f"left {joint} inversions inconsistent"
        assert len(right_flags) == 1, f"right {joint} inversions inconsistent"


def test_left_and_right_inversion_are_opposite_per_segment():
    """Each leg pair (front, mid, rear) must have opposite inversion flags
    for the same joint type — the two sides of one segment are mirrored."""
    sm = ServoMap.from_config(CONFIG)
    for left_name, right_name in (
        ("front_left", "front_right"),
        ("mid_left",   "mid_right"),
        ("rear_left",  "rear_right"),
    ):
        for joint in JOINT_NAMES:
            left = sm.get(left_name, joint).inverted
            right = sm.get(right_name, joint).inverted
            assert left != right, (
                f"{left_name}.{joint} and {right_name}.{joint} both inverted={left}"
            )


def test_duplicate_channel_rejected():
    p = _profile()
    bad = {
        ("front_left", "coxa"): JointServo(channel=0, profile=p),
        ("front_left", "femur"): JointServo(channel=0, profile=p),  # dup
    }
    with pytest.raises(ValueError, match="duplicate"):
        ServoMap(bad)
