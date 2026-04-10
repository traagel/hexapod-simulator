"""Wire-protocol round-trip and frame-format invariants."""

import pytest

from hexapod.drivers.servo.mapping import NUM_CHANNELS
from hexapod.drivers.servo.protocol import (
    CMD_FRAME_LEN,
    CMD_START,
    CONTACT_ORDER,
    FB_FRAME_LEN,
    FB_START,
    decode_feedback,
    encode_command,
    encode_feedback,
)


# ── command frame ─────────────────────────────────────────────────────────


def test_command_frame_length_and_start():
    frame = encode_command([1500] * NUM_CHANNELS)
    assert len(frame) == CMD_FRAME_LEN
    assert frame[0] == CMD_START


def test_command_payload_is_uint16_le():
    pulses = [1000 + i for i in range(NUM_CHANNELS)]
    frame = encode_command(pulses)
    for i, expected in enumerate(pulses):
        lo = frame[1 + i * 2]
        hi = frame[1 + i * 2 + 1]
        assert lo + (hi << 8) == expected


def test_command_xor_checksum():
    frame = encode_command(list(range(1000, 1000 + NUM_CHANNELS)))
    body = frame[:-1]
    xor = 0
    for b in body:
        xor ^= b
    assert frame[-1] == xor


def test_command_wrong_length_rejected():
    with pytest.raises(ValueError):
        encode_command([1500] * (NUM_CHANNELS - 1))


# ── feedback frame ────────────────────────────────────────────────────────


def test_feedback_round_trip_all_off():
    contacts = {k: False for k in CONTACT_ORDER}
    frame = encode_feedback(contacts)
    assert len(frame) == FB_FRAME_LEN
    assert frame[0] == FB_START
    fb = decode_feedback(frame)
    assert fb.contacts == contacts
    assert fb.voltage_mv == 0


def test_feedback_round_trip_alternating():
    contacts = {k: (i % 2 == 0) for i, k in enumerate(CONTACT_ORDER)}
    fb = decode_feedback(encode_feedback(contacts, voltage_mv=7600))
    assert fb.contacts == contacts
    assert fb.voltage_mv == 7600


def test_feedback_all_six_independent_bits():
    """Setting one leg's bit at a time should produce a one-hot bit pattern."""
    for i, key in enumerate(CONTACT_ORDER):
        contacts = {k: (k == key) for k in CONTACT_ORDER}
        frame = encode_feedback(contacts)
        assert frame[1] == (1 << i)


def test_feedback_bad_checksum_raises():
    frame = bytearray(encode_feedback({k: False for k in CONTACT_ORDER}))
    frame[-1] ^= 0xFF
    with pytest.raises(ValueError, match="checksum"):
        decode_feedback(bytes(frame))


def test_feedback_bad_start_raises():
    frame = bytearray(encode_feedback({k: False for k in CONTACT_ORDER}))
    frame[0] = 0x00
    with pytest.raises(ValueError, match="start"):
        decode_feedback(bytes(frame))


def test_feedback_wrong_length_rejected():
    with pytest.raises(ValueError):
        decode_feedback(b"\x5a\x00")
