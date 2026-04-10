"""Body pose in the world frame — full 3D rotation (roll, pitch, yaw)."""

import math


class Pose:
    """3D body pose: position (x, y), orientation (roll, pitch, yaw).

    The rotation convention is intrinsic ZYX (extrinsic XYZ):
        R = Rz(yaw) @ Ry(pitch) @ Rx(roll)

    The FK/IK frame has z = body_height at the body plane and z = 0 at the
    ground.  The rotation is applied around the body centre (``pivot_z``,
    typically ``hexapod.height``).  Points at the pivot are unaffected by
    roll/pitch; points above or below pivot shift in world-space as expected.

    Roll and pitch are set directly (not integrated from velocity) because
    they come from user input or an IMU, not from the gait's twist.
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        yaw: float = 0.0,
        roll: float = 0.0,
        pitch: float = 0.0,
    ) -> None:
        self.x = x
        self.y = y
        self.yaw = yaw
        self.roll = roll
        self.pitch = pitch

    def _rotation(self) -> tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]:
        """Rotation matrix R = Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
        cx, sx = math.cos(self.roll), math.sin(self.roll)
        cy, sy = math.cos(self.pitch), math.sin(self.pitch)
        cz, sz = math.cos(self.yaw), math.sin(self.yaw)
        return (
            (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
            (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
            (-sy,     cy * sx,                cy * cx),
        )

    def integrate(
        self,
        linear_body: tuple[float, float],
        angular: float,
        dt: float,
    ) -> None:
        """Advance the pose by a body-frame twist over time ``dt``.

        linear_body is in the body frame (vx forward, vy left); it gets rotated
        into the world by the current yaw before being applied.

        Roll and pitch are not integrated — they are set directly via
        ``set_body_orientation``.
        """
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        vx, vy = linear_body
        self.x += (c * vx - s * vy) * dt
        self.y += (s * vx + c * vy) * dt
        self.yaw += angular * dt

    def transform(
        self, point: tuple[float, float, float], pivot_z: float = 0.0,
    ) -> tuple[float, float, float]:
        """Map a body-frame point into the world frame.

        ``pivot_z`` is the z-coordinate of the rotation centre (the body
        plane).  Points at ``pivot_z`` only move in xy (yaw); points above
        or below shift vertically when roll/pitch are nonzero.  When
        roll = pitch = 0, z passes through unchanged regardless of
        ``pivot_z`` (backward-compatible).
        """
        r = self._rotation()
        px, py = point[0], point[1]
        pz = point[2] - pivot_z  # shift so pivot is at z=0
        return (
            self.x + r[0][0] * px + r[0][1] * py + r[0][2] * pz,
            self.y + r[1][0] * px + r[1][1] * py + r[1][2] * pz,
            pivot_z + r[2][0] * px + r[2][1] * py + r[2][2] * pz,
        )

    def inverse_transform(
        self, point: tuple[float, float, float], pivot_z: float = 0.0,
    ) -> tuple[float, float, float]:
        """Map a world-frame point into the body frame.

        Uses R^T (transpose) since rotation matrices are orthogonal.
        """
        r = self._rotation()
        dx = point[0] - self.x
        dy = point[1] - self.y
        dz = point[2] - pivot_z
        return (
            r[0][0] * dx + r[1][0] * dy + r[2][0] * dz,
            r[0][1] * dx + r[1][1] * dy + r[2][1] * dz,
            pivot_z + r[0][2] * dx + r[1][2] * dy + r[2][2] * dz,
        )
