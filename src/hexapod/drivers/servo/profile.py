"""Servo profile — describes one servo model's electrical/mechanical map.

A profile is the linear angle→pulse mapping defined by two anchor points:
``(angle_min_deg, pulse_min_us)`` and ``(angle_max_deg, pulse_max_us)``.
Inside that range it's linear; outside it's clamped.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ServoProfile:
    name: str
    frequency_hz: float
    pulse_min_us: int
    pulse_max_us: int
    angle_min_deg: float
    angle_max_deg: float
    # Optional physical-speed limit. Informational on the host; the MCU
    # smoother is the thing that actually enforces it.
    max_speed_dps: float | None = None

    def angle_deg_to_pulse_us(self, angle_deg: float) -> int:
        a_min, a_max = self.angle_min_deg, self.angle_max_deg
        a = max(a_min, min(a_max, angle_deg))
        t = (a - a_min) / (a_max - a_min)
        pulse = self.pulse_min_us + t * (self.pulse_max_us - self.pulse_min_us)
        return int(round(pulse))

    def angle_rad_to_pulse_us(self, angle_rad: float) -> int:
        return self.angle_deg_to_pulse_us(math.degrees(angle_rad))

    @classmethod
    def load(cls, path: str | Path) -> "ServoProfile":
        path = Path(path)
        with open(path) as f:
            d = yaml.safe_load(f)
        return cls(
            name=d.get("name", path.stem),
            frequency_hz=float(d["frequency_hz"]),
            pulse_min_us=int(d["pulse_min_us"]),
            pulse_max_us=int(d["pulse_max_us"]),
            angle_min_deg=float(d["angle_min_deg"]),
            angle_max_deg=float(d["angle_max_deg"]),
            max_speed_dps=(
                float(d["max_speed_dps"]) if "max_speed_dps" in d else None
            ),
        )
