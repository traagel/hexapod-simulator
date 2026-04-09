"""Matplotlib visualization — a consumer of the Robot API.

This module reads from the Robot but does NOT advance simulation. The run loop
calls Robot.step(dt) and the controller; the viz only draws what it sees.
"""

import math

import matplotlib.animation as manimation
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from ..controllers.base import Controller
from ..core.gait.base import Gait
from ..robot import Robot


class MatplotlibViz:
    def __init__(self, robot: Robot) -> None:
        self.robot = robot
        self.trail: list[tuple[float, float]] = []
        self.fig = plt.figure(figsize=(9, 7))
        self.ax = self.fig.add_subplot(111, projection="3d")

    def draw(self, bounds_pts: list[tuple[float, float, float]]) -> None:
        ax = self.ax
        hexapod = self.robot.hexapod
        gait = self.robot.gait
        pose = hexapod.pose
        state = self.robot.state()

        self.trail.append((pose.x, pose.y))

        ax.cla()
        _set_equal_aspect(ax, bounds_pts)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        ax.set_title(
            f"t={state.t:5.2f}  pose=({pose.x:.1f}, {pose.y:.1f}, yaw={pose.yaw:.2f})"
        )

        T = pose.transform

        body = [T(leg.coxa.start) for leg in hexapod.legs]
        body.append(body[0])
        bx, by, bz = zip(*body, strict=True)
        ax.plot(bx, by, bz, color="black", linewidth=2)

        for leg in hexapod.legs:
            pts = [
                T(leg.coxa.start),
                T(leg.coxa.end),
                T(leg.femur.end),
                T(leg.tibia.end),
            ]
            xs, ys, zs = zip(*pts, strict=True)
            ax.plot(xs, ys, zs, color="red", marker="o", linewidth=2)
            fx, fy, fz = pts[-1]
            ax.plot(
                [fx, fx], [fy, fy], [fz, 0], color="gray", linestyle=":", linewidth=0.8
            )

        _draw_gait_polygons(ax, hexapod, gait, state.gait_phase)

        if len(self.trail) >= 2:
            tx, ty = zip(*self.trail, strict=True)
            ax.plot(
                tx, ty, [0] * len(self.trail), color="blue", linewidth=1.5, alpha=0.8
            )


def run(
    robot: Robot,
    controller: Controller | None = None,
    seconds: float = 8.0,
    fps: int = 30,
    block: bool = True,
) -> manimation.FuncAnimation:
    """Drive a Robot from a controller and render with matplotlib.

    The run loop is here, in the viz layer — exactly one place per consumer.
    A WebSocket transport would have its own loop instead.
    """
    viz = MatplotlibViz(robot)
    dt = 1.0 / fps
    frames = int(seconds * fps)
    bounds_pts = _estimate_bounds(robot, controller, seconds, dt)

    def update(frame: int):
        state = robot.state()
        if controller is not None:
            controller.update(robot, state, dt)
        robot.step(dt)
        viz.draw(bounds_pts)

    anim = manimation.FuncAnimation(
        viz.fig, update, frames=frames, interval=1000 / fps, blit=False, repeat=True
    )
    plt.tight_layout()
    plt.show(block=block)
    return anim


# ── helpers ──────────────────────────────────────────────────────────────


def _estimate_bounds(
    robot: Robot,
    controller: Controller | None,
    seconds: float,
    dt: float,
) -> list[tuple[float, float, float]]:
    """Pre-roll a virtual pose to find world bounds without mutating state."""
    from ..core.pose import Pose

    hexapod = robot.hexapod
    gait = robot.gait
    cycle_seconds = robot.cycle_seconds

    base: list[tuple[float, float, float]] = []
    for leg in hexapod.legs:
        nx, ny, nz = gait.neutral_position(leg)
        base.append((nx, ny, nz))
        base.append((nx, ny, nz + gait.lift_height))

    sim = Pose()
    saved_lin = gait.linear_velocity
    saved_ang = gait.angular_velocity
    poses: list[tuple[float, float]] = [(0.0, 0.0)]
    n = int(seconds / dt)
    for _ in range(n):
        # Simple linear extrapolation; controller-driven runs may exceed this.
        sim.integrate(
            (saved_lin[0] / cycle_seconds, saved_lin[1] / cycle_seconds),
            saved_ang / cycle_seconds,
            dt,
        )
        poses.append((sim.x, sim.y))

    pts: list[tuple[float, float, float]] = []
    for px, py in poses:
        for bx, by, bz in base:
            pts.append((px + bx, py + by, bz))
    return pts


def _draw_gait_polygons(ax, hexapod, gait: Gait, phase: float) -> None:
    colors = ["tab:blue", "tab:orange", "tab:purple", "tab:green"]
    for i, group in enumerate(gait.GROUPS):
        local = gait._local_phase(phase, i)
        in_stance = local >= 0.5
        feet = []
        for key in group:
            leg = hexapod.legs.get(*key)
            fx, fy, _ = hexapod.pose.transform(leg.tibia.end)
            feet.append((fx, fy, 0.0))
        if len(feet) < 3:
            continue
        cx = sum(p[0] for p in feet) / len(feet)
        cy = sum(p[1] for p in feet) / len(feet)
        feet.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        color = colors[i % len(colors)]
        poly = Poly3DCollection(
            [feet],
            facecolors=color,
            edgecolors=color,
            alpha=0.25 if in_stance else 0.0,
            linewidths=2,
            linestyles="solid" if in_stance else "dashed",
        )
        ax.add_collection3d(poly)


def _set_equal_aspect(ax, points: list[tuple[float, float, float]]) -> None:
    if not points:
        points = [(0.0, 0.0, 0.0)]
    xs, ys, zs = zip(*points, strict=True)
    cx, cy, cz = (
        (max(xs) + min(xs)) / 2,
        (max(ys) + min(ys)) / 2,
        (max(zs) + min(zs)) / 2,
    )
    r = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2 or 1.0
    ax.set_xlim(cx - r, cx + r)
    ax.set_ylim(cy - r, cy + r)
    ax.set_zlim(cz - r, cz + r)
    ax.set_box_aspect((1, 1, 1))
