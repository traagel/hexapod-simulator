"""Run the hexapod as a websocket server backed by either the in-memory
simulator or a real Servo2040 over USB serial.

    # simulator (default)
    uv run python server.py

    # real hardware
    uv sync --extra hardware
    uv run python server.py --device /dev/ttyACM0

Then open frontend/index.html in your browser.
"""

import argparse

from hexapod import Hexapod, Robot
from hexapod.core.gait import TripodGait
from hexapod.drivers import SimDriver
from hexapod.transports import WebSocketServer

CONFIG = "config/hexapod.yaml"


def build_driver(device: str | None, hexapod: Hexapod):
    """Pick the simulator or the USB serial driver based on `device`."""
    if device is None:
        return SimDriver(hexapod)
    # Imported lazily so the simulator path doesn't need pyserial.
    from hexapod.drivers.serial import HostSerialDriver
    from hexapod.drivers.servo import ServoMap

    servo_map = ServoMap.from_config(CONFIG)
    return HostSerialDriver(servo_map, device=device)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device",
        default=None,
        help="USB serial device to drive real hardware (e.g. /dev/ttyACM0). "
        "Omit for the in-memory simulator.",
    )
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--camera-port", type=int, default=8766)
    parser.add_argument("--camera-device", default=0,
                        help="Camera index (int) or device path (e.g. /dev/video0).")
    parser.add_argument("--no-camera", action="store_true",
                        help="Disable the webcam stream even if opencv is installed.")
    args = parser.parse_args()

    hexapod = Hexapod.from_config(CONFIG)
    gait = TripodGait(
        hexapod,
        step_length=10,
        lift_height=3,
        neutral_radius=14,
    )
    driver = build_driver(args.device, hexapod)
    robot = Robot(hexapod, gait, driver, cycle_seconds=0.6)

    # Optional camera — lazy-import so server works without opencv.
    camera = None
    if not args.no_camera:
        try:
            from hexapod.transports.camera import MJPEGServer

            cam_device = args.camera_device
            try:
                cam_device = int(cam_device)
            except (ValueError, TypeError):
                pass
            camera = MJPEGServer(
                host=args.host, port=args.camera_port, device=cam_device,
            )
        except ImportError:
            pass

    backend = "sim" if args.device is None else f"hardware ({args.device})"
    print(f"hexapod server: {backend} on ws://{args.host}:{args.port}")

    server = WebSocketServer(
        robot, host=args.host, port=args.port, fps=args.fps, camera=camera,
    )
    try:
        server.run()
    finally:
        driver.close()


if __name__ == "__main__":
    main()
