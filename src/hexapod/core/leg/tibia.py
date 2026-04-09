from typing import TYPE_CHECKING

from ..angle import Angle

if TYPE_CHECKING:
    from .leg import Leg


class Tibia:
    def __init__(self, leg: "Leg", length: float = 0.0) -> None:
        self.leg = leg
        self.length = length
        self.angle = Angle()

    @property
    def start(self) -> tuple[float, float, float]:
        return self.leg.femur.end

    @property
    def end(self) -> tuple[float, float, float]:
        from ..kinematics.fk import tibia as fk_tibia

        return fk_tibia.transform(self.leg)
