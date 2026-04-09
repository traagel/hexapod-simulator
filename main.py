"""Tiny entry point — wires the layers together and runs the matplotlib viz."""

from hexapod import Hexapod, Robot
from hexapod.controllers import ConstantTwist
from hexapod.core.gait import TripodGait
from hexapod.drivers import SimDriver
from hexapod.viz import run


def main() -> None:
    hexapod = Hexapod.from_config("config/hexapod.yaml")
    gait = TripodGait(hexapod, step_length=4, lift_height=3)
    robot = Robot(hexapod, gait, SimDriver(hexapod), cycle_seconds=2.0)

    controller = ConstantTwist(vx=2.0, vy=0.0, omega=0.3)
    run(robot, controller=controller, seconds=10.0, fps=30)


if __name__ == "__main__":
    main()
