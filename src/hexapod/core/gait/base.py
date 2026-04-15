"""Gait engine: a two-level state machine.

Global (`Gait`):
    NOT-WALKING   — feet held via `plans[key].world_lock`, no phase advance
    WALKING       — phase advances each tick; per-leg transitions fire

Per-leg (`LegPlan.phase`):
    STANCE  — foot world-locked at `world_lock` (pose-projected each frame)
    SWING   — foot interpolates body-frame start → target with lift arc

Transitions fire inside `tick()`. `sample(leg)` is a pure read.
"""

import math
from dataclasses import dataclass
from enum import Enum

from ..enums import Segment, Side
from ..hexapod import Hexapod
from ..kinematics import fk
from ..leg import Leg

LegKey = tuple[Segment, Side]
LegTargets = dict[LegKey, tuple[float, float, float]]

# Fraction of the swing (0..1) below which contact reports are ignored as
# lift-off noise. A real obstacle reads True only after the foot has cleared
# this much of its arc.
EARLY_TOUCHDOWN_MIN = 0.3


class LegPhase(Enum):
    STANCE = "stance"
    SWING = "swing"


@dataclass
class LegPlan:
    """Per-leg state. Invariant: phase == STANCE ⇒ world_lock is not None."""

    phase: LegPhase
    world_lock: tuple[float, float, float] | None = None
    swing_start_body: tuple[float, float, float] | None = None
    swing_target_body: tuple[float, float, float] | None = None
    latched_delta: tuple[float, float] = (0.0, 0.0)
    prev_local: float = 0.0


class Gait:
    """Splits legs into groups that swing in alternating phases.

    Subclasses set `GROUPS` (a partition of every leg key); groups are offset
    by 1/N of a cycle each.
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
        d = _normalize(direction)
        self.linear_velocity: tuple[float, float] = (
            d[0] * step_length,
            d[1] * step_length,
        )
        self.angular_velocity: float = angular_velocity

        self.phase: float = 0.0
        self.walking: bool = False
        self.plans: dict[LegKey, LegPlan] = {}

    # ── lifecycle ──────────────────────────────────────────────────────────

    def plant_all_from_fk(self) -> None:
        """Snapshot every leg's current FK position as its world lock.

        Call this when entering any state in which feet should stay planted
        exactly where they visibly are (post-stand, after a body teleport,
        after a height change). Idempotent.
        """
        pose = self.hexapod.pose
        height = self.hexapod.height
        for leg in self.hexapod.legs:
            key = (leg.segment, leg.side)
            foot_body = fk.solve(leg)
            world = pose.transform(foot_body, pivot_z=height)
            self.plans[key] = LegPlan(
                phase=LegPhase.STANCE,
                world_lock=(world[0], world[1], self.stance_z),
            )

    def begin_walk(self) -> None:
        """Enter WALKING. Captures truth (actual FK positions) as world locks
        so the first STANCE→SWING transition reads where the foot really is,
        not a stale cache. This is the kick-teleport fix.

        Seeds every leg's ``prev_local`` to 1.0 so the next `tick()` sees a
        wrap-through-zero for group 0 and fires STANCE→SWING immediately —
        the robot starts stepping on frame 1 rather than stalling for a cycle.
        """
        self.plant_all_from_fk()
        self.phase = 0.0
        self.walking = True
        for plan in self.plans.values():
            plan.prev_local = 1.0

    def relock_stance_from_fk(self) -> None:
        """Re-snapshot world_lock for every STANCE leg at its current FK
        position. Use after the body teleports (pose or height changes) so
        planted feet stay visually anchored instead of snapping to wherever
        the stale lock re-projects to. SWING legs are untouched; their plan
        is in body frame and survives body teleports naturally.
        """
        pose = self.hexapod.pose
        height = self.hexapod.height
        for leg in self.hexapod.legs:
            key = (leg.segment, leg.side)
            plan = self.plans.get(key)
            if plan is None or plan.phase != LegPhase.STANCE:
                continue
            foot_body = fk.solve(leg)
            world = pose.transform(foot_body, pivot_z=height)
            plan.world_lock = (world[0], world[1], self.stance_z)

    def end_walk(self) -> None:
        """Leave WALKING. Caller should have verified `is_settled` first."""
        self.walking = False

    @property
    def is_settled(self) -> bool:
        """True when no leg has a committed step in flight. The robot flips
        from WALKING to STANDING when this becomes True and commanded twist
        is zero.
        """
        for plan in self.plans.values():
            if plan.phase != LegPhase.STANCE:
                return False
            if math.hypot(*plan.latched_delta) > 1e-9:
                return False
        return True

    # ── per-tick ───────────────────────────────────────────────────────────

    def tick(
        self,
        phase_advance: float,
        contacts: dict[LegKey, bool] | None = None,
    ) -> None:
        """Advance the gait phase by `phase_advance` cycles and fire every
        leg's state transitions. Read targets with `sample(leg)` afterwards.
        Does nothing if not walking.
        """
        if not self.walking:
            return
        self.phase = (self.phase + phase_advance) % 1.0
        for leg in self.hexapod.legs:
            self._step_leg(leg, contacts)

    def _step_leg(
        self, leg: Leg, contacts: dict[LegKey, bool] | None,
    ) -> None:
        key = (leg.segment, leg.side)
        plan = self.plans[key]
        group = self._group_index(key)
        local = self._local_phase(self.phase, group)
        prev = plan.prev_local

        crossed_swing_start = prev >= 0.5 and local < 0.5
        crossed_swing_end_natural = prev < 0.5 <= local

        reflex_touchdown = (
            plan.phase == LegPhase.SWING
            and contacts is not None
            and contacts.get(key, False)
            and local < 0.5
            and (local / 0.5) >= EARLY_TOUCHDOWN_MIN
            and not crossed_swing_start
        )

        if plan.phase == LegPhase.STANCE and crossed_swing_start:
            self._on_swing_start(leg, plan)
        elif plan.phase == LegPhase.SWING and crossed_swing_end_natural:
            self._on_swing_end_natural(plan)
        elif reflex_touchdown:
            self._on_swing_end_reflex(leg, plan, local)

        plan.prev_local = local

    # ── transition side effects ────────────────────────────────────────────

    def _on_swing_start(self, leg: Leg, plan: LegPlan) -> None:
        """STANCE → SWING. Foot lifts off; its landing target is latched now
        so mid-cycle twist changes don't teleport it."""
        assert plan.world_lock is not None
        pose = self.hexapod.pose
        height = self.hexapod.height
        neutral = self.neutral_position(leg)

        start_body = pose.inverse_transform(plan.world_lock, pivot_z=height)
        dx, dy = self._foot_delta(neutral)
        target_body = (neutral[0] + 0.5 * dx, neutral[1] + 0.5 * dy, neutral[2])

        plan.phase = LegPhase.SWING
        plan.swing_start_body = start_body
        plan.swing_target_body = target_body
        plan.latched_delta = (dx, dy)
        plan.world_lock = None

    def _on_swing_end_natural(self, plan: LegPlan) -> None:
        """SWING → STANCE at the planned landing target."""
        assert plan.swing_target_body is not None
        pose = self.hexapod.pose
        height = self.hexapod.height
        world = pose.transform(plan.swing_target_body, pivot_z=height)
        plan.phase = LegPhase.STANCE
        plan.world_lock = (world[0], world[1], self.stance_z)
        plan.swing_start_body = None
        plan.swing_target_body = None

    def _on_swing_end_reflex(
        self, leg: Leg, plan: LegPlan, local: float,
    ) -> None:
        """SWING → STANCE at the current arc position. Fires when a contact
        sensor reports touchdown mid-swing (obstacle). Locking at the planned
        end would drag the foot through the obstacle; locking here doesn't.
        """
        pose = self.hexapod.pose
        height = self.hexapod.height
        current_body = self._swing_interp(plan, local)
        world = pose.transform(current_body, pivot_z=height)
        plan.phase = LegPhase.STANCE
        plan.world_lock = (world[0], world[1], self.stance_z)
        plan.swing_start_body = None
        plan.swing_target_body = None

    # ── sampling ───────────────────────────────────────────────────────────

    def sample(self, leg: Leg) -> tuple[float, float, float]:
        """Pure read of the current body-frame foot target for `leg`."""
        key = (leg.segment, leg.side)
        plan = self.plans[key]
        if plan.phase == LegPhase.STANCE:
            assert plan.world_lock is not None
            pose = self.hexapod.pose
            height = self.hexapod.height
            return pose.inverse_transform(
                (plan.world_lock[0], plan.world_lock[1], self.stance_z),
                pivot_z=height,
            )
        group = self._group_index(key)
        local = self._local_phase(self.phase, group)
        return self._swing_interp(plan, local)

    # ── geometry helpers (pure math) ───────────────────────────────────────

    def neutral_position(self, leg: Leg) -> tuple[float, float, float]:
        """Foot rest position on the ground, outward from the coxa mount."""
        radius = self.neutral_radius
        if radius is None:
            L1 = leg.femur.length
            L2 = leg.tibia.length
            drop = max(0.0, leg.height - self.stance_z)
            d_target = max(L1, L2)
            d_target = max(abs(L1 - L2) + 0.5, min(L1 + L2 - 0.5, d_target))
            horizontal = math.sqrt(max(0.0, d_target * d_target - drop * drop))
            radius = leg.coxa.length + horizontal
        out = leg.coxa.rest_angle
        mx, my = leg.coxa.mount
        return (
            mx + radius * math.cos(out),
            my + radius * math.sin(out),
            self.stance_z,
        )

    def _group_index(self, key: LegKey) -> int:
        for i, group in enumerate(self.GROUPS):
            if key in group:
                return i
        raise KeyError(f"leg {key} not assigned to any gait group")

    def _local_phase(self, phase: float, group: int) -> float:
        n = len(self.GROUPS)
        return (phase + group / n) % 1.0

    def _foot_delta(
        self, neutral: tuple[float, float, float],
    ) -> tuple[float, float]:
        """Body-frame stance vector d such that, during stance, the foot
        sweeps +0.5d → -0.5d while the body translates by +d and the foot's
        world position stays put.
            d = 0.5 * (linear_velocity + omega × neutral_radius)
        """
        nx, ny, _ = neutral
        vx, vy = self.linear_velocity
        w = self.angular_velocity
        return (0.5 * (vx - w * ny), 0.5 * (vy + w * nx))

    def _ground_z_at(self, x: float, y: float) -> float:
        """Body-frame z corresponding to world z=0 at the given xy. When
        roll/pitch are zero this returns ``stance_z``.
        """
        pose = self.hexapod.pose
        height = self.hexapod.height
        world = pose.transform((x, y, self.stance_z), pivot_z=height)
        ground_world = (world[0], world[1], self.stance_z)
        return pose.inverse_transform(ground_world, pivot_z=height)[2]

    def _swing_interp(
        self, plan: LegPlan, local: float,
    ) -> tuple[float, float, float]:
        """Interpolate the foot through its swing arc in body frame."""
        assert plan.swing_start_body is not None
        assert plan.swing_target_body is not None
        start = plan.swing_start_body
        target = plan.swing_target_body
        t = max(0.0, min(1.0, local / 0.5))
        x = start[0] + (target[0] - start[0]) * t
        y = start[1] + (target[1] - start[1]) * t
        span = math.hypot(target[0] - start[0], target[1] - start[1])
        is_idle = span < 1e-6
        lift = 0.0 if is_idle else self.lift_height * math.sin(math.pi * t)
        ground_z = self._ground_z_at(x, y)
        return (x, y, ground_z + lift)


def _normalize(v: tuple[float, float]) -> tuple[float, float]:
    n = math.hypot(*v)
    if n == 0:
        return (1.0, 0.0)
    return (v[0] / n, v[1] / n)
