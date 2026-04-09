import math
from typing import TYPE_CHECKING

from ..angle import Angle

if TYPE_CHECKING:
    from .leg import Leg


class Coxa:
    def __init__(
        self,
        leg: "Leg",
        length: float = 0.0,
        mount: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        self.leg = leg
        self.length = length
        self.mount = mount
        self.angle = Angle()

    @property
    def rest_angle(self) -> float:
        """Outward direction from the body origin to the mount, in radians."""
        return math.atan2(self.mount[1], self.mount[0])

    @property
    def world_angle(self) -> float:
        """Coxa heading in the body frame: rest direction + joint offset."""
        return self.rest_angle + self.angle.rad

    @property
    def start(self) -> tuple[float, float, float]:
        return (self.mount[0], self.mount[1], self.leg.height)

    @property
    def end(self) -> tuple[float, float, float]:
        from ..kinematics.fk import coxa as fk_coxa

        return fk_coxa.transform(self.leg)
