from . import coxa, femur, tibia
from ...leg import Leg


def solve(leg: Leg) -> tuple[float, float, float]:
    """Return foot (x, y, z) in the coxa frame."""
    return tibia.transform(leg)


__all__ = ["coxa", "femur", "tibia", "solve"]
