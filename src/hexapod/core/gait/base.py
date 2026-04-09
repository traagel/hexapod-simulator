"""Base gait: maps a phase in [0, 1) to per-leg foot targets."""

import math

from ..enums import Segment, Side
from ..hexapod import Hexapod
from ..leg import Leg

LegKey = tuple[Segment, Side]
LegTargets = dict[LegKey, tuple[float, float, float]]


class Gait:
    """A gait splits legs into groups that swing in alternating phases.

    Each group is a set of leg keys; groups should partition all legs.
    Subclasses set `GROUPS` and (optionally) override `neutral_radius`.
    """

    GROUPS: list[set[LegKey]] = []

    def __init__(
        self,
        hexapod: Hexapod,
        step_length: float = 4.0,
        lift_height: float = 3.0,
        direction: tuple[float, float] = (1.0, 0.0),
        angular_velocity: float = 0.0,
        stance_z: float = 0.0,
        neutral_radius: float | None = None,
    ) -> None:
        self.hexapod = hexapod
        self.lift_height = lift_height
        self.stance_z = stance_z
        self.neutral_radius = neutral_radius

        # Per-cycle body twist in the body frame.
        # linear: how far the body translates per gait cycle.
        # angular: how much the body rotates (radians) per gait cycle.
        d = _normalize(direction)
        self.linear_velocity = (d[0] * step_length, d[1] * step_length)
        self.angular_velocity = angular_velocity

        # Per-leg latched state. The plan is committed at swing-start and
        # holds for the full step, so changing twist mid-cycle never causes
        # a teleport.
        #   _swing_start_body  : foot's body-frame pos when swing began
        #   _swing_target_body : foot's body-frame pos to land at (sampled at swing start)
        #   _stance_world      : foot's world-frame pos while planted (locked at swing-end)
        #   _prev_local        : last local phase per leg (for boundary detection)
        self._swing_start_body: dict[LegKey, tuple[float, float, float]] = {}
        self._swing_target_body: dict[LegKey, tuple[float, float, float]] = {}
        self._stance_world: dict[LegKey, tuple[float, float, float]] = {}
        self._latched_delta: dict[LegKey, tuple[float, float]] = {}
        self._prev_local: dict[LegKey, float] = {}
        # Legs whose stance has been "locked in" by an early-touchdown reflex.
        # Cleared only at the next real phase-driven swing-start.
        self._stance_override: set[LegKey] = set()

    @property
    def is_active(self) -> bool:
        """True if any leg has latched a non-zero step plan."""
        for dx, dy in self._latched_delta.values():
            if math.hypot(dx, dy) > 1e-6:
                return True
        return False

    # --- geometry -----------------------------------------------------------

    def neutral_position(self, leg: Leg) -> tuple[float, float, float]:
        """Foot rest position on the ground, outward from the coxa mount.

        When `neutral_radius` is unset, pick a radius that places the foot
        comfortably in the middle of the leg's reachable annulus given the
        body height. The IK workspace in the leg's vertical plane is
            d ∈ [|L1−L2|, L1+L2]
        so we aim for d_target = max(L1, L2) (the middle of that range when
        L1 ≠ L2) and back out the horizontal radius from the body height.
        This stays valid for both equal-length and asymmetric leg geometries.
        """
        radius = self.neutral_radius
        if radius is None:
            L1 = leg.femur.length
            L2 = leg.tibia.length
            drop = max(0.0, leg.height - self.stance_z)
            d_target = max(L1, L2)
            # Clamp into the reachable annulus with a small safety margin so
            # we stay off the IK clamp boundary.
            d_target = max(abs(L1 - L2) + 0.5, min(L1 + L2 - 0.5, d_target))
            horizontal = math.sqrt(max(0.0, d_target * d_target - drop * drop))
            radius = leg.coxa.length + horizontal
        out = leg.coxa.rest_angle
        mx, my = leg.coxa.mount
        return (mx + radius * math.cos(out), my + radius * math.sin(out), self.stance_z)

    # --- phase --------------------------------------------------------------

    def _group_index(self, key: LegKey) -> int:
        for i, group in enumerate(self.GROUPS):
            if key in group:
                return i
        raise KeyError(f"leg {key} not assigned to any gait group")

    def _local_phase(self, phase: float, group: int) -> float:
        n = len(self.GROUPS)
        return (phase + group / n) % 1.0

    # --- target generation --------------------------------------------------

    def targets(
        self,
        phase: float,
        contacts: dict[LegKey, bool] | None = None,
    ) -> LegTargets:
        """Return foot targets for every leg at the given gait phase.

        Two boundaries per leg per cycle drive the planning:
          - swing-start (local crosses 0): sample current twist, set swing
            target body-frame position. Foot lifts off, world position will
            drift as body moves but that's fine — the foot is in the air.
          - swing-end (local crosses 0.5 OR early ground contact): lock the
            foot's current world position. During stance the foot holds that
            world position regardless of how the body translates or rotates.

        If `contacts` is given, a leg in swing past `EARLY_TOUCHDOWN_MIN`
        progress that reports contact will end its swing immediately —
        terrain adaptation for bumping into an obstacle mid-step.
        """
        EARLY_TOUCHDOWN_MIN = 0.3  # ignore contact during the first 30% of swing
        pose = self.hexapod.pose
        result: LegTargets = {}

        for leg in self.hexapod.legs:
            key = (leg.segment, leg.side)
            group = self._group_index(key)
            # Natural (phase-driven) local; never overwritten so wrap detection
            # stays correct on the next frame.
            local_natural = self._local_phase(phase, group)
            prev_local = self._prev_local.get(key)

            crossed_swing_start = prev_local is None or (
                prev_local >= 0.5 and local_natural < 0.5
            )
            crossed_swing_end_natural = (
                prev_local is not None and prev_local < 0.5 <= local_natural
            )

            # A real phase-driven swing-start clears any reflex override.
            if crossed_swing_start:
                self._stance_override.discard(key)

            # Reflex: swing leg past the early-noise window AND in contact
            # → lock it into stance now.
            in_override = key in self._stance_override
            should_override = (
                contacts is not None
                and contacts.get(key, False)
                and local_natural < 0.5
                and (local_natural / 0.5) >= EARLY_TOUCHDOWN_MIN
                and not crossed_swing_start
            )
            crossed_swing_end_reflex = False
            if should_override and not in_override:
                self._stance_override.add(key)
                crossed_swing_end_reflex = True

            # Effective local: stance if override is active, else natural.
            local = 0.5 if key in self._stance_override else local_natural
            crossed_swing_end = crossed_swing_end_natural or crossed_swing_end_reflex

            neutral = self.neutral_position(leg)

            if crossed_swing_start:
                # Foot lifts off. Where it currently is becomes the swing start.
                # Plant target = neutral + delta/2 (so the upcoming stance
                # sweeps symmetrically from +delta/2 to -delta/2 in body frame
                # while the body translates by delta).
                start_body = self._stance_world.get(key)
                if start_body is None:
                    start_body = neutral
                else:
                    start_body = pose.inverse_transform(start_body)
                self._swing_start_body[key] = start_body

                dx, dy = self._foot_delta(neutral)
                self._latched_delta[key] = (dx, dy)
                self._swing_target_body[key] = (
                    neutral[0] + 0.5 * dx,
                    neutral[1] + 0.5 * dy,
                    neutral[2],
                )
                self._stance_world.pop(key, None)

            if crossed_swing_end:
                # Foot lands. Lock its current world position for the stance.
                target_body = self._swing_target_body.get(key, neutral)
                self._stance_world[key] = pose.transform(target_body)

            if local < 0.5:
                # swing — interpolate body-frame, add lift arc
                target = self._swing_at(leg, local, neutral)
            else:
                # stance — hold the locked world position (or just sit at
                # neutral if we don't have one yet, e.g. first frame)
                if key in self._stance_world:
                    target = pose.inverse_transform(self._stance_world[key])
                else:
                    target = neutral

            result[key] = target
            self._prev_local[key] = local_natural

        return result

    def _foot_delta(self, neutral: tuple[float, float, float]) -> tuple[float, float]:
        """Body-frame stance vector that keeps the foot world-stationary.

        During the half-cycle of stance, a foot must move in the body frame by
        -v_body_at_foot * (T_cycle / 2), so its world position stays put.
        Returned vector `d` is used as foot_offset = s * d with s sweeping
        +0.5 -> -0.5 during stance, so the actual change is -d, and
        d = 0.5 * (linear_velocity + omega x neutral).
        """
        nx, ny, _ = neutral
        vx, vy = self.linear_velocity
        w = self.angular_velocity
        return (0.5 * (vx - w * ny), 0.5 * (vy + w * nx))

    def _swing_at(
        self,
        leg: Leg,
        local: float,
        neutral: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        """Interpolate the foot through its swing arc in body frame."""
        key: LegKey = (leg.segment, leg.side)
        start = self._swing_start_body.get(key, neutral)
        target = self._swing_target_body.get(key, neutral)

        t = local / 0.5  # 0 -> 1 across the swing
        x = start[0] + (target[0] - start[0]) * t
        y = start[1] + (target[1] - start[1]) * t

        # No lift when start and target are the same point — the leg is idle.
        span = math.hypot(target[0] - start[0], target[1] - start[1])
        is_idle = span < 1e-6
        lift = 0.0 if is_idle else self.lift_height * math.sin(math.pi * t)

        return (x, y, neutral[2] + lift)


def _normalize(v: tuple[float, float]) -> tuple[float, float]:
    n = math.hypot(*v)
    if n == 0:
        return (1.0, 0.0)
    return (v[0] / n, v[1] / n)
