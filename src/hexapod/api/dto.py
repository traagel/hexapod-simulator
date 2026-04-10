"""Transport-agnostic data types for the public Robot API.

These are frozen dataclasses with `to_dict` / `from_dict` so any transport
(WebSocket, REST, ZMQ, serial) can serialize them without depending on
matplotlib, asyncio, or any core internals.
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class JointAngles:
    coxa: float
    femur: float
    tibia: float


@dataclass(frozen=True)
class LegState:
    angles: JointAngles
    # All in body frame. Lets the frontend draw jointed legs without FK.
    coxa_start: tuple[float, float, float]
    coxa_end: tuple[float, float, float]
    femur_end: tuple[float, float, float]
    foot: tuple[float, float, float]
    # True iff the foot's ground contact sensor is asserted. From the driver.
    # SimDriver synthesizes it from foot z; HardwareSerialDriver will read
    # the bit returned by the MCU.
    contact: bool = False


@dataclass(frozen=True)
class PoseDTO:
    x: float
    y: float
    z: float
    yaw: float
    roll: float = 0.0
    pitch: float = 0.0


@dataclass(frozen=True)
class TwistDTO:
    vx: float = 0.0
    vy: float = 0.0
    omega: float = 0.0


@dataclass(frozen=True)
class RobotState:
    t: float
    pose: PoseDTO
    twist: TwistDTO
    legs: dict[str, LegState]
    gait_phase: float
    voltage_mv: int = 0
    low_battery: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RobotState":
        return cls(
            t=d["t"],
            pose=PoseDTO(**d["pose"]),
            twist=TwistDTO(**d["twist"]),
            legs={
                k: LegState(
                    angles=JointAngles(**v["angles"]),
                    coxa_start=tuple(v["coxa_start"]),
                    coxa_end=tuple(v["coxa_end"]),
                    femur_end=tuple(v["femur_end"]),
                    foot=tuple(v["foot"]),
                    contact=bool(v.get("contact", False)),
                )
                for k, v in d["legs"].items()
            },
            gait_phase=d["gait_phase"],
            voltage_mv=d.get("voltage_mv", 0),
            low_battery=d.get("low_battery", False),
        )
