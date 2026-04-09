"""Load hexapod configuration from a YAML file."""

from pathlib import Path
from typing import Any

import yaml

from .enums import Segment, Side

_SEGMENT_KEYS: dict[str, Segment] = {
    "front": Segment.FRONT,
    "mid": Segment.MID,
    "rear": Segment.REAR,
}


def load(path: str | Path) -> dict[str, Any]:
    """Read a hexapod YAML config and expand the symmetric mounts.

    Returns a dict with `height` and `legs`, where `legs` maps
    `(Segment, Side)` to a per-leg config dict.
    """
    with open(path) as f:
        raw = yaml.safe_load(f)

    joints = {name: raw[name] for name in ("coxa", "femur", "tibia")}

    def _joint_dict(j: dict[str, Any], flip_angle: bool) -> dict[str, Any]:
        out: dict[str, Any] = {
            "length": j["length"],
            "angle": -j["angle"] if flip_angle else j["angle"],
        }
        # `bend` is mechanical (same physical part on both sides), so it is
        # NOT sign-flipped for the right side.
        if "bend" in j:
            out["bend"] = j["bend"]
        return out

    legs: dict[tuple[Segment, Side], dict[str, Any]] = {}
    for key, (x, y) in raw["mounts"].items():
        segment = _SEGMENT_KEYS[key]
        legs[(segment, Side.LEFT)] = {
            "mount": (x, y),
            "joints": {n: _joint_dict(j, flip_angle=False) for n, j in joints.items()},
        }
        legs[(segment, Side.RIGHT)] = {
            "mount": (x, -y),
            "joints": {n: _joint_dict(j, flip_angle=True) for n, j in joints.items()},
        }

    return {"height": raw["height"], "legs": legs}
