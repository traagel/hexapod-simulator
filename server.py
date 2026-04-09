"""Run the hexapod simulation as a websocket server.

uv run python server.py
open frontend/index.html in your browser
"""

from hexapod import Hexapod, Robot
from hexapod.core.gait import TripodGait
from hexapod.drivers import SimDriver
from hexapod.transports import WebSocketServer


def main() -> None:
    hexapod = Hexapod.from_config("config/hexapod.yaml")
    gait = TripodGait(hexapod, step_length=4, lift_height=3)
    robot = Robot(hexapod, gait, SimDriver(hexapod), cycle_seconds=0.6)

    server = WebSocketServer(robot, host="127.0.0.1", port=8765, fps=30)
    server.run()


if __name__ == "__main__":
    main()
