"""HostSerialDriver — JointDriver that pushes 18 servo pulses to a Servo2040
over USB serial.

The driver does NOT depend on pyserial at import time. It accepts any object
that implements a tiny ``_SerialPort`` protocol (write/read/in_waiting/close),
which lets tests inject a fake. When constructed via ``device=``, pyserial is
imported lazily and a real ``serial.Serial`` is opened.

If the underlying serial port goes into a persistent error state (USB device
unplugged, MCU crashed, kernel returning EIO on every call), the driver:

  * stops trying to talk to the dead port immediately,
  * suppresses repeated log spam (one warning per failure burst),
  * if it knows the device path, periodically tries to reopen it.

This way the robot loop keeps stepping cleanly while the hardware is missing,
and reconnects automatically when it comes back.

Note: this module is named ``serial`` but uses absolute imports, so
``import serial`` inside the lazy block resolves to top-level pyserial, not
to this file.
"""

import logging
import time
from typing import Protocol

from ..api.dto import JointAngles
from ..core.enums import Segment, Side
from .base import LegKey
from .servo.mapping import NUM_CHANNELS, ServoMap
from .servo.protocol import (
    FB_FRAME_LEN,
    FB_START,
    decode_feedback,
    encode_command,
)

_log = logging.getLogger(__name__)

# How often to attempt reopening a dead port (seconds).
_RECONNECT_INTERVAL_S = 2.0

_NAME_BY_KEY: dict[LegKey, str] = {
    (Segment.FRONT, Side.LEFT):  "front_left",
    (Segment.FRONT, Side.RIGHT): "front_right",
    (Segment.MID,   Side.LEFT):  "mid_left",
    (Segment.MID,   Side.RIGHT): "mid_right",
    (Segment.REAR,  Side.LEFT):  "rear_left",
    (Segment.REAR,  Side.RIGHT): "rear_right",
}


class _SerialPort(Protocol):
    """Subset of pyserial.Serial that we use. Lets tests inject a fake.

    Parameter names match pyserial so a real `serial.Serial` satisfies the
    protocol.
    """

    def write(self, b: bytes, /) -> int | None: ...
    def read(self, size: int = 1, /) -> bytes: ...
    @property
    def in_waiting(self) -> int: ...
    def close(self) -> None: ...


def _open_serial(device: str, baudrate: int) -> _SerialPort:
    import serial  # lazy: pyserial is an optional extra

    return serial.Serial(
        device,
        baudrate=baudrate,
        timeout=0,
        write_timeout=0,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )


class HostSerialDriver:
    """JointDriver pushing servo pulses over USB serial to a Servo2040."""

    def __init__(
        self,
        servo_map: ServoMap,
        port: _SerialPort | None = None,
        *,
        device: str | None = None,
        baudrate: int = 115200,
    ) -> None:
        if port is None and device is None:
            raise ValueError(
                "HostSerialDriver: pass either `port` or `device`"
            )
        if port is None:
            assert device is not None  # for the type-checker
            port = _open_serial(device, baudrate)
        self._port: _SerialPort | None = port
        self._device = device
        self._baudrate = baudrate
        self._map = servo_map
        self._rx_buf = bytearray()
        self._latest_contacts: dict[LegKey, bool] | None = None

        # Reconnect/health bookkeeping.
        self._dead = False
        self._next_reconnect_at = 0.0

    # ── failure / reconnect helpers ───────────────────────────────────────

    def _mark_dead(self, why: str) -> None:
        if not self._dead:
            _log.warning(
                "HostSerialDriver: serial port lost (%s) — will retry every %.0fs",
                why, _RECONNECT_INTERVAL_S,
            )
        self._dead = True
        self._rx_buf.clear()
        if self._port is not None:
            try:
                self._port.close()
            except OSError:
                pass
        self._port = None
        self._next_reconnect_at = time.monotonic() + _RECONNECT_INTERVAL_S

    def _try_reconnect(self) -> bool:
        """If the port is dead and the cooldown has elapsed, attempt to
        reopen the device. Returns True iff the port is alive after this
        call."""
        if not self._dead:
            return self._port is not None
        if self._device is None:
            return False  # nothing to reconnect to (test harness fake)
        now = time.monotonic()
        if now < self._next_reconnect_at:
            return False
        try:
            self._port = _open_serial(self._device, self._baudrate)
        except OSError as e:
            self._next_reconnect_at = now + _RECONNECT_INTERVAL_S
            _log.debug("HostSerialDriver: reconnect attempt failed: %s", e)
            return False
        _log.warning("HostSerialDriver: reconnected to %s", self._device)
        self._dead = False
        return True

    # ── JointDriver protocol ──────────────────────────────────────────────

    def write(self, commands: dict[LegKey, JointAngles]) -> None:
        if not self._try_reconnect():
            return
        assert self._port is not None

        pulses = [0] * NUM_CHANNELS
        for key, angles in commands.items():
            leg_name = _NAME_BY_KEY[key]
            for joint_name, value in (
                ("coxa", angles.coxa),
                ("femur", angles.femur),
                ("tibia", angles.tibia),
            ):
                js = self._map.get(leg_name, joint_name)
                pulses[js.channel] = js.angle_rad_to_pulse_us(value)
        try:
            self._port.write(encode_command(pulses))
        except OSError as e:
            self._mark_dead(f"write: {e}")

    def read(self) -> dict[LegKey, JointAngles] | None:
        # Open-loop: the Servo2040 has no joint encoders to report back.
        return None

    def read_contacts(self) -> dict[LegKey, bool] | None:
        if not self._try_reconnect():
            return self._latest_contacts
        assert self._port is not None

        try:
            n = self._port.in_waiting
            if n:
                self._rx_buf.extend(self._port.read(n))
        except OSError as e:
            self._mark_dead(f"read: {e}")
            return self._latest_contacts

        # Walk the buffer, looking for a valid feedback frame. On any framing
        # error we slide one byte and retry — that's the resync rule.
        while len(self._rx_buf) >= FB_FRAME_LEN:
            if self._rx_buf[0] != FB_START:
                del self._rx_buf[0]
                continue
            frame = bytes(self._rx_buf[:FB_FRAME_LEN])
            try:
                contacts = decode_feedback(frame)
            except ValueError:
                del self._rx_buf[0]
                continue
            self._latest_contacts = contacts
            del self._rx_buf[:FB_FRAME_LEN]

        return self._latest_contacts

    def close(self) -> None:
        if self._port is not None:
            try:
                self._port.close()
            except OSError:
                pass
            self._port = None
