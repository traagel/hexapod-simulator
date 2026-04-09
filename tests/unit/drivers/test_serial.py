"""HostSerialDriver against an in-memory fake serial port."""

from pathlib import Path

from hexapod.api.dto import JointAngles
from hexapod.core.enums import Segment, Side
from hexapod.drivers.serial import HostSerialDriver
from hexapod.drivers.servo.mapping import ServoMap
from hexapod.drivers.servo.protocol import (
    CMD_FRAME_LEN,
    CONTACT_ORDER,
    encode_feedback,
)

CONFIG = Path(__file__).resolve().parents[3] / "config" / "hexapod.yaml"


class FakePort:
    """Minimal serial-port stand-in: byte buffers + the four methods used."""

    def __init__(self) -> None:
        self.tx = bytearray()
        self.rx = bytearray()

    def write(self, b: bytes, /) -> int:
        self.tx.extend(b)
        return len(b)

    def read(self, size: int = 1, /) -> bytes:
        out = bytes(self.rx[:size])
        del self.rx[:size]
        return out

    @property
    def in_waiting(self) -> int:
        return len(self.rx)

    def close(self) -> None:
        pass


def _make() -> tuple[HostSerialDriver, FakePort, ServoMap]:
    sm = ServoMap.from_config(CONFIG)
    port = FakePort()
    return HostSerialDriver(sm, port=port), port, sm


def _all_zero_commands() -> dict[tuple[Segment, Side], JointAngles]:
    return {
        (seg, side): JointAngles(0.0, 0.0, 0.0)
        for seg in Segment
        for side in Side
    }


def test_constructor_requires_port_or_device():
    sm = ServoMap.from_config(CONFIG)
    try:
        HostSerialDriver(sm)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_write_emits_one_command_frame():
    drv, port, _ = _make()
    drv.write(_all_zero_commands())
    assert len(port.tx) == CMD_FRAME_LEN


def test_write_routes_angles_to_correct_channels():
    """Every channel's frame slot must hold whatever its own JointServo
    converts the commanded angle to — independent of profile vs calibration
    so this test stays correct as the conversion path evolves."""
    drv, port, sm = _make()
    drv.write(_all_zero_commands())
    frame = bytes(port.tx)
    for js in sm.joints.values():
        expected = js.angle_rad_to_pulse_us(0.0)
        ch = js.channel
        pulse = frame[1 + ch * 2] + (frame[1 + ch * 2 + 1] << 8)
        assert pulse == expected, f"channel {ch}: {pulse} != {expected}"


def test_read_contacts_parses_feedback_frame():
    drv, port, _ = _make()
    contacts = {k: (i < 3) for i, k in enumerate(CONTACT_ORDER)}
    port.rx.extend(encode_feedback(contacts))
    assert drv.read_contacts() == contacts


def test_read_contacts_resyncs_past_garbage():
    drv, port, _ = _make()
    contacts = {k: True for k in CONTACT_ORDER}
    port.rx.extend(b"\x00\xff\x12")  # garbage prefix
    port.rx.extend(encode_feedback(contacts))
    assert drv.read_contacts() == contacts


def test_read_contacts_returns_none_when_silent():
    drv, _, _ = _make()
    assert drv.read_contacts() is None


def test_read_contacts_returns_latest_after_multiple_frames():
    drv, port, _ = _make()
    older = {k: False for k in CONTACT_ORDER}
    newer = {k: True for k in CONTACT_ORDER}
    port.rx.extend(encode_feedback(older))
    port.rx.extend(encode_feedback(newer))
    assert drv.read_contacts() == newer
