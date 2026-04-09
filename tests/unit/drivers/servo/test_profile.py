"""ServoProfile: linear angle→pulse map, clamping, YAML loading."""

import math
from pathlib import Path

import pytest

from hexapod.drivers.servo.profile import ServoProfile

REPO = Path(__file__).resolve().parents[4]


def _profile() -> ServoProfile:
    return ServoProfile(
        name="test",
        frequency_hz=50,
        pulse_min_us=500,
        pulse_max_us=2500,
        angle_min_deg=-90,
        angle_max_deg=90,
    )


def test_center_angle_is_midpoint_pulse():
    p = _profile()
    assert p.angle_deg_to_pulse_us(0) == 1500


def test_endpoints_map_to_endpoints():
    p = _profile()
    assert p.angle_deg_to_pulse_us(-90) == 500
    assert p.angle_deg_to_pulse_us(90) == 2500


def test_outside_range_clamps():
    p = _profile()
    assert p.angle_deg_to_pulse_us(-200) == 500
    assert p.angle_deg_to_pulse_us(200) == 2500


def test_radian_helper_matches_degree_helper():
    p = _profile()
    assert p.angle_rad_to_pulse_us(math.pi / 2) == p.angle_deg_to_pulse_us(90)
    assert p.angle_rad_to_pulse_us(0) == p.angle_deg_to_pulse_us(0)


def test_load_bundled_mg996r():
    p = ServoProfile.load(REPO / "config" / "servos" / "mg996r.yaml")
    assert p.name == "mg996r"
    assert p.frequency_hz == 50
    assert p.pulse_min_us == 500
    assert p.pulse_max_us == 2500
    assert p.angle_deg_to_pulse_us(0) == 1500


def test_load_missing_field_raises(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: bad\nfrequency_hz: 50\n")
    with pytest.raises(KeyError):
        ServoProfile.load(bad)
