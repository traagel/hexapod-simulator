from typing import TYPE_CHECKING

from ..enums import Segment, Side
from .coxa import Coxa
from .femur import Femur
from .tibia import Tibia

if TYPE_CHECKING:
    from ..hexapod import Hexapod


class Leg:
    def __init__(self, segment: Segment, side: Side, hexapod: "Hexapod") -> None:
        self.segment = segment
        self.side = side
        self.hexapod = hexapod
        self.coxa = Coxa(self)
        self.femur = Femur(self)
        self.tibia = Tibia(self)

    @property
    def height(self) -> float:
        return self.hexapod.height
