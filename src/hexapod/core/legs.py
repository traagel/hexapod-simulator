from typing import Iterator

from .enums import Segment, Side
from .leg import Leg


class Legs:
    def __init__(self) -> None:
        self._map: dict[tuple[Segment, Side], Leg] = {}

    def add(self, leg: Leg) -> None:
        self._map[(leg.segment, leg.side)] = leg

    def get(self, segment: Segment, side: Side) -> Leg:
        return self._map[(segment, side)]

    def by_side(self, side: Side) -> list[Leg]:
        return [leg for (_, s), leg in self._map.items() if s == side]

    def by_segment(self, segment: Segment) -> list[Leg]:
        return [leg for (seg, _), leg in self._map.items() if seg == segment]

    def __iter__(self) -> Iterator[Leg]:
        return iter(self._map.values())

    def __len__(self) -> int:
        return len(self._map)
