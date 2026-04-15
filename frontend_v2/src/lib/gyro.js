/**
 * Phone orientation → roll/pitch. Calibrates to whatever pose the phone is
 * held at when gyro is first enabled, so "natural holding" maps to zero tilt.
 */
import { send } from "./ws.js";

const MAX_TILT = Math.PI / 12;

let active = false;
let basePitch = 0;

export async function startGyro() {
  if (
    typeof DeviceOrientationEvent !== "undefined" &&
    typeof DeviceOrientationEvent.requestPermission === "function"
  ) {
    try {
      const r = await DeviceOrientationEvent.requestPermission();
      if (r !== "granted") return false;
    } catch {
      return false;
    }
  }
  // One-shot calibration: first event captures baseline.
  basePitch = null;
  window.addEventListener("deviceorientation", onOrientation);
  active = true;
  return true;
}

export function stopGyro() {
  active = false;
  window.removeEventListener("deviceorientation", onOrientation);
  send({ type: "set_orientation", roll: 0, pitch: 0 });
}

function clamp(v) {
  return Math.max(-MAX_TILT, Math.min(MAX_TILT, v));
}

function onOrientation(e) {
  if (!active) return;
  if (basePitch === null) basePitch = e.beta;
  const pitch = clamp(((e.beta - basePitch) * Math.PI) / 180 * 0.5);
  const roll = clamp((-e.gamma * Math.PI) / 180 * 0.5);
  send({ type: "set_orientation", roll, pitch });
}
