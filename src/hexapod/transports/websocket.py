"""WebSocket transport — bidirectional JSON.

Server protocol:
  → client receives:  {"type": "state", "data": <RobotState dict>}
  ← client may send:  {"type": "twist", "vx": float, "vy": float, "omega": float}
                      {"type": "stop"}
                      {"type": "set_pose", "x": float, "y": float, "yaw": float}

The transport never reaches into core. It only calls Robot.* methods.
"""

import asyncio
import json
import logging

import websockets
from websockets.asyncio.server import ServerConnection, serve

from ..robot import Robot

log = logging.getLogger(__name__)


class WebSocketServer:
    def __init__(
        self,
        robot: Robot,
        host: str = "127.0.0.1",
        port: int = 8765,
        fps: int = 30,
    ) -> None:
        self.robot = robot
        self.host = host
        self.port = port
        self.fps = fps
        self._clients: set[ServerConnection] = set()

    async def _handler(self, websocket: ServerConnection) -> None:
        self._clients.add(websocket)
        log.info("client connected (%d total)", len(self._clients))
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                self._dispatch(msg)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            log.info("client disconnected (%d total)", len(self._clients))

    def _dispatch(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "twist":
            self.robot.set_twist(
                float(msg.get("vx", 0.0)),
                float(msg.get("vy", 0.0)),
                float(msg.get("omega", 0.0)),
            )
        elif kind == "stop":
            self.robot.stop()
        elif kind == "set_pose":
            self.robot.set_body_pose(
                float(msg.get("x", 0.0)),
                float(msg.get("y", 0.0)),
                float(msg.get("yaw", 0.0)),
            )
        elif kind == "set_height":
            self.robot.set_body_height(float(msg.get("z", 5.0)))
        elif kind == "set_step_length":
            self.robot.set_step_length(float(msg.get("length", 4.0)))
        elif kind == "set_stance_radius":
            self.robot.set_stance_radius(float(msg.get("radius", 9.8)))

    async def _broadcast_loop(self) -> None:
        dt = 1.0 / self.fps
        while True:
            self.robot.step(dt)
            if self._clients:
                payload = json.dumps(
                    {"type": "state", "data": self.robot.state().to_dict()}
                )
                stale: list[ServerConnection] = []
                for ws in self._clients:
                    try:
                        await ws.send(payload)
                    except websockets.ConnectionClosed:
                        stale.append(ws)
                for ws in stale:
                    self._clients.discard(ws)
            await asyncio.sleep(dt)

    async def serve(self) -> None:
        log.info("hexapod ws server on ws://%s:%d", self.host, self.port)
        async with serve(self._handler, self.host, self.port):
            await self._broadcast_loop()

    def run(self) -> None:
        logging.basicConfig(level=logging.INFO)
        asyncio.run(self.serve())
