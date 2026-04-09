"""Forward kinematics for the coxa joint."""

import math

from ...leg import Leg


def transform(leg: Leg) -> tuple[float, float, float]:
    """Return the coxa-femur joint position.

    The coxa rotates only in the xy plane, so z is just the body height.
    """
    angle = leg.coxa.world_angle
    length = leg.coxa.length
    mx, my = leg.coxa.mount
    x = mx + length * math.cos(angle)
    y = my + length * math.sin(angle)
    z = leg.height
    return (x, y, z)
