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

    legs: dict[tuple[Segment, Side], dict[str, Any]] = {}
    for key, (x, y) in raw["mounts"].items():
        segment = _SEGMENT_KEYS[key]
        legs[(segment, Side.LEFT)] = {
            "mount": (x, y),
            "joints": {
                name: {"length": j["length"], "angle": j["angle"]}
                for name, j in joints.items()
            },
        }
        legs[(segment, Side.RIGHT)] = {
            "mount": (x, -y),
            "joints": {
                name: {"length": j["length"], "angle": -j["angle"]}
                for name, j in joints.items()
            },
        }

    return {"height": raw["height"], "legs": legs}
