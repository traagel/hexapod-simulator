"""DTO serialization round-trip — the wire format used by every transport."""

from hexapod.api.dto import (
    JointAngles,
    LegState,
    PoseDTO,
    RobotState,
    TwistDTO,
)


def _state() -> RobotState:
    return RobotState(
        t=1.25,
        pose=PoseDTO(x=1.0, y=2.0, z=3.0, yaw=0.4),
        twist=TwistDTO(vx=0.1, vy=-0.2, omega=0.3),
        legs={
            "front_left": LegState(
                angles=JointAngles(0.1, 0.2, 0.3),
                coxa_start=(0.0, 0.0, 0.0),
                coxa_end=(1.0, 0.0, 0.0),
                femur_end=(2.0, 0.0, 1.0),
                foot=(3.0, 0.0, 0.0),
                contact=True,
            ),
        },
        gait_phase=0.42,
    )


def test_round_trip():
    s = _state()
    again = RobotState.from_dict(s.to_dict())
    assert again == s


def test_to_dict_is_plain_data():
    d = _state().to_dict()
    assert isinstance(d, dict)
    assert d["legs"]["front_left"]["contact"] is True
    assert d["pose"]["x"] == 1.0
