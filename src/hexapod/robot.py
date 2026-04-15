"""Robot facade — the single public API surface.

External controllers, transports, and visualizers all talk to a Robot.
They never reach into core/, gait/, or kinematics/ directly.

The Robot owns a four-state machine:
    ZERO_STANCE   — holding every foot at its all-zero-joint FK position
    TRANSITION    — animated two-phase tap-dance between zero and neutral
    STANDING      — feet world-locked at neutral; phase frozen
    WALKING       — gait phase advancing; feet cycling swing/stance

Mode transitions:
    ZERO_STANCE ─set_zero_stance(False)─► TRANSITION(→STANDING)
    STANDING    ─set_zero_stance(True)──► TRANSITION(→ZERO_STANCE)
    STANDING    ─set_twist(nonzero)─────► WALKING
    WALKING     ─gait settles + no twist► STANDING
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from .api.dto import JointAngles, LegState, PoseDTO, RobotState, TwistDTO
from .core.enums import Segment, Side
from .core.gait.base import Gait
from .core.hexapod import Hexapod
from .core.kinematics import fk, ik
from .drivers.base import JointDriver, LegKey

StateCallback = Callable[[RobotState], None]
Unsubscribe = Callable[[], None]

_KEY_NAMES: dict[LegKey, str] = {
    (Segment.FRONT, Side.LEFT): "front_left",
    (Segment.FRONT, Side.RIGHT): "front_right",
    (Segment.MID, Side.LEFT): "mid_left",
    (Segment.MID, Side.RIGHT): "mid_right",
    (Segment.REAR, Side.LEFT): "rear_left",
    (Segment.REAR, Side.RIGHT): "rear_right",
}


class RobotMode(Enum):
    ZERO_STANCE = "zero_stance"
    TRANSITION = "transition"
    STANDING = "standing"
    WALKING = "walking"


@dataclass
class TransitionState:
    """Two-phase tap-dance animation from `start` to `end` per leg, landing
    in `to_mode` when complete. Group i (i∈{0,1}) moves during the i-th half
    of the window, so one tripod re-plants before the other lifts.
    """

    to_mode: RobotMode
    duration: float
    lift: float
    start: dict[LegKey, tuple[float, float, float]]
    end: dict[LegKey, tuple[float, float, float]]
    elapsed: float = 0.0


class Robot:
    """Owns the core domain + a driver. Drives one tick at a time via step()."""

    def __init__(
        self,
        hexapod: Hexapod,
        gait: Gait,
        driver: JointDriver,
        cycle_seconds: float = 2.0,
    ) -> None:
        self.hexapod = hexapod
        self.gait = gait
        self.driver = driver
        self.cycle_seconds = cycle_seconds

        # Start at rest; Robot owns the live twist, not the gait's constructor default.
        self.gait.linear_velocity = (0.0, 0.0)
        self.gait.angular_velocity = 0.0

        self._t = 0.0
        self.max_step_length: float | None = None
        self._commanded_twist = TwistDTO()
        self._subscribers: list[StateCallback] = []

        # Pending command buffer (applied at the start of next step()).
        self._pending_twist: TwistDTO | None = None
        self._pending_foot_targets: dict[LegKey, tuple[float, float, float]] = {}
        self._pending_pose: PoseDTO | None = None

        self._servos_enabled = False
        self._low_power = False
        self._low_battery_cutoff_mv = 6400
        self._low_battery_triggered = False

        # FK positions at all-zero joint angles — the "zero stance" rest pose.
        self._zero_foot_targets: dict[LegKey, tuple[float, float, float]] = {}
        for leg in self.hexapod.legs:
            saved = (leg.coxa.angle.rad, leg.femur.angle.rad, leg.tibia.angle.rad)
            leg.coxa.angle.rad = 0.0
            leg.femur.angle.rad = 0.0
            leg.tibia.angle.rad = 0.0
            self._zero_foot_targets[(leg.segment, leg.side)] = fk.solve(leg)
            leg.coxa.angle.rad, leg.femur.angle.rad, leg.tibia.angle.rad = saved

        # Mode starts at ZERO_STANCE; external caller drives the transition out.
        self.mode: RobotMode = RobotMode.ZERO_STANCE
        self.transition: TransitionState | None = None

    # ── command surface ────────────────────────────────────────────────────

    def set_twist(self, vx: float, vy: float, omega: float) -> None:
        """Body-frame velocity command (units/sec, rad/sec)."""
        self._pending_twist = TwistDTO(vx=vx, vy=vy, omega=omega)

    def stop(self) -> None:
        """Command zero twist. Gait settles over the next ~1 cycle and the
        robot auto-transitions WALKING → STANDING when every leg is planted.
        """
        self._pending_twist = TwistDTO(0.0, 0.0, 0.0)

    def set_foot_target(self, leg: LegKey, xyz: tuple[float, float, float]) -> None:
        """Override a single foot target for the next tick (body frame)."""
        self._pending_foot_targets[leg] = xyz

    def set_body_pose(self, x: float, y: float, yaw: float) -> None:
        """Teleport the body pose. Applied at the start of next step()."""
        self._pending_pose = PoseDTO(x=x, y=y, z=self.hexapod.height, yaw=yaw)

    def set_body_height(self, height: float) -> None:
        """Body z above the ground. Re-anchors any planted feet at the new
        height so they don't appear to shift."""
        self.hexapod.height = float(height)
        self.gait.relock_stance_from_fk()

    def set_body_orientation(self, roll: float, pitch: float) -> None:
        """Tilt the body. Feet stay world-planted via the stance re-projection."""
        self.hexapod.pose.roll = float(roll)
        self.hexapod.pose.pitch = float(pitch)

    def set_step_length(self, length: float) -> None:
        """Soft cap on the gait's per-cycle body translation."""
        self.max_step_length = max(0.0, float(length))
        self._apply_twist(self._commanded_twist)

    def set_stance_radius(self, radius: float) -> None:
        """How far feet sit from the coxa mounts in the rest pose."""
        self.gait.neutral_radius = max(0.0, float(radius))

    def set_lift_height(self, height: float) -> None:
        """How high feet lift during swing."""
        self.gait.lift_height = max(0.0, float(height))

    def set_cycle_time(self, seconds: float) -> None:
        """Duration of one full gait cycle."""
        self.cycle_seconds = max(0.2, float(seconds))
        self._apply_twist(self._commanded_twist)

    def set_servos_enabled(self, enabled: bool) -> None:
        """Enable or disable servo output. Disabled by default."""
        self._servos_enabled = bool(enabled)
        if enabled:
            self._low_battery_triggered = False

    def set_low_power(self, enabled: bool) -> None:
        """Low power mode — limits concurrent servo movement."""
        self._low_power = bool(enabled)

    def set_low_battery_cutoff(self, mv: int) -> None:
        """Set battery voltage threshold (millivolts) for auto servo cutoff."""
        self._low_battery_cutoff_mv = max(0, int(mv))

    def set_zero_stance(self, enabled: bool) -> None:
        """Toggle zero-stance mode with a two-phase tap-dance transition."""
        if enabled and self.mode != RobotMode.ZERO_STANCE:
            self._enter_transition(RobotMode.ZERO_STANCE)
        elif not enabled and self.mode == RobotMode.ZERO_STANCE:
            self._enter_transition(RobotMode.STANDING)

    # ── mode transitions ───────────────────────────────────────────────────

    def _enter_walking(self) -> None:
        """STANDING → WALKING. Snapshots real FK positions so the first
        STANCE→SWING reads truth; no teleport on walk-start.
        """
        self.gait.begin_walk()
        self.mode = RobotMode.WALKING

    def _enter_standing(self) -> None:
        """any → STANDING. Re-plants every leg at its actual current FK."""
        self.gait.walking = False
        self.gait.plant_all_from_fk()
        self.mode = RobotMode.STANDING

    def _enter_zero_stance(self) -> None:
        """any → ZERO_STANCE. Plans become stale while held at zero; refreshed
        on the next transition out."""
        self.gait.walking = False
        self.mode = RobotMode.ZERO_STANCE

    def _enter_transition(self, to_mode: RobotMode) -> None:
        """Kick off a tap-dance animation from current FK to the target pose.
        Interrupts walking if in flight — the animation owns the feet."""
        start: dict[LegKey, tuple[float, float, float]] = {}
        end: dict[LegKey, tuple[float, float, float]] = {}
        for leg in self.hexapod.legs:
            key = (leg.segment, leg.side)
            start[key] = fk.solve(leg)
            if to_mode == RobotMode.ZERO_STANCE:
                end[key] = self._zero_foot_targets[key]
            else:  # STANDING
                end[key] = self.gait.neutral_position(leg)
        self.transition = TransitionState(
            to_mode=to_mode,
            duration=2.0,
            lift=self.gait.lift_height,
            start=start,
            end=end,
        )
        self.gait.walking = False
        self.mode = RobotMode.TRANSITION

    def _finish_transition(self) -> None:
        assert self.transition is not None
        to_mode = self.transition.to_mode
        self.transition = None
        if to_mode == RobotMode.STANDING:
            self._enter_standing()
        elif to_mode == RobotMode.ZERO_STANCE:
            self._enter_zero_stance()

    # ── tick the world ─────────────────────────────────────────────────────

    def step(self, dt: float) -> RobotState:
        """Advance the simulation by dt seconds and return the new state."""
        self._drain_pending_commands()

        targets = self._dispatch_mode(dt)

        for key, xyz in self._pending_foot_targets.items():
            targets[key] = xyz
        self._pending_foot_targets.clear()

        self._solve_and_write(targets)

        if self.mode == RobotMode.WALKING:
            self._integrate_pose(dt)

        self._t += dt

        state = self.state()
        for cb in self._subscribers:
            cb(state)
        return state

    def _drain_pending_commands(self) -> None:
        if self._pending_pose is not None:
            self.hexapod.pose.x = self._pending_pose.x
            self.hexapod.pose.y = self._pending_pose.y
            self.hexapod.pose.yaw = self._pending_pose.yaw
            self._pending_pose = None
            # Feet stay visually planted after a body teleport.
            self.gait.relock_stance_from_fk()

        if self._pending_twist is not None:
            self._commanded_twist = self._pending_twist
            self._apply_twist(self._pending_twist)
            self._pending_twist = None
            # Nonzero twist while STANDING kicks off WALKING right now.
            if self._has_commanded_twist() and self.mode == RobotMode.STANDING:
                self._enter_walking()

    def _dispatch_mode(self, dt: float) -> dict[LegKey, tuple[float, float, float]]:
        if self.mode == RobotMode.ZERO_STANCE:
            return dict(self._zero_foot_targets)
        if self.mode == RobotMode.TRANSITION:
            return self._tick_transition(dt)
        if self.mode == RobotMode.STANDING:
            return self._tick_standing()
        # WALKING
        return self._tick_walking(dt)

    def _tick_transition(
        self, dt: float,
    ) -> dict[LegKey, tuple[float, float, float]]:
        trans = self.transition
        assert trans is not None
        trans.elapsed += dt
        targets = self._compute_transition_targets(trans)
        if trans.elapsed >= trans.duration:
            self._finish_transition()
        return targets

    def _compute_transition_targets(
        self, trans: TransitionState,
    ) -> dict[LegKey, tuple[float, float, float]]:
        t = min(trans.elapsed / trans.duration, 1.0)
        result: dict[LegKey, tuple[float, float, float]] = {}
        for i, group in enumerate(self.gait.GROUPS):
            window_start = i * 0.5
            local = max(0.0, min(1.0, (t - window_start) / 0.5))
            for key in group:
                s = trans.start[key]
                e = trans.end[key]
                if local <= 0.0:
                    result[key] = s
                elif local >= 1.0:
                    result[key] = e
                else:
                    x = s[0] + (e[0] - s[0]) * local
                    y = s[1] + (e[1] - s[1]) * local
                    z_base = s[2] + (e[2] - s[2]) * local
                    lift = trans.lift * math.sin(math.pi * local)
                    result[key] = (x, y, z_base + lift)
        return result

    def _tick_standing(self) -> dict[LegKey, tuple[float, float, float]]:
        return {
            (leg.segment, leg.side): self.gait.sample(leg)
            for leg in self.hexapod.legs
        }

    def _tick_walking(
        self, dt: float,
    ) -> dict[LegKey, tuple[float, float, float]]:
        contacts = self.driver.read_contacts()
        self.gait.tick(dt / self.cycle_seconds, contacts=contacts)
        targets = {
            (leg.segment, leg.side): self.gait.sample(leg)
            for leg in self.hexapod.legs
        }
        # If the operator has released all controls and every leg has planted
        # with zero committed delta, we're settled — drop back to STANDING.
        if not self._has_commanded_twist() and self.gait.is_settled:
            self._enter_standing()
        return targets

    def _solve_and_write(
        self, targets: dict[LegKey, tuple[float, float, float]],
    ) -> None:
        commands: dict[LegKey, JointAngles] = {}
        for key, target in targets.items():
            leg = self.hexapod.legs.get(*key)
            try:
                c, f, ti = ik.solve(leg, target)
            except (ValueError, ZeroDivisionError):
                c = leg.coxa.angle.rad
                f = leg.femur.angle.rad
                ti = leg.tibia.angle.rad
            commands[key] = JointAngles(coxa=c, femur=f, tibia=ti)
            leg.coxa.angle.rad = c
            leg.femur.angle.rad = f
            leg.tibia.angle.rad = ti

        voltage = getattr(self.driver, "voltage_mv", 0)
        if (
            voltage > 0
            and self._low_battery_cutoff_mv > 0
            and voltage < self._low_battery_cutoff_mv
            and self._servos_enabled
        ):
            self._servos_enabled = False
            self._low_battery_triggered = True

        if self._servos_enabled:
            self.driver.write(commands)

    def _integrate_pose(self, dt: float) -> None:
        lin_per_s = (
            self.gait.linear_velocity[0] / self.cycle_seconds,
            self.gait.linear_velocity[1] / self.cycle_seconds,
        )
        ang_per_s = self.gait.angular_velocity / self.cycle_seconds
        self.hexapod.pose.integrate(lin_per_s, ang_per_s, dt)

    # ── helpers ────────────────────────────────────────────────────────────

    def _has_commanded_twist(self) -> bool:
        t = self._commanded_twist
        return t.vx != 0.0 or t.vy != 0.0 or t.omega != 0.0

    def _apply_twist(self, t: TwistDTO) -> None:
        """Convert a per-second twist to per-cycle gait velocity, with cap."""
        lin = (t.vx * self.cycle_seconds, t.vy * self.cycle_seconds)
        if self.max_step_length is not None:
            mag = math.hypot(*lin)
            if mag > self.max_step_length and mag > 0:
                scale = self.max_step_length / mag
                lin = (lin[0] * scale, lin[1] * scale)
        self.gait.linear_velocity = lin
        self.gait.angular_velocity = t.omega * self.cycle_seconds

    # ── state surface ──────────────────────────────────────────────────────

    def state(self) -> RobotState:
        contacts = self.driver.read_contacts() or {}
        legs: dict[str, LegState] = {}
        for leg in self.hexapod.legs:
            key = (leg.segment, leg.side)
            name = _KEY_NAMES[key]
            legs[name] = LegState(
                angles=JointAngles(
                    coxa=leg.coxa.angle.rad,
                    femur=leg.femur.angle.rad,
                    tibia=leg.tibia.angle.rad,
                ),
                coxa_start=leg.coxa.start,
                coxa_end=leg.coxa.end,
                femur_end=leg.femur.end,
                foot=leg.tibia.end,
                contact=contacts.get(key, False),
            )
        return RobotState(
            t=self._t,
            pose=PoseDTO(
                x=self.hexapod.pose.x,
                y=self.hexapod.pose.y,
                z=self.hexapod.height,
                yaw=self.hexapod.pose.yaw,
                roll=self.hexapod.pose.roll,
                pitch=self.hexapod.pose.pitch,
            ),
            twist=TwistDTO(
                vx=self.gait.linear_velocity[0] / self.cycle_seconds,
                vy=self.gait.linear_velocity[1] / self.cycle_seconds,
                omega=self.gait.angular_velocity / self.cycle_seconds,
            ),
            legs=legs,
            gait_phase=self.gait.phase,
            voltage_mv=getattr(self.driver, "voltage_mv", 0),
            low_battery=self._low_battery_triggered,
        )

    def subscribe(self, callback: StateCallback) -> Unsubscribe:
        self._subscribers.append(callback)

        def _unsub() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return _unsub
