/**
 * Web Gamepad API → twist. Standard mapping:
 *   LS y → vx (forward), LS x → vy (strafe), RS x → omega.
 * Polls at rAF, but throttles send to ~30 Hz and skips frames that are
 * entirely inside the deadzone (after the first zero is emitted).
 */
import { writable, get } from "svelte/store";
import { speed, sendTwist } from "./input.js";
import { send } from "./ws.js";

export const gamepadConnected = writable(false);

const DEADZONE = 0.15;
const SEND_INTERVAL_MS = 33;

let polling = false;
let wasActive = false;
let lastSend = 0;

function deadzone(v) {
  return Math.abs(v) < DEADZONE ? 0 : v;
}

function readPad(pad) {
  const lx = deadzone(pad.axes[0] ?? 0);
  const ly = deadzone(pad.axes[1] ?? 0);
  const rx = deadzone(pad.axes[2] ?? 0);
  const btnA = pad.buttons[0]?.pressed;
  const btnB = pad.buttons[1]?.pressed;
  if (btnA || btnB) {
    send({ type: "stop" });
    wasActive = false;
    return;
  }
  const active = !!(lx || ly || rx);
  if (!active && !wasActive) return;
  const now = performance.now();
  if (now - lastSend < SEND_INTERVAL_MS) return;
  lastSend = now;
  const spd = get(speed);
  sendTwist(-ly * spd, -lx * spd, -rx * spd * 0.1);
  wasActive = active;
}

function tick() {
  if (!polling) return;
  const pads = navigator.getGamepads?.() || [];
  const pad = Array.from(pads).find((p) => p && p.connected);
  if (pad) readPad(pad);
  requestAnimationFrame(tick);
}

export function startGamepadPolling() {
  if (polling) return;
  polling = true;
  requestAnimationFrame(tick);
}

export function stopGamepadPolling() {
  polling = false;
}

window.addEventListener("gamepadconnected", () => {
  gamepadConnected.set(true);
  startGamepadPolling();
});
window.addEventListener("gamepaddisconnected", () => {
  const pads = navigator.getGamepads?.() || [];
  const any = Array.from(pads).some((p) => p && p.connected);
  gamepadConnected.set(any);
  if (!any) stopGamepadPolling();
});
