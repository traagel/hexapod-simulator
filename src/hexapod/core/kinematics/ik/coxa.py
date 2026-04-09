"""Coxa angle component of the IK solution."""

from ...leg import Leg


def solve(leg: Leg, target: tuple[float, float, float]) -> float:
    from . import solve as solve_all

    return solve_all(leg, target)[0]
