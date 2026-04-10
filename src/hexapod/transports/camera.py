"""MJPEG streaming server — serves webcam frames over HTTP.

Runs in the same asyncio event loop as the WebSocket server.  One background
task captures frames from the camera (via a thread executor so the blocking
cv2.read() doesn't stall the loop); each connected HTTP client receives the
latest JPEG as a multipart/x-mixed-replace stream.

    GET /stream  →  multipart MJPEG
    GET /         →  200 OK (health check)

Requires ``opencv-python-headless`` (optional ``[camera]`` extra).
"""

from __future__ import annotations

import asyncio
import logging

import cv2

log = logging.getLogger(__name__)

_BOUNDARY = b"frame"


class MJPEGServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8766,
        device: int | str = 0,
        fps: int = 15,
        quality: int = 70,
    ) -> None:
        self.host = host
        self.port = port
        self.device = device
        self.fps = fps
        self.quality = quality

        self._cap: cv2.VideoCapture | None = None
        self._latest_frame: bytes = b""
        self._frame_event = asyncio.Event()
        self._running = False
        self._server: asyncio.Server | None = None

    # ── lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> bool:
        """Open the camera and start serving.  Returns False if no camera."""
        loop = asyncio.get_running_loop()
        cap = await loop.run_in_executor(None, cv2.VideoCapture, self.device)
        if not cap.isOpened():
            log.warning("camera device %s not available — skipping", self.device)
            cap.release()
            return False

        self._cap = cap
        self._running = True
        asyncio.create_task(self._capture_loop())
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port,
        )
        log.info("mjpeg server on http://%s:%d/stream", self.host, self.port)
        return True

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._cap:
            self._cap.release()

    def stream_url(self) -> str:
        return f"http://{self.host}:{self.port}/stream"

    # ── capture loop (single producer) ────────────────────────────────

    async def _capture_loop(self) -> None:
        loop = asyncio.get_running_loop()
        period = 1.0 / self.fps
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.quality]

        while self._running:
            ret, frame = await loop.run_in_executor(None, self._cap.read)
            if ret:
                _, buf = cv2.imencode(".jpg", frame, encode_params)
                self._latest_frame = buf.tobytes()
                self._frame_event.set()
                self._frame_event.clear()
            await asyncio.sleep(period)

    # ── HTTP handler (one per client) ─────────────────────────────────

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        # Read the HTTP request line to determine the path.
        request_line = await reader.readline()
        # Drain remaining headers.
        while (await reader.readline()) != b"\r\n":
            pass

        path = request_line.split(b" ")[1] if b" " in request_line else b"/"

        if path != b"/stream":
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain\r\n"
                b"Content-Length: 2\r\n\r\nok"
            )
            await writer.drain()
            writer.close()
            return

        # MJPEG multipart response.
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: multipart/x-mixed-replace; boundary=" + _BOUNDARY + b"\r\n"
            b"Cache-Control: no-cache\r\n"
            b"Connection: close\r\n\r\n"
        )

        period = 1.0 / self.fps
        try:
            while self._running:
                frame = self._latest_frame
                if frame:
                    writer.write(
                        b"--" + _BOUNDARY + b"\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame + b"\r\n"
                    )
                    await writer.drain()
                await asyncio.sleep(period)
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()
