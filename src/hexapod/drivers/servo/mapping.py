"""Per-joint servo configuration: channel, trim, direction, profile.

Loaded from the `servos:` section of the hexapod YAML. The result is an
18-entry table addressed by ``(leg_name, joint_name)``.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

from .calibration import Calibration, SampleTable, interpolate
from .profile import ServoProfile

JointName = str  # "coxa" | "femur" | "tibia"
LegName = str    # "front_left" | "front_right" | "mid_left" | ...

NUM_CHANNELS = 18

LEG_NAMES: tuple[LegName, ...] = (
    "front_left",
    "front_right",
    "mid_left",
    "mid_right",
    "rear_left",
    "rear_right",
)

JOINT_NAMES: tuple[JointName, ...] = ("coxa", "femur", "tibia")


@dataclass(frozen=True)
class JointServo:
    """One servo: which channel it's wired to plus per-instance corrections.

    The angle conversion applies trim first, then optionally inverts, then:
      * if `samples` is set, looks up the per-servo calibration table
        (piecewise-linear, centered around `zero_offset_deg`); otherwise
      * falls back to the profile's nominal linear map.

    `trim_deg` is still useful even with calibration — it lets you fine-tune
    a servo's zero without re-measuring the whole table.
    """

    channel: int
    profile: ServoProfile
    trim_deg: float = 0.0
    inverted: bool = False
    samples: SampleTable | None = None
    zero_offset_deg: float = 0.0

    def angle_rad_to_pulse_us(self, angle_rad: float) -> int:
        deg = math.degrees(angle_rad) + self.trim_deg
        if self.inverted:
            deg = -deg
        if self.samples is not None:
            return interpolate(self.samples, deg + self.zero_offset_deg)
        return self.profile.angle_deg_to_pulse_us(deg)


class ServoMap:
    """All 18 servos, addressed by (leg_name, joint_name)."""

    def __init__(
        self, joints: dict[tuple[LegName, JointName], JointServo]
    ) -> None:
        self._joints = joints
        # Reverse lookup also catches duplicate channels at construction time.
        by_channel: dict[int, JointServo] = {}
        for js in joints.values():
            if js.channel in by_channel:
                raise ValueError(f"duplicate servo channel {js.channel}")
            by_channel[js.channel] = js
        self._by_channel = by_channel

    def get(self, leg: LegName, joint: JointName) -> JointServo:
        return self._joints[(leg, joint)]

    @property
    def joints(self) -> dict[tuple[LegName, JointName], JointServo]:
        return self._joints

    @property
    def by_channel(self) -> dict[int, JointServo]:
        return self._by_channel

    @classmethod
    def from_config(
        cls,
        hexapod_yaml: str | Path,
        profiles_dir: str | Path | None = None,
        calibration: Calibration | str | Path | bool | None = None,
    ) -> "ServoMap":
        """Load a ServoMap from the `servos:` section of a hexapod config.

        ``profiles_dir`` defaults to ``<hexapod_yaml_dir>/servos``.

        ``calibration`` controls per-servo measured tables:
          * ``None`` (default) — auto-discover at
            ``<hexapod_yaml_dir>/calibration/<profile>.yaml`` if present.
          * ``False`` — disable calibration entirely; use the linear profile.
          * ``str`` / ``Path`` — load from this file.
          * ``Calibration`` — use the already-loaded instance.
        """
        path = Path(hexapod_yaml)
        with open(path) as f:
            cfg = yaml.safe_load(f)
        if "servos" not in cfg:
            raise ValueError(f"{path}: missing top-level `servos` section")

        servos_cfg = cfg["servos"]
        if profiles_dir is None:
            profiles_dir = path.parent / "servos"
        profile_name = servos_cfg["profile"]
        profile = ServoProfile.load(Path(profiles_dir) / f"{profile_name}.yaml")

        # Resolve calibration argument.
        cal: Calibration | None
        if calibration is None:
            auto = path.parent / "calibration" / f"{profile_name}.yaml"
            cal = Calibration.load(auto) if auto.exists() else None
        elif calibration is False:
            cal = None
        elif isinstance(calibration, Calibration):
            cal = calibration
        elif isinstance(calibration, (str, Path)):
            cal = Calibration.load(calibration)
        else:
            raise TypeError(f"unsupported `calibration` value: {calibration!r}")

        joints: dict[tuple[LegName, JointName], JointServo] = {}
        legs_cfg = servos_cfg["legs"]
        for leg_name in LEG_NAMES:
            if leg_name not in legs_cfg:
                raise ValueError(f"servo config missing leg {leg_name!r}")
            leg_block = legs_cfg[leg_name]
            for joint_name in JOINT_NAMES:
                if joint_name not in leg_block:
                    raise ValueError(
                        f"servo config missing {leg_name}.{joint_name}"
                    )
                entry = leg_block[joint_name]
                samples = (
                    cal.tables.get((leg_name, joint_name)) if cal else None
                )
                joints[(leg_name, joint_name)] = JointServo(
                    channel=int(entry["channel"]),
                    profile=profile,
                    trim_deg=float(entry.get("trim_deg", 0.0)),
                    inverted=bool(entry.get("inverted", False)),
                    samples=samples,
                    zero_offset_deg=cal.zero_offset_deg if cal else 0.0,
                )

        if len(joints) != NUM_CHANNELS:
            raise ValueError(
                f"expected {NUM_CHANNELS} joint servos, got {len(joints)}"
            )
        return cls(joints)
