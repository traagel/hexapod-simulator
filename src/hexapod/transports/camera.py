"""MJPEG streaming server — serves webcam frames over HTTP.

Runs in the same asyncio event loop as the WebSocket server.  A dedicated
thread grabs frames as fast as the camera produces them (discarding all but
the latest), so the stream always shows the most recent image with minimal
latency.  Each connected HTTP client is woken by an asyncio.Event when a
new JPEG is ready.

    GET /stream  →  multipart MJPEG
    GET /         →  200 OK (health check)

Requires ``opencv-python-headless`` (optional ``[camera]`` extra).
"""

from __future__ import annotations

import asyncio
import logging
import threading

import cv2

log = logging.getLogger(__name__)

_BOUNDARY = b"frame"


class MJPEGServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8766,
        device: int | str = 0,
        fps: int = 30,
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
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    # ── lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> bool:
        """Open the camera and start serving.  Returns False if no camera."""
        loop = asyncio.get_running_loop()
        cap = await loop.run_in_executor(None, cv2.VideoCapture, self.device)
        if not cap.isOpened():
            log.warning("camera device %s not available — skipping", self.device)
            cap.release()
            return False

        # Minimise the internal buffer so .read() returns the latest frame.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._cap = cap
        self._loop = loop
        self._running = True

        # Dedicated thread grabs frames as fast as the camera delivers them.
        self._thread = threading.Thread(target=self._capture_thread, daemon=True)
        self._thread.start()

        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port,
        )
        log.info("mjpeg server on http://%s:%d/stream", self.host, self.port)
        return True

    async def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._cap:
            self._cap.release()

    def stream_url(self) -> str:
        return f"http://{self.host}:{self.port}/stream"

    # ── capture thread (single producer) ──────────────────────────────

    def _capture_thread(self) -> None:
        """Runs in a dedicated thread.  Grabs frames at camera rate, encodes
        JPEG, and signals the asyncio event so HTTP clients wake immediately."""
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.quality]
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                continue
            _, buf = cv2.imencode(".jpg", frame, encode_params)
            self._latest_frame = buf.tobytes()
            self._loop.call_soon_threadsafe(self._frame_event.set)

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

        min_period = 1.0 / self.fps
        try:
            while self._running:
                # Wait for the capture thread to signal a new frame.
                self._frame_event.clear()
                await self._frame_event.wait()
                frame = self._latest_frame
                if frame:
                    writer.write(
                        b"--" + _BOUNDARY + b"\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame + b"\r\n"
                    )
                    await writer.drain()
                # Cap the send rate so we don't flood slow clients.
                await asyncio.sleep(min_period)
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()
