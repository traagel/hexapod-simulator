"""Body pose in the world frame."""

import math


class Pose:
    """2D body pose: position (x, y) and yaw. z stays at the body height."""

    def __init__(self, x: float = 0.0, y: float = 0.0, yaw: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.yaw = yaw

    def integrate(
        self,
        linear_body: tuple[float, float],
        angular: float,
        dt: float,
    ) -> None:
        """Advance the pose by a body-frame twist over time `dt`.

        linear_body is in the body frame (vx forward, vy left); it gets rotated
        into the world by the current yaw before being applied.
        """
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        vx, vy = linear_body
        self.x += (c * vx - s * vy) * dt
        self.y += (s * vx + c * vy) * dt
        self.yaw += angular * dt

    def transform(
        self, point: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        """Map a body-frame point into the world frame."""
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        px, py, pz = point
        return (self.x + c * px - s * py, self.y + s * px + c * py, pz)

    def inverse_transform(
        self, point: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        """Map a world-frame point into the body frame."""
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        dx = point[0] - self.x
        dy = point[1] - self.y
        return (c * dx + s * dy, -s * dx + c * dy, point[2])
