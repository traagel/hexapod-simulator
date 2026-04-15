"""mDNS / Zeroconf advertisement so the frontend is reachable as
`hexapod.local:<port>` without hunting for the Pi's LAN IP.

`zeroconf` is an optional dep (install with `uv sync --extra mdns`). If it
isn't installed or advertisement fails, `advertise()` returns a no-op
handle and logs a warning — the server keeps running either way.
"""

from __future__ import annotations

import logging
import socket

log = logging.getLogger(__name__)


def _local_ip() -> str:
    """Pick the outbound-interface IP. Doesn't actually send anything."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


class MDNSHandle:
    def __init__(self, zc=None, info=None) -> None:
        self._zc = zc
        self._info = info

    def close(self) -> None:
        if self._zc is not None:
            try:
                if self._info is not None:
                    self._zc.unregister_service(self._info)
                self._zc.close()
            except Exception:
                log.exception("mdns shutdown failed")


def advertise(name: str, port: int) -> MDNSHandle:
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except ImportError:
        log.info("zeroconf not installed; skipping mDNS (try `uv sync --extra mdns`)")
        return MDNSHandle()

    try:
        ip = _local_ip()
        info = ServiceInfo(
            "_http._tcp.local.",
            f"{name}._http._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=port,
            server=f"{name}.local.",
            properties={"path": "/"},
        )
        zc = Zeroconf()
        zc.register_service(info)
        log.info("mDNS: http://%s.local:%d/ -> %s", name, port, ip)
        return MDNSHandle(zc, info)
    except Exception:
        log.exception("mDNS advertisement failed")
        return MDNSHandle()
