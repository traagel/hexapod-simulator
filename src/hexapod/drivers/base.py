"""JointDriver protocol — the seam between simulation and real hardware."""

from typing import Protocol

from ..api.dto import JointAngles
from ..core.enums import Segment, Side

LegKey = tuple[Segment, Side]


class JointDriver(Protocol):
    """Receives joint commands and applies them.

    Implementations:
      - SimDriver writes into the in-memory Hexapod model.
      - ServoDriver maps angles to PWM and writes over I2C/UART.
      - MockDriver records calls for tests.
    """

    def write(self, commands: dict[LegKey, JointAngles]) -> None: ...

    def read(self) -> dict[LegKey, JointAngles] | None:
        """Optional joint feedback. Return None if the driver is open-loop."""
        ...

    def read_contacts(self) -> dict[LegKey, bool] | None:
        """Optional ground-contact feedback per leg. None if no sensors."""
        ...

    def close(self) -> None: ...
