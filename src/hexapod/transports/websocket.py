"""WebSocket transport — bidirectional JSON.

Server protocol:
  → client receives:  {"type": "state", "data": <RobotState dict>}
  ← client may send:  {"type": "twist", "vx", "vy", "omega"}
                      {"type": "stop"}
                      {"type": "set_pose", "x", "y", "yaw"}
                      {"type": "set_height", "z"}
                      {"type": "set_step_length", "length"}
                      {"type": "set_stance_radius", "radius"}
                      {"type": "set_foot_target", "leg", "x", "y", "z"}
                          leg ∈ {front_left, front_right, mid_left, mid_right,
                                 rear_left, rear_right}

The transport never reaches into core. It only calls Robot.* methods.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import websockets
from websockets.asyncio.server import ServerConnection, serve

from ..core.enums import Segment, Side
from ..robot import Robot

if TYPE_CHECKING:
    from .camera import MJPEGServer

log = logging.getLogger(__name__)

_LEG_KEYS: dict[str, tuple[Segment, Side]] = {
    "front_left":  (Segment.FRONT, Side.LEFT),
    "front_right": (Segment.FRONT, Side.RIGHT),
    "mid_left":    (Segment.MID,   Side.LEFT),
    "mid_right":   (Segment.MID,   Side.RIGHT),
    "rear_left":   (Segment.REAR,  Side.LEFT),
    "rear_right":  (Segment.REAR,  Side.RIGHT),
}


class WebSocketServer:
    def __init__(
        self,
        robot: Robot,
        host: str = "127.0.0.1",
        port: int = 8765,
        fps: int = 30,
        camera: MJPEGServer | None = None,
    ) -> None:
        self.robot = robot
        self.host = host
        self.port = port
        self.fps = fps
        self.camera = camera
        self._camera_url: str | None = None
        self._clients: set[ServerConnection] = set()

    async def _handler(self, websocket: ServerConnection) -> None:
        self._clients.add(websocket)
        log.info("client connected (%d total)", len(self._clients))
        if self._camera_url:
            await websocket.send(json.dumps({
                "type": "config",
                "camera_url": self._camera_url,
            }))
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
        elif kind == "set_foot_target":
            leg_name = msg.get("leg")
            leg = _LEG_KEYS.get(leg_name) if isinstance(leg_name, str) else None
            if leg is not None:
                self.robot.set_foot_target(
                    leg,
                    (
                        float(msg.get("x", 0.0)),
                        float(msg.get("y", 0.0)),
                        float(msg.get("z", 0.0)),
                    ),
                )

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
        if self.camera:
            ok = await self.camera.start()
            if ok:
                self._camera_url = self.camera.stream_url()

        log.info("hexapod ws server on ws://%s:%d", self.host, self.port)
        try:
            async with serve(self._handler, self.host, self.port):
                await self._broadcast_loop()
        finally:
            if self.camera:
                await self.camera.stop()

    def run(self) -> None:
        logging.basicConfig(level=logging.INFO)
        asyncio.run(self.serve())
