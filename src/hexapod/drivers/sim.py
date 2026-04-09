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
        """Synthetic contact: foot z near 0 (within a few mm)."""
        threshold = 0.05
        return {
            (leg.segment, leg.side): leg.tibia.end[2] <= threshold
            for leg in self.hexapod.legs
        }

    def close(self) -> None:
        pass
