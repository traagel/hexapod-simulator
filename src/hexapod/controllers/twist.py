"""Constant body-frame twist controller."""

from ..api.dto import RobotState
from ..robot import Robot


class ConstantTwist:
    """Drives the robot at a fixed (vx, vy, omega)."""

    def __init__(self, vx: float = 0.0, vy: float = 0.0, omega: float = 0.0) -> None:
        self.vx = vx
        self.vy = vy
        self.omega = omega
        self._sent = False

    def update(self, robot: Robot, state: RobotState, dt: float) -> None:
        if not self._sent:
            robot.set_twist(self.vx, self.vy, self.omega)
            self._sent = True
