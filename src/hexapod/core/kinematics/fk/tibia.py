"""Forward kinematics for the tibia joint."""

import math

from ...leg import Leg


def transform(leg: Leg) -> tuple[float, float, float]:
    """Return the foot position in the body frame.

    tibia.angle is measured relative to the femur: 0 keeps the tibia
    collinear with the femur, positive bends the knee downward.
    """
    coxa_angle = leg.coxa.world_angle
    femur_angle = leg.femur.angle.rad
    tibia_angle = leg.tibia.angle.rad
    length = leg.tibia.length

    pitch = femur_angle - tibia_angle
    horizontal = length * math.cos(pitch)
    vertical = length * math.sin(pitch)

    fx, fy, fz = leg.femur.end
    return (
        fx + horizontal * math.cos(coxa_angle),
        fy + horizontal * math.sin(coxa_angle),
        fz + vertical,
    )
