"""Forward kinematics for the femur joint."""

import math

from ...leg import Leg


def transform(leg: Leg) -> tuple[float, float, float]:
    """Return the femur-tibia joint position in the body frame.

    The femur rotates in the vertical plane containing the coxa's outward
    direction. femur.angle = 0 is horizontal, positive lifts the knee up.
    """
    coxa_angle = leg.coxa.world_angle
    femur_angle = leg.femur.angle.rad
    length = leg.femur.length

    horizontal = length * math.cos(femur_angle)
    vertical = length * math.sin(femur_angle)

    cx, cy, cz = leg.coxa.end
    return (
        cx + horizontal * math.cos(coxa_angle),
        cy + horizontal * math.sin(coxa_angle),
        cz + vertical,
    )
