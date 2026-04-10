"""Robot facade — the single public API surface.

External controllers, transports, and visualizers all talk to a Robot.
They never reach into core/, gait/, or kinematics/ directly.
"""

from collections.abc import Callable

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

        # Start at rest. step_length on the gait was just a default for
        # standalone use; the Robot owns the live twist.
        self.gait.linear_velocity = (0.0, 0.0)
        self.gait.angular_velocity = 0.0

        self._t = 0.0
        self._phase = 0.0
        self._kick_pending = False
        # Soft cap on per-cycle body translation. None = no cap.
        self.max_step_length: float | None = None
        # Last commanded twist (per second). Cached so adjustments to
        # max_step_length can re-derive gait.linear_velocity without waiting
        # for a fresh set_twist call.
        self._commanded_twist = TwistDTO()
        self._subscribers: list[StateCallback] = []
        # Pending command buffer (applied at the start of next step).
        self._pending_twist: TwistDTO | None = None
        self._pending_foot_targets: dict[LegKey, tuple[float, float, float]] = {}
        self._pending_pose: PoseDTO | None = None
        self._stopped = False
        self._servos_enabled = False
        self._zero_stance = True  # start in zero stance

        # Transition animation state.
        self._transitioning = False
        self._transition_elapsed = 0.0
        self._transition_duration = 2.0  # total seconds for both groups
        self._transition_start: dict[LegKey, tuple[float, float, float]] = {}
        self._transition_end: dict[LegKey, tuple[float, float, float]] = {}
        self._transition_lift = 3.0

        # Pre-compute the FK foot positions at all-zero joint angles.
        self._zero_foot_targets: dict[LegKey, tuple[float, float, float]] = {}
        for leg in self.hexapod.legs:
            saved = (leg.coxa.angle.rad, leg.femur.angle.rad, leg.tibia.angle.rad)
            leg.coxa.angle.rad = 0.0
            leg.femur.angle.rad = 0.0
            leg.tibia.angle.rad = 0.0
            self._zero_foot_targets[(leg.segment, leg.side)] = fk.solve(leg)
            leg.coxa.angle.rad, leg.femur.angle.rad, leg.tibia.angle.rad = saved

    # ── command surface ────────────────────────────────────────────────

    def set_twist(self, vx: float, vy: float, omega: float) -> None:
        """Body-frame velocity command (units/sec, rad/sec)."""
        self._pending_twist = TwistDTO(vx=vx, vy=vy, omega=omega)
        self._stopped = False
        # If we're currently idle and the new command isn't zero, kick the
        # gait so it starts stepping NOW instead of waiting for the next
        # natural swing-start phase boundary.
        if (vx, vy, omega) != (0.0, 0.0, 0.0) and not self.gait.is_active:
            self._kick_pending = True

    def set_foot_target(self, leg: LegKey, xyz: tuple[float, float, float]) -> None:
        """Override a single foot target for the next tick (body frame)."""
        self._pending_foot_targets[leg] = xyz

    def set_body_pose(self, x: float, y: float, yaw: float) -> None:
        """Teleport the body pose. Use sparingly — bypasses dynamics."""
        self._pending_pose = PoseDTO(x=x, y=y, z=self.hexapod.height, yaw=yaw)

    def set_body_height(self, height: float) -> None:
        """Body z above the ground."""
        self.hexapod.height = float(height)
        self.gait._stance_world.clear()

    def set_body_orientation(self, roll: float, pitch: float) -> None:
        """Tilt the body. Angles in radians."""
        self.hexapod.pose.roll = float(roll)
        self.hexapod.pose.pitch = float(pitch)

    def set_step_length(self, length: float) -> None:
        """Soft cap on the gait's per-cycle body translation."""
        self.max_step_length = max(0.0, float(length))
        # Re-apply with the latest commanded twist so the slider takes effect
        # even if no new key has been pressed.
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

    def stop(self) -> None:
        self._pending_twist = TwistDTO(0.0, 0.0, 0.0)
        self._stopped = True

    def set_servos_enabled(self, enabled: bool) -> None:
        """Enable or disable servo output. Disabled by default."""
        self._servos_enabled = bool(enabled)

    def set_zero_stance(self, enabled: bool) -> None:
        """Toggle zero stance with a two-phase tap-dance transition.

        Each tripod group lifts, moves to target, and sets down in turn.
        """
        self._zero_stance = bool(enabled)
        self._transitioning = True
        self._transition_elapsed = 0.0
        self._transition_lift = self.gait.lift_height

        # Snapshot current foot positions as start, compute end targets.
        for leg in self.hexapod.legs:
            key = (leg.segment, leg.side)
            self._transition_start[key] = fk.solve(leg)
            if enabled:
                self._transition_end[key] = self._zero_foot_targets[key]
            else:
                self._transition_end[key] = self.gait.neutral_position(leg)

    def _has_twist(self) -> bool:
        t = self._commanded_twist
        return t.vx != 0.0 or t.vy != 0.0 or t.omega != 0.0

    def _transition_targets(self, dt: float) -> dict[LegKey, tuple[float, float, float]]:
        """Two-phase tap-dance: group 0 moves in first half, group 1 in second."""
        import math

        t = min(self._transition_elapsed / self._transition_duration, 1.0)
        half = self._transition_duration / 2.0
        groups = self.gait.GROUPS
        result: dict[LegKey, tuple[float, float, float]] = {}

        for i, group in enumerate(groups):
            # Group 0 moves during t=0..0.5, group 1 during t=0.5..1.0
            phase_start = i * 0.5
            phase_end = phase_start + 0.5
            local = (t - phase_start) / 0.5  # 0..1 within this group's window
            local = max(0.0, min(1.0, local))

            for key in group:
                s = self._transition_start[key]
                e = self._transition_end[key]

                if local <= 0.0:
                    # Not started yet — hold at start.
                    result[key] = s
                elif local >= 1.0:
                    # Done — hold at end.
                    result[key] = e
                else:
                    # Interpolate XY, add lift arc on Z.
                    x = s[0] + (e[0] - s[0]) * local
                    y = s[1] + (e[1] - s[1]) * local
                    z_base = s[2] + (e[2] - s[2]) * local
                    lift = self._transition_lift * math.sin(math.pi * local)
                    result[key] = (x, y, z_base + lift)

        return result

    # ── tick the world ─────────────────────────────────────────────────

    def step(self, dt: float) -> RobotState:
        """Advance the simulation by dt seconds. Returns the new state."""
        # 1. Apply buffered commands.
        if self._pending_pose is not None:
            self.hexapod.pose.x = self._pending_pose.x
            self.hexapod.pose.y = self._pending_pose.y
            self.hexapod.pose.yaw = self._pending_pose.yaw
            self._pending_pose = None

        if self._pending_twist is not None:
            self._commanded_twist = self._pending_twist
            self._apply_twist(self._pending_twist)
            self._pending_twist = None

        # 2. Advance the gait phase by wall time.  Freeze when the gait
        #    has no active plan so legs don't keep cycling swing↔stance
        #    and re-locking at slightly different positions each time.
        if self._kick_pending:
            # Reset the gait so the very next targets() call sees a fresh
            # swing-start for group 0 and (after the swing-end check) the
            # other group's stance is locked at its current world position.
            self._phase = 0.0
            self.gait._prev_local.clear()
            self.gait._latched_delta.clear()
            self._kick_pending = False
        elif self.gait.is_active or self._has_twist():
            self._phase = (self._phase + dt / self.cycle_seconds) % 1.0
        else:
            # No twist — make sure every leg is in stance so tilting
            # while stationary doesn't leave swing legs dangling.
            self.gait.land_all()

        # ── Transition animation ──────────────────────────────────────
        if self._transitioning:
            self._transition_elapsed += dt
            if self._transition_elapsed >= self._transition_duration:
                self._transitioning = False
                if not self._zero_stance:
                    # Stood up — clear gait state so it picks up fresh.
                    self.gait._stance_world.clear()

            targets = self._transition_targets(dt)
        elif self._zero_stance:
            # Holding zero — keep all feet at zero FK positions.
            targets = dict(self._zero_foot_targets)
        else:
            # 3. Normal gait targets.
            contacts = self.driver.read_contacts()
            targets = self.gait.targets(self._phase, contacts=contacts)
            for key, xyz in self._pending_foot_targets.items():
                targets[key] = xyz
            self._pending_foot_targets.clear()

        # 4. IK -> joint commands -> driver.
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
        if self._servos_enabled:
            self.driver.write(commands)

        # 5. Integrate body pose ONLY when at least one leg is committed to a
        #    real step. Otherwise the body would slide ahead of feet that
        #    haven't lifted yet (and keep sliding after a stop command).
        if self.gait.is_active:
            lin_per_s = (
                self.gait.linear_velocity[0] / self.cycle_seconds,
                self.gait.linear_velocity[1] / self.cycle_seconds,
            )
            ang_per_s = self.gait.angular_velocity / self.cycle_seconds
            self.hexapod.pose.integrate(lin_per_s, ang_per_s, dt)

        self._t += dt

        # 6. Build state, fan out to subscribers.
        state = self.state()
        for cb in self._subscribers:
            cb(state)
        return state

    # ── state surface ──────────────────────────────────────────────────

    def _apply_twist(self, t: TwistDTO) -> None:
        """Convert a per-second twist to per-cycle gait velocity, with cap."""
        import math as _m

        lin = (t.vx * self.cycle_seconds, t.vy * self.cycle_seconds)
        if self.max_step_length is not None:
            mag = _m.hypot(*lin)
            if mag > self.max_step_length and mag > 0:
                scale = self.max_step_length / mag
                lin = (lin[0] * scale, lin[1] * scale)
        self.gait.linear_velocity = lin
        self.gait.angular_velocity = t.omega * self.cycle_seconds

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
            gait_phase=self._phase,
            voltage_mv=getattr(self.driver, "voltage_mv", 0),
        )

    def subscribe(self, callback: StateCallback) -> Unsubscribe:
        self._subscribers.append(callback)

        def _unsub() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return _unsub
