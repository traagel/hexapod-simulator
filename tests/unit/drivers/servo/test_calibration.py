"""Calibration: piecewise-linear interpolation, loader, ServoMap integration."""

import math
from pathlib import Path

import pytest

from hexapod.drivers.servo.calibration import Calibration, interpolate
from hexapod.drivers.servo.mapping import JointServo, ServoMap
from hexapod.drivers.servo.profile import ServoProfile

REPO = Path(__file__).resolve().parents[4]
CONFIG = REPO / "config" / "hexapod.yaml"
CAL_PATH = REPO / "config" / "calibration" / "ds3235ssg.yaml"


def _profile() -> ServoProfile:
    return ServoProfile(
        name="t",
        frequency_hz=50,
        pulse_min_us=500,
        pulse_max_us=2500,
        angle_min_deg=-135,
        angle_max_deg=135,
    )


# ── interpolate() ─────────────────────────────────────────────────────────


def test_interpolate_returns_exact_sample():
    samples = ((0.0, 500), (90.0, 1500), (180.0, 2500))
    assert interpolate(samples, 0.0) == 500
    assert interpolate(samples, 90.0) == 1500
    assert interpolate(samples, 180.0) == 2500


def test_interpolate_midpoint_is_average():
    samples = ((0.0, 500), (90.0, 1500))
    assert interpolate(samples, 45.0) == 1000


def test_interpolate_uneven_spacing():
    """Slope must change with sample spacing — that's the whole point."""
    samples = ((0.0, 0), (10.0, 100), (90.0, 180))
    # Between 10 and 90 the slope is 1 us/deg, so 50° → 140
    assert interpolate(samples, 50.0) == 140
    # Between 0 and 10 the slope is 10 us/deg, so 5° → 50
    assert interpolate(samples, 5.0) == 50


def test_interpolate_clamps_below_and_above():
    samples = ((0.0, 500), (90.0, 1500), (180.0, 2500))
    assert interpolate(samples, -10.0) == 500
    assert interpolate(samples, 999.0) == 2500


# ── Calibration.load ──────────────────────────────────────────────────────


def test_load_bundled_ds3235ssg():
    cal = Calibration.load(CAL_PATH)
    assert cal.profile_name == "ds3235ssg"
    assert cal.zero_offset_deg == 135.0
    # 18 entries
    assert len(cal.tables) == 18
    # Spot-check one known cell from the source CSV.
    rf1 = cal.tables[("front_right", "coxa")]
    assert (135.0, 1360) in rf1


def test_load_rejects_unsorted_samples(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "servo: x\n"
        "zero_offset_deg: 0\n"
        "legs:\n"
        "  front_left:\n"
        "    coxa:\n"
        "      - {deg: 90, pulse_us: 1500}\n"
        "      - {deg: 0,  pulse_us: 500}\n"
        "    femur: []\n"
        "    tibia: []\n"
    )
    with pytest.raises(ValueError, match="sorted"):
        Calibration.load(bad)


# ── JointServo with calibration ───────────────────────────────────────────


def test_joint_servo_uses_samples_when_present():
    samples = ((0.0, 500), (135.0, 1500), (270.0, 2500))
    js = JointServo(
        channel=0,
        profile=_profile(),
        samples=samples,
        zero_offset_deg=135.0,
    )
    # 0 rad → centered 0° → calibration 135° → 1500 us
    assert js.angle_rad_to_pulse_us(0.0) == 1500
    # +135° → calibration 270° → 2500
    assert js.angle_rad_to_pulse_us(math.radians(135)) == 2500
    # -135° → calibration 0° → 500
    assert js.angle_rad_to_pulse_us(math.radians(-135)) == 500


def test_joint_servo_trim_then_inverted_then_calibration():
    """Order: trim, invert, then look up the calibrated table."""
    samples = ((0.0, 500), (135.0, 1500), (270.0, 2500))
    js = JointServo(
        channel=0,
        profile=_profile(),
        samples=samples,
        zero_offset_deg=135.0,
        trim_deg=10.0,
        inverted=True,
    )
    # 0 rad → +10° (trim) → -10° (invert) → +125° in cal coords → ~1407
    deg_in_cal = -10.0 + 135.0
    expected = interpolate(samples, deg_in_cal)
    assert js.angle_rad_to_pulse_us(0.0) == expected


# ── ServoMap.from_config calibration loading ──────────────────────────────


def test_from_config_auto_loads_calibration():
    sm = ServoMap.from_config(CONFIG)
    # All 18 joints should now have samples populated.
    for js in sm.joints.values():
        assert js.samples is not None
        assert js.zero_offset_deg == 135.0


def test_from_config_uses_calibrated_neutral_for_front_right_coxa():
    """RF1's calibrated neutral (135° in cal coords) is 1360 us — distinct
    from the linear profile's 1500. Asserts ServoMap.from_config wires the
    calibration table into JointServo end-to-end."""
    sm = ServoMap.from_config(CONFIG)
    js = sm.get("front_right", "coxa")
    # Inverting 0° is still 0°, so inversion does not affect this assertion.
    assert js.angle_rad_to_pulse_us(0.0) == 1360


def test_from_config_calibration_false_disables_it():
    sm = ServoMap.from_config(CONFIG, calibration=False)
    for js in sm.joints.values():
        assert js.samples is None
    # And RF1 reverts to the linear profile's center.
    js = sm.get("front_right", "coxa")
    profile = js.profile
    assert js.angle_rad_to_pulse_us(0.0) == profile.angle_deg_to_pulse_us(0)


def test_from_config_explicit_calibration_instance():
    cal = Calibration.load(CAL_PATH)
    sm = ServoMap.from_config(CONFIG, calibration=cal)
    assert sm.get("front_right", "coxa").samples is not None
