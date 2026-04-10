"""SimDriver — writes joint commands straight into an in-memory Hexapod."""

from ..api.dto import JointAngles
from ..core.hexapod import Hexapod
from .base import LegKey


class SimDriver:
    def __init__(self, hexapod: Hexapod) -> None:
        self.hexapod = hexapod

    def write(self, commands: dict[LegKey, JointAngles]) -> None:
        for (segment, side), angles in commands.items():
            leg = self.hexapod.legs.get(segment, side)
            leg.coxa.angle.rad = angles.coxa
            leg.femur.angle.rad = angles.femur
            leg.tibia.angle.rad = angles.tibia

    def read(self) -> dict[LegKey, JointAngles] | None:
        result: dict[LegKey, JointAngles] = {}
        for leg in self.hexapod.legs:
            result[(leg.segment, leg.side)] = JointAngles(
                coxa=leg.coxa.angle.rad,
                femur=leg.femur.angle.rad,
                tibia=leg.tibia.angle.rad,
            )
        return result

    def read_contacts(self) -> dict[LegKey, bool] | None:
        """Synthetic contact: foot world-frame z near ground (within a few mm)."""
        threshold = 0.05
        pose = self.hexapod.pose
        height = self.hexapod.height
        result: dict[LegKey, bool] = {}
        for leg in self.hexapod.legs:
            world_z = pose.transform(leg.tibia.end, pivot_z=height)[2]
            result[(leg.segment, leg.side)] = world_z <= threshold
        return result

    def close(self) -> None:
        pass
