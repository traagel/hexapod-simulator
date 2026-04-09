"""Controller protocol — input layer above the Robot facade."""

from typing import Protocol

from ..api.dto import RobotState
from ..robot import Robot


class Controller(Protocol):
    """Reads state, issues commands. Called once per tick by the run loop."""

    def update(self, robot: Robot, state: RobotState, dt: float) -> None: ...
