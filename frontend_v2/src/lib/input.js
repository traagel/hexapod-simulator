/**
 * Keyboard / mouse input → WebSocket messages.
 *
 * Also exposes `sendTwist()` so gamepad and touch-joystick modules route
 * through the same dead-man gate. Dead-man requires holding Backquote (`)
 * while a control input is active; otherwise the robot is commanded to stop.
 */
import { writable, get } from "svelte/store";
import { send } from "./ws.js";
import { controls } from "./scene.js";

export const keys = {};
export const speed = writable(15);
export const fpvActive = writable(false);
export const fpvSens = writable({ yaw: 5, pitch: 4, roll: 6 });
export const deadMan = writable(false);

const MAX_TILT = Math.PI / 12;
const ROLL_DECAY = 0.92;
const ENGAGE_KEY = "`";

let fpvRoll = 0, fpvPitch = 0, fpvYaw = 0;
let shiftHeld = false;

export function sendTwist(vx, vy, omega) {
  if (get(deadMan) && !keys[ENGAGE_KEY]) {
    send({ type: "stop" });
    return;
  }
  send({ type: "twist", vx, vy, omega });
}

function pushTwist() {
  if (keys[" "]) {
    send({ type: "stop" });
    fpvYaw = 0;
    return;
  }
  const spd = get(speed);
  const vx = (keys["w"] ? spd : 0) - (keys["s"] ? spd : 0);
  const vy = (keys["a"] ? spd : 0) - (keys["d"] ? spd : 0);
  if (get(fpvActive)) {
    sendTwist(vx, vy, fpvYaw);
    fpvYaw = 0;
  } else {
    const turnRate = spd * 0.1;
    const omega = (keys["q"] ? turnRate : 0) - (keys["e"] ? turnRate : 0);
    sendTwist(vx, vy, omega);
  }
}

export function installInput() {
  window.addEventListener("keydown", (e) => {
    keys[e.key.toLowerCase()] = true;
    if (e.key === "Shift" && !shiftHeld) {
      shiftHeld = true;
      controls.enabled = false;
    }
    pushTwist();
  });
  window.addEventListener("keyup", (e) => {
    keys[e.key.toLowerCase()] = false;
    if (e.key === "Shift") {
      shiftHeld = false;
      controls.enabled = true;
      send({ type: "set_orientation", roll: 0, pitch: 0 });
    }
    pushTwist();
  });

  window.addEventListener("mousemove", (e) => {
    if (get(fpvActive)) {
      const s = get(fpvSens);
      const yawSens = s.yaw / 1000;
      const pitchSens = s.pitch / 2000;
      fpvYaw = -e.movementX * yawSens;
      fpvPitch = Math.max(-MAX_TILT, Math.min(MAX_TILT, fpvPitch + e.movementY * pitchSens));
      sendTwist(0, 0, fpvYaw);
      fpvYaw = 0;
      return;
    }
    if (!shiftHeld) return;
    const nx = (e.clientX / window.innerWidth - 0.5) * 2;
    const ny = (e.clientY / window.innerHeight - 0.5) * 2;
    send({ type: "set_orientation", roll: -nx * MAX_TILT, pitch: ny * MAX_TILT });
  });
}

export function enterFPV() {
  fpvActive.set(true);
  document.body.classList.add("fpv");
  controls.enabled = false;
  document.body.requestPointerLock();
}

export function exitFPV() {
  fpvActive.set(false);
  document.body.classList.remove("fpv");
  controls.enabled = true;
  fpvRoll = 0;
  fpvPitch = 0;
  send({ type: "set_orientation", roll: 0, pitch: 0 });
  if (document.pointerLockElement) document.exitPointerLock();
}

export function fpvOrientationTick() {
  if (!get(fpvActive)) return;
  const s = get(fpvSens);
  const rollDir = (keys["q"] ? 1 : 0) - (keys["e"] ? 1 : 0);
  const rollSpeed = s.roll / 10;
  if (rollDir !== 0) {
    fpvRoll += rollDir * rollSpeed * 0.02;
    fpvRoll = Math.max(-MAX_TILT, Math.min(MAX_TILT, fpvRoll));
  } else {
    fpvRoll *= ROLL_DECAY;
    if (Math.abs(fpvRoll) < 0.001) fpvRoll = 0;
  }
  send({ type: "set_orientation", roll: fpvRoll, pitch: fpvPitch });
}

document.addEventListener("pointerlockchange", () => {
  if (!document.pointerLockElement && get(fpvActive)) exitFPV();
});
