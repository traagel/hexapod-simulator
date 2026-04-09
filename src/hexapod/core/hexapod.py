from pathlib import Path

from . import config
from .enums import Segment, Side
from .leg import Leg
from .legs import Legs
from .pose import Pose


class Hexapod:
    def __init__(self, height: float) -> None:
        self.height = height
        self.pose = Pose()
        self.legs = Legs()
        for segment in Segment:
            for side in Side:
                self.legs.add(Leg(segment, side, hexapod=self))

    @classmethod
    def from_config(cls, path: str | Path) -> "Hexapod":
        cfg = config.load(path)
        hexapod = cls.__new__(cls)
        hexapod.height = cfg["height"]
        hexapod.pose = Pose()
        hexapod.legs = Legs()
        for (segment, side), leg_cfg in cfg["legs"].items():
            leg = Leg(segment, side, hexapod=hexapod)
            leg.coxa.mount = tuple(leg_cfg["mount"])
            for name in ("coxa", "femur", "tibia"):
                joint = getattr(leg, name)
                joint_cfg = leg_cfg["joints"][name]
                joint.length = joint_cfg["length"]
                joint.angle.deg = joint_cfg["angle"]
                # Optional mechanical bend (currently only the tibia has one).
                if "bend" in joint_cfg and hasattr(joint, "bend"):
                    joint.bend.deg = joint_cfg["bend"]
            hexapod.legs.add(leg)
        return hexapod
