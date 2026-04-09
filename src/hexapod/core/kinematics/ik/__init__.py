"""Inverse kinematics for a 3-DOF leg.

Coxa yaws to point at the target, then femur+tibia form a 2-link planar
chain in the resulting vertical plane. Knee-up solution is selected.
"""

import math

from ...leg import Leg
from . import coxa, femur, tibia


def solve(leg: Leg, target: tuple[float, float, float]) -> tuple[float, float, float]:
    """Return (coxa, femur, tibia) angles that place the foot at target.

    Target is in the body frame. If the target is outside the femur+tibia
    workspace, it is clamped to the nearest reachable point along the same
    direction from the femur joint — the leg reaches as far as it can rather
    than throwing.

    Angles match the FK convention:
      - coxa.angle:  offset from coxa.rest_angle, in the xy plane
      - femur.angle: pitch from horizontal, +up
      - tibia.angle: bend relative to femur, +bends knee down
    """
    tx, ty, tz = target
    mx, my = leg.coxa.mount

    # 1. Coxa: yaw to aim at the target in the xy plane.
    dx, dy = tx - mx, ty - my
    coxa_world = math.atan2(dy, dx)
    coxa_offset = coxa_world - leg.coxa.rest_angle

    # 2. Reduce to a 2D problem in the leg's vertical plane.
    horizontal = math.hypot(dx, dy)
    r = horizontal - leg.coxa.length
    dz = tz - leg.height

    L1 = leg.femur.length
    L2 = leg.tibia.length
    d = math.hypot(r, dz)

    # 3. Clamp to the reachable annulus [|L1-L2|, L1+L2]. A small inset keeps
    #    the IK away from the singular fully-extended / fully-folded poses.
    eps = 1e-3
    d_min = abs(L1 - L2) + eps
    d_max = L1 + L2 - eps
    if d > d_max or d < d_min:
        target_d = max(d_min, min(d_max, d))
        if d < 1e-9:
            # Direction is undefined at exactly the femur joint — push outward.
            r, dz = target_d, 0.0
        else:
            scale = target_d / d
            r *= scale
            dz *= scale
        d = target_d

    # 4. Two-link planar IK, knee-up solution.
    alpha = math.atan2(dz, r)
    cos_beta = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
    beta = math.acos(max(-1.0, min(1.0, cos_beta)))
    femur_angle = alpha + beta

    # Tibia absolute pitch from the foot position relative to the knee.
    knee_x = L1 * math.cos(femur_angle)
    knee_z = L1 * math.sin(femur_angle)
    phi = math.atan2(dz - knee_z, r - knee_x)
    # Subtract the mechanical bend so the servo command produces the same
    # physical pose with a bent tibia as a straight one would.
    tibia_angle = femur_angle - phi - leg.tibia.bend.rad

    return (coxa_offset, femur_angle, tibia_angle)


def apply(leg: Leg, target: tuple[float, float, float]) -> None:
    """Solve IK for `target` and write the angles into `leg`."""
    c, f, t = solve(leg, target)
    leg.coxa.angle.rad = c
    leg.femur.angle.rad = f
    leg.tibia.angle.rad = t


__all__ = ["coxa", "femur", "tibia", "solve", "apply"]
