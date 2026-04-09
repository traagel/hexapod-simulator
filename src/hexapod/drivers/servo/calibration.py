"""Per-servo calibration tables.

A calibration file maps each physical servo (addressed by leg + joint) to a
list of measured ``(commanded_deg, observed_pulse_us)`` samples taken across
the full mechanical travel. At runtime the host interpolates the table
piecewise-linearly to convert an IK joint angle to the pulse width that
actually puts that specific servo at that mechanical angle.

The IK convention puts joint angle 0 at the mechanical neutral, so the
calibration's ``zero_offset_deg`` says where in the table that neutral lives
(typically half the servo's full travel — 135° for a 270° servo).
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

LegName = str   # "front_left", ...
JointName = str  # "coxa" | "femur" | "tibia"
SamplePair = tuple[float, int]   # (commanded_deg, observed_pulse_us)
SampleTable = tuple[SamplePair, ...]


def interpolate(samples: SampleTable, x_deg: float) -> int:
    """Piecewise-linear lookup; clamps to the table's endpoints.

    Samples must be sorted by ``deg`` ascending. Returns the interpolated
    pulse width in microseconds, rounded to the nearest integer.
    """
    if not samples:
        raise ValueError("interpolate: empty sample table")
    if x_deg <= samples[0][0]:
        return samples[0][1]
    if x_deg >= samples[-1][0]:
        return samples[-1][1]
    for (x0, y0), (x1, y1) in zip(samples, samples[1:]):
        if x0 <= x_deg <= x1:
            t = (x_deg - x0) / (x1 - x0)
            return int(round(y0 + t * (y1 - y0)))
    return samples[-1][1]  # unreachable; here for type-checker


@dataclass(frozen=True)
class Calibration:
    """All 18 servos' measured angle→pulse tables, loaded from one YAML."""

    profile_name: str
    zero_offset_deg: float
    tables: dict[tuple[LegName, JointName], SampleTable]

    def lookup(
        self, leg: LegName, joint: JointName, deg_centered: float
    ) -> int:
        """Convert a centered joint angle (0 = mechanical neutral) to pulse_us
        using the per-servo table.
        """
        table = self.tables[(leg, joint)]
        return interpolate(table, deg_centered + self.zero_offset_deg)

    def has(self, leg: LegName, joint: JointName) -> bool:
        return (leg, joint) in self.tables

    @classmethod
    def load(cls, path: str | Path) -> "Calibration":
        path = Path(path)
        with open(path) as f:
            d = yaml.safe_load(f)

        tables: dict[tuple[LegName, JointName], SampleTable] = {}
        for leg_name, joint_block in d["legs"].items():
            for joint_name, samples in joint_block.items():
                rows = tuple(
                    (float(s["deg"]), int(round(float(s["pulse_us"]))))
                    for s in samples
                )
                # Sanity: ensure sorted ascending by deg.
                if any(rows[i][0] >= rows[i + 1][0] for i in range(len(rows) - 1)):
                    raise ValueError(
                        f"{path}: {leg_name}.{joint_name} samples must be "
                        f"sorted ascending by `deg`"
                    )
                tables[(leg_name, joint_name)] = rows

        return cls(
            profile_name=str(d["servo"]),
            zero_offset_deg=float(d.get("zero_offset_deg", 0.0)),
            tables=tables,
        )
