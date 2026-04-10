/**
 * Input handling — keyboard, mouse tilt, FPV, sliders, servo buttons.
 */
import { send, onOpen } from "./ws.js";
import { controls } from "./scene.js";

// ── Keyboard state ────────────────────────────────────────────────────
const keys = {};
window.addEventListener("keydown", (e) => { keys[e.key.toLowerCase()] = true; pushTwist(); });
window.addEventListener("keyup",   (e) => { keys[e.key.toLowerCase()] = false; pushTwist(); });

// ── Slider bindings ───────────────────────────────────────────────────
function bindSlider(id, type, key) {
  const el = document.getElementById(id);
  const v  = document.getElementById(id + "-v");
  const push = () => {
    v.textContent = el.value;
    send({ type, [key]: parseFloat(el.value) });
  };
  el.addEventListener("input", push);
  onOpen(push);
}

export function initSliders() {
  bindSlider("height", "set_height",        "z");
  bindSlider("step",   "set_step_length",   "length");
  bindSlider("radius", "set_stance_radius", "radius");
  bindSlider("lift",   "set_lift_height",   "height");
  bindSlider("cycle",  "set_cycle_time",    "seconds");
}

// ── Speed ─────────────────────────────────────────────────────────────
const speedEl = document.getElementById("speed");
const speedV  = document.getElementById("speed-v");
speedEl.oninput = () => { speedV.textContent = speedEl.value; };

// ── Servo controls ────────────────────────────────────────────────────
let servosOn = false;
const servoBtn = document.getElementById("servo-toggle");

export function initServoControls() {
  servoBtn.onclick = () => {
    servosOn = !servosOn;
    send({ type: "set_servos", enabled: servosOn });
    servoBtn.textContent = servosOn ? "ON" : "OFF";
    servoBtn.style.color = servosOn ? "#4f4" : "#f44";
  };

  let zeroOn = false;
  const zeroBtn = document.getElementById("zero-btn");
  zeroBtn.onclick = () => {
    zeroOn = !zeroOn;
    send({ type: "zero_stance", enabled: zeroOn });
    zeroBtn.style.color = zeroOn ? "#4f4" : "#ddd";
  };

  let lowPower = false;
  const lpBtn = document.getElementById("lowpwr-btn");
  lpBtn.onclick = () => {
    lowPower = !lowPower;
    lpBtn.style.color = lowPower ? "#ff0" : "#ddd";
    if (lowPower) {
      speedEl.value = Math.max(1, Math.round(parseFloat(speedEl.value) / 2));
      speedV.textContent = speedEl.value;
      const cycleEl = document.getElementById("cycle");
      cycleEl.value = Math.min(4, (parseFloat(cycleEl.value) * 2).toFixed(1));
      document.getElementById("cycle-v").textContent = cycleEl.value;
      cycleEl.dispatchEvent(new Event("input"));
    }
  };
}

/** Called from HUD update to sync servo button on low battery. */
export function syncLowBattery(lowBattery) {
  if (lowBattery && servosOn) {
    servosOn = false;
    servoBtn.textContent = "OFF";
    servoBtn.style.color = "#f44";
  }
}

// ── Foot target override ──────────────────────────────────────────────
let latestState = null;

export function setLatestState(state) { latestState = state; }

export function initFootTarget() {
  const targetLegEl = document.getElementById("target-leg");
  const txEl = document.getElementById("tx");
  const tyEl = document.getElementById("ty");
  const tzEl = document.getElementById("tz");
  const txV  = document.getElementById("tx-v");
  const tyV  = document.getElementById("ty-v");
  const tzV  = document.getElementById("tz-v");

  function refreshLabels() {
    txV.textContent = txEl.value;
    tyV.textContent = tyEl.value;
    tzV.textContent = tzEl.value;
  }
  [txEl, tyEl, tzEl].forEach(el => el.addEventListener("input", refreshLabels));

  let timer = null;
  function pushFootTarget() {
    const leg = targetLegEl.value;
    if (!leg) return;
    send({
      type: "set_foot_target", leg,
      x: parseFloat(txEl.value), y: parseFloat(tyEl.value), z: parseFloat(tzEl.value),
    });
  }

  function clamp(el, v) {
    return Math.max(parseFloat(el.min), Math.min(parseFloat(el.max), v));
  }

  targetLegEl.addEventListener("change", () => {
    if (timer) { clearInterval(timer); timer = null; }
    if (targetLegEl.value && latestState) {
      const foot = latestState.legs[targetLegEl.value]?.foot;
      if (foot) {
        const snap = (v) => Math.round(v * 2) / 2;
        txEl.value = clamp(txEl, snap(foot[0]));
        tyEl.value = clamp(tyEl, snap(foot[1]));
        tzEl.value = clamp(tzEl, snap(foot[2]));
        refreshLabels();
      }
      pushFootTarget();
      timer = setInterval(pushFootTarget, 33);
    }
  });
}

// ── FPV mode ──────────────────────────────────────────────────────────
let fpvActive = false;
let fpvRoll = 0, fpvPitch = 0, fpvYaw = 0;
const MAX_TILT = Math.PI / 12;

const sensYawEl   = document.getElementById("sens-yaw");
const sensPitchEl = document.getElementById("sens-pitch");
const sensRollEl  = document.getElementById("sens-roll");
const sensYawV    = document.getElementById("sens-yaw-v");
const sensPitchV  = document.getElementById("sens-pitch-v");
const sensRollV   = document.getElementById("sens-roll-v");
sensYawEl.oninput   = () => { sensYawV.textContent = sensYawEl.value; };
sensPitchEl.oninput = () => { sensPitchV.textContent = sensPitchEl.value; };
sensRollEl.oninput  = () => { sensRollV.textContent = sensRollEl.value; };

const ROLL_DECAY = 0.92;

export function initFPV() {
  const fpvBtn = document.getElementById("fpv-btn");
  const camDiv = document.getElementById("camera");

  function enterFPV() {
    fpvActive = true;
    document.body.classList.add("fpv");
    camDiv.style.display = "block";
    fpvBtn.style.color = "#4f4";
    controls.enabled = false;
    document.body.requestPointerLock();
  }
  function exitFPV() {
    fpvActive = false;
    document.body.classList.remove("fpv");
    fpvBtn.style.color = "#ddd";
    controls.enabled = true;
    fpvRoll = 0; fpvPitch = 0;
    send({ type: "set_orientation", roll: 0, pitch: 0 });
    if (document.pointerLockElement) document.exitPointerLock();
  }
  fpvBtn.onclick = () => { fpvActive ? exitFPV() : enterFPV(); };
  document.addEventListener("pointerlockchange", () => {
    if (!document.pointerLockElement && fpvActive) exitFPV();
  });

  document.getElementById("camera-close").onclick = () => {
    const cam = document.getElementById("camera");
    cam.style.display = cam.style.display === "none" ? "block" : "none";
  };
}

/** Called every render frame for smooth roll ramp/decay. */
export function fpvOrientationTick() {
  if (!fpvActive) return;
  const rollDir = (keys["q"] ? 1 : 0) - (keys["e"] ? 1 : 0);
  const rollSpeed = sensRollEl.value / 10;
  if (rollDir !== 0) {
    fpvRoll += rollDir * rollSpeed * 0.02;
    fpvRoll = Math.max(-MAX_TILT, Math.min(MAX_TILT, fpvRoll));
  } else {
    fpvRoll *= ROLL_DECAY;
    if (Math.abs(fpvRoll) < 0.001) fpvRoll = 0;
  }
  send({ type: "set_orientation", roll: fpvRoll, pitch: fpvPitch });
}

// ── Mouse tilt (Shift + mouse) ────────────────────────────────────────
let shiftHeld = false;

export function initMouseTilt() {
  window.addEventListener("keydown", (e) => {
    if (e.key === "Shift" && !shiftHeld) {
      shiftHeld = true;
      controls.enabled = false;
    }
  });
  window.addEventListener("keyup", (e) => {
    if (e.key === "Shift") {
      shiftHeld = false;
      controls.enabled = true;
      send({ type: "set_orientation", roll: 0, pitch: 0 });
    }
  });
  window.addEventListener("mousemove", (e) => {
    if (fpvActive) {
      const yawSens   = sensYawEl.value / 1000;
      const pitchSens = sensPitchEl.value / 2000;
      fpvYaw   = -e.movementX * yawSens;
      fpvPitch = Math.max(-MAX_TILT, Math.min(MAX_TILT, fpvPitch + e.movementY * pitchSens));
      send({ type: "twist", vx: 0, vy: 0, omega: fpvYaw });
      fpvYaw = 0;
      return;
    }
    if (!shiftHeld) return;
    const nx = (e.clientX / window.innerWidth  - 0.5) * 2;
    const ny = (e.clientY / window.innerHeight - 0.5) * 2;
    send({ type: "set_orientation", roll: -nx * MAX_TILT, pitch: ny * MAX_TILT });
  });
}

// ── Twist (WASD / QE) ────────────────────────────────────────────────
function pushTwist() {
  if (keys[" "]) { send({ type: "stop" }); fpvYaw = 0; return; }
  const spd = parseFloat(speedEl.value);
  const vx = (keys["w"] ? spd : 0) - (keys["s"] ? spd : 0);
  const vy = (keys["a"] ? spd : 0) - (keys["d"] ? spd : 0);
  if (fpvActive) {
    send({ type: "twist", vx, vy, omega: fpvYaw });
    fpvYaw = 0;
  } else {
    const turnRate = spd * 0.1;
    const omega = (keys["q"] ? turnRate : 0) - (keys["e"] ? turnRate : 0);
    send({ type: "twist", vx, vy, omega });
  }
}

// ── Camera config ─────────────────────────────────────────────────────
export function handleCameraConfig(msg) {
  if (msg.camera_url) {
    const url = new URL(msg.camera_url);
    url.hostname = location.hostname;
    document.getElementById("camera-feed").src = url.toString();
    document.getElementById("camera").style.display = "block";
  }
}
