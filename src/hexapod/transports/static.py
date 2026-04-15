"""Threaded static-file HTTP server.

Runs alongside the WebSocket server so one process serves both the frontend
and the live state stream. No external deps — stdlib `http.server` in a
daemon thread. Silences the per-request access log.
"""

from __future__ import annotations

import http.server
import logging
import mimetypes
import socketserver
import threading
from pathlib import Path

log = logging.getLogger(__name__)

# `.webmanifest` is not in stdlib's default type map.
mimetypes.add_type("application/manifest+json", ".webmanifest")


class _ReuseTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class StaticServer:
    def __init__(
        self,
        directory: Path,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        self.directory = Path(directory)
        self.host = host
        self.port = port
        self._httpd: _ReuseTCPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        directory = str(self.directory)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)

            def log_message(self, *_args, **_kwargs) -> None:
                pass

        self._httpd = _ReuseTCPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True, name="static-http",
        )
        self._thread.start()
        log.info("static files on http://%s:%d/ from %s",
                 self.host, self.port, self.directory)

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
