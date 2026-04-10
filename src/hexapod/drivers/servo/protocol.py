"""Binary frame format on the wire to the Servo2040.

This file is the canonical reference for the C++ firmware side: any change
here MUST be mirrored in the firmware parser.

Command frame  (host → MCU):
    byte  0      0xA5                       start sentinel
    bytes 1..36  18 × uint16 LE pulse_us    one per channel, in channel order
    byte  37     XOR checksum               over bytes 0..36
    total        38 bytes  (CMD_FRAME_LEN)

Feedback frame (MCU → host):
    byte 0       0x5A                       start sentinel
    byte 1       contact bits               LSB = front_left, then front_right,
                                             mid_left, mid_right, rear_left,
                                             rear_right
    bytes 2..3   uint16 LE voltage_mv       battery voltage in millivolts
    byte 4       XOR checksum               over bytes 0..3
    total        5 bytes   (FB_FRAME_LEN)

Both frames use simple sentinel + XOR rather than COBS so the firmware can
parse them with a tiny state machine.
"""

import struct

from ...core.enums import Segment, Side
from .mapping import LEG_NAMES, NUM_CHANNELS

LegKey = tuple[Segment, Side]

CMD_START = 0xA5
FB_START = 0x5A

CMD_FRAME_LEN = 1 + NUM_CHANNELS * 2 + 1   # 38
FB_FRAME_LEN = 1 + 1 + 2 + 1                # 5

_NAME_TO_KEY: dict[str, LegKey] = {
    "front_left":  (Segment.FRONT, Side.LEFT),
    "front_right": (Segment.FRONT, Side.RIGHT),
    "mid_left":    (Segment.MID,   Side.LEFT),
    "mid_right":   (Segment.MID,   Side.RIGHT),
    "rear_left":   (Segment.REAR,  Side.LEFT),
    "rear_right":  (Segment.REAR,  Side.RIGHT),
}

# Bit position in the contact byte → leg key. Bit 0 is LEG_NAMES[0], etc.
CONTACT_ORDER: tuple[LegKey, ...] = tuple(_NAME_TO_KEY[n] for n in LEG_NAMES)


def _xor(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
    return c & 0xFF


def encode_command(pulses_us: list[int]) -> bytes:
    """Pack 18 pulse widths into the on-wire command frame."""
    if len(pulses_us) != NUM_CHANNELS:
        raise ValueError(f"expected {NUM_CHANNELS} pulses, got {len(pulses_us)}")
    payload = struct.pack(
        f"<{NUM_CHANNELS}H", *(p & 0xFFFF for p in pulses_us)
    )
    body = bytes([CMD_START]) + payload
    return body + bytes([_xor(body)])


class Feedback:
    """Parsed feedback frame."""
    __slots__ = ("contacts", "voltage_mv")

    def __init__(
        self,
        contacts: dict[LegKey, bool],
        voltage_mv: int = 0,
    ) -> None:
        self.contacts = contacts
        self.voltage_mv = voltage_mv


def decode_feedback(frame: bytes) -> Feedback:
    """Parse a feedback frame into contacts + battery voltage."""
    if len(frame) != FB_FRAME_LEN:
        raise ValueError(f"feedback frame must be {FB_FRAME_LEN} bytes")
    if frame[0] != FB_START:
        raise ValueError(f"bad feedback start byte 0x{frame[0]:02x}")
    if _xor(frame[:-1]) != frame[-1]:
        raise ValueError("feedback checksum mismatch")
    bits = frame[1]
    contacts = {key: bool((bits >> i) & 1) for i, key in enumerate(CONTACT_ORDER)}
    voltage_mv = struct.unpack_from("<H", frame, 2)[0]
    return Feedback(contacts=contacts, voltage_mv=voltage_mv)


def encode_feedback(
    contacts: dict[LegKey, bool], voltage_mv: int = 0,
) -> bytes:
    """Inverse of decode_feedback. Used by tests and any mock-MCU loopback."""
    bits = 0
    for i, key in enumerate(CONTACT_ORDER):
        if contacts.get(key, False):
            bits |= 1 << i
    body = bytes([FB_START, bits]) + struct.pack("<H", voltage_mv & 0xFFFF)
    return body + bytes([_xor(body)])
