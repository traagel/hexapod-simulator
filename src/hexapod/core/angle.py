import math


class Angle:
    """Joint angle stored once, exposed as both radians and degrees."""

    __slots__ = ("_rad",)

    def __init__(self, rad: float = 0.0) -> None:
        self._rad = rad

    @classmethod
    def from_deg(cls, deg: float) -> "Angle":
        return cls(math.radians(deg))

    @classmethod
    def from_rad(cls, rad: float) -> "Angle":
        return cls(rad)

    @property
    def rad(self) -> float:
        return self._rad

    @rad.setter
    def rad(self, value: float) -> None:
        self._rad = value

    @property
    def deg(self) -> float:
        return math.degrees(self._rad)

    @deg.setter
    def deg(self, value: float) -> None:
        self._rad = math.radians(value)

    def __repr__(self) -> str:
        return f"Angle(rad={self._rad:.4f}, deg={self.deg:.2f})"
