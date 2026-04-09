"""Shared rotation/translation math used by IK and FK."""

import math


def rot_z(angle: float) -> tuple[tuple[float, float], tuple[float, float]]:
    c, s = math.cos(angle), math.sin(angle)
    return ((c, -s), (s, c))
