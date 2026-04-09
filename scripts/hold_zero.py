"""Hold every joint at IK angle 0 indefinitely — for mounting servo horns.

With the calibration table loaded, IK angle 0 maps to each servo's own
mechanical centre (the 135° row of its calibration table, typically near
1500 µs but offset per-servo). Run this while you're physically attaching
the servo horns so each leg sits at its neutral pose at the servo centre:

  * coxa  → leg points outward along the body→mount direction
  * femur → femur is horizontal (parallel to the body plane)
  * tibia → tibia points at the femur direction MINUS the bend offset
            (currently 25°, baked into config/hexapod.yaml)

Usage:
    uv run python scripts/hold_zero.py --device /dev/ttyACM0

Press Ctrl-C to stop. The firmware watchdog will release the servos after
500 ms once the script exits.
"""

import argparse
import time

from hexapod.api.dto import JointAngles
from hexapod.core.enums import Segment, Side
from hexapod.drivers.serial import HostSerialDriver
from hexapod.drivers.servo import ServoMap

CONFIG = "config/hexapod.yaml"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", default="/dev/ttyACM0")
    p.add_argument("--baudrate", type=int, default=115200)
    p.add_argument("--hz", type=int, default=50,
                   help="frame rate; firmware watchdog wants <500 ms gaps")
    args = p.parse_args()

    sm = ServoMap.from_config(CONFIG)
    drv = HostSerialDriver(sm, device=args.device, baudrate=args.baudrate)
    zero = {(seg, side): JointAngles(0.0, 0.0, 0.0)
            for seg in Segment for side in Side}

    print(f"holding all 18 servos at IK angle 0 on {args.device}")
    print("each channel will receive its own calibrated centre pulse:")
    for (leg_name, joint_name), js in sorted(
        sm.joints.items(), key=lambda kv: kv[1].channel
    ):
        print(f"  ch{js.channel:2d}  {leg_name:12s} {joint_name:5s}  "
              f"{js.angle_rad_to_pulse_us(0.0)} us")
    print("press Ctrl-C to stop")

    period = 1.0 / args.hz
    try:
        while True:
            drv.write(zero)
            time.sleep(period)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        drv.close()


if __name__ == "__main__":
    main()
