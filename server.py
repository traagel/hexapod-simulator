"""Run the hexapod as a websocket server backed by either the in-memory
simulator or a real Servo2040 over USB serial. Also serves the built
frontend on an HTTP port and (optionally) advertises itself over mDNS.

    # simulator (default)
    uv run python server.py

    # real hardware
    uv sync --extra hardware
    uv run python server.py --device /dev/ttyACM0

The frontend is served from frontend_v2/dist. Build it with:

    cd frontend_v2 && bun install && bun run build

Then open http://hexapod.local:8080/ (or http://<host-ip>:8080/).
"""

import argparse
from pathlib import Path

from hexapod import Hexapod, Robot
from hexapod.core.gait import TripodGait
from hexapod.drivers import SimDriver
from hexapod.transports import WebSocketServer
from hexapod.transports.mdns import advertise
from hexapod.transports.static import StaticServer

CONFIG = "config/hexapod.yaml"
REPO = Path(__file__).resolve().parent


def build_driver(device: str | None, hexapod: Hexapod):
    """Pick the simulator or the USB serial driver based on `device`."""
    if device is None:
        return SimDriver(hexapod)
    # Imported lazily so the simulator path doesn't need pyserial.
    from hexapod.drivers.serial import HostSerialDriver
    from hexapod.drivers.servo import ServoMap

    servo_map = ServoMap.from_config(CONFIG)
    return HostSerialDriver(servo_map, device=device)


def resolve_static_dir(explicit: str | None) -> Path | None:
    """Locate the built frontend bundle, or None to disable static serving."""
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else None
    candidate = REPO / "frontend_v2" / "dist"
    return candidate if candidate.is_dir() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device",
        default=None,
        help="USB serial device to drive real hardware (e.g. /dev/ttyACM0). "
        "Omit for the in-memory simulator.",
    )
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--host", default="0.0.0.0",
                        help="Bind address for WS and static HTTP (default: 0.0.0.0).")
    parser.add_argument("--port", type=int, default=8765,
                        help="WebSocket port (default: 8765).")
    parser.add_argument("--static-port", type=int, default=8080,
                        help="HTTP port for the frontend (default: 8080).")
    parser.add_argument("--static-dir", default=None,
                        help="Directory to serve. Defaults to frontend_v2/dist.")
    parser.add_argument("--no-static", action="store_true",
                        help="Disable the built-in static file server.")
    parser.add_argument("--mdns-name", default="hexapod",
                        help="mDNS name; reach the frontend at <name>.local.")
    parser.add_argument("--no-mdns", action="store_true",
                        help="Disable mDNS advertisement.")
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

    # Static files.
    static = None
    if not args.no_static:
        static_dir = resolve_static_dir(args.static_dir)
        if static_dir is None:
            print("static: frontend_v2/dist not found — "
                  "build it with `cd frontend_v2 && bun run build`, "
                  "or pass --static-dir / --no-static to silence this.")
        else:
            static = StaticServer(static_dir, host=args.host, port=args.static_port)
            static.start()
            print(f"static: http://{args.host}:{args.static_port}/ -> {static_dir}")

    # mDNS.
    mdns = None
    if not args.no_mdns and static is not None:
        mdns = advertise(args.mdns_name, args.static_port)
        print(f"mdns: http://{args.mdns_name}.local:{args.static_port}/")

    backend = "sim" if args.device is None else f"hardware ({args.device})"
    print(f"hexapod server: {backend} on ws://{args.host}:{args.port}")

    server = WebSocketServer(
        robot, host=args.host, port=args.port, fps=args.fps, camera=camera,
    )
    try:
        server.run()
    finally:
        driver.close()
        if static is not None:
            static.stop()
        if mdns is not None:
            mdns.close()


if __name__ == "__main__":
    main()
