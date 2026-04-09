"""Hexapod simulation/control package.

Layered architecture:
  core/        pure domain (kinematics, gait, pose) — no I/O
  drivers/    output abstraction (sim, servos)
  api/        DTOs, command/state types
  robot.py    public facade — Robot.step(dt), Robot.command(...), Robot.state()
  controllers/ input producers (joysticks, planners)
  viz/        visualization consumers
  transports/ wire protocols (websocket, rest, zmq, ...)
"""

from .core import Coxa, Femur, Hexapod, Leg, Legs, Pose, Segment, Side, Tibia
from .robot import Robot

__all__ = [
    "Coxa",
    "Femur",
    "Hexapod",
    "Leg",
    "Legs",
    "Pose",
    "Robot",
    "Segment",
    "Side",
    "Tibia",
]
