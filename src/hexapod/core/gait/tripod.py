"""Tripod gait: two alternating triangles of three legs each."""

from ..enums import Segment, Side
from .base import Gait, LegKey


class TripodGait(Gait):
    """Classic tripod: {FR, ML, RR} and {FL, MR, RL} alternate."""

    GROUPS: list[set[LegKey]] = [
        {
            (Segment.FRONT, Side.RIGHT),
            (Segment.MID, Side.LEFT),
            (Segment.REAR, Side.RIGHT),
        },
        {
            (Segment.FRONT, Side.LEFT),
            (Segment.MID, Side.RIGHT),
            (Segment.REAR, Side.LEFT),
        },
    ]
