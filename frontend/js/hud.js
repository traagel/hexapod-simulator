/**
 * Drone-style HUD — artificial horizon, compass, battery, speed, tilt.
 */

// ── Compass ───────────────────────────────────────────────────────────
const compassStrip = document.getElementById("compass-strip");
const COMPASS_LABELS = ["N","","","E","","","S","","","W","",""];
let html = "";
for (let rep = 0; rep < 3; rep++) {
  for (let i = 0; i < 12; i++) {
    const lbl = COMPASS_LABELS[i] || (i * 30);
    html += `<span style="display:inline-block;width:30px;text-align:center">${lbl}</span>`;
  }
}
compassStrip.innerHTML = html;

function updateCompass(yaw) {
  let deg = (-yaw * 180 / Math.PI) % 360;
  if (deg < 0) deg += 360;
  compassStrip.style.left = (-(deg / 360) * 360 - 360 + 100) + "px";
}

// ── Artificial Horizon ────────────────────────────────────────────────
const ahiCtx = document.getElementById("ahi-canvas").getContext("2d");

function drawAHI(roll, pitch) {
  const w = 100, h = 100, cx = w / 2, cy = h / 2, r = 42;
  const ctx = ahiCtx;
  ctx.clearRect(0, 0, w, h);

  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.clip();

  const pitchPx = pitch * 100;
  ctx.translate(cx, cy);
  ctx.rotate(-roll);

  // Sky.
  ctx.fillStyle = "#1a3a5a";
  ctx.fillRect(-r * 2, -r * 2, r * 4, r * 2 + pitchPx);
  // Ground.
  ctx.fillStyle = "#3a2a1a";
  ctx.fillRect(-r * 2, pitchPx, r * 4, r * 2);
  // Horizon line.
  ctx.strokeStyle = "#0f0";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(-r, pitchPx);
  ctx.lineTo(r, pitchPx);
  ctx.stroke();

  // Pitch ladder.
  ctx.strokeStyle = "rgba(0,255,0,0.4)";
  ctx.lineWidth = 0.8;
  ctx.font = "8px monospace";
  ctx.fillStyle = "rgba(0,255,0,0.5)";
  ctx.textAlign = "center";
  for (let d = -30; d <= 30; d += 10) {
    if (d === 0) continue;
    const y = pitchPx - d * (100 / (180 / Math.PI));
    ctx.beginPath();
    ctx.moveTo(-12, y);
    ctx.lineTo(12, y);
    ctx.stroke();
    ctx.fillText(d + "", 20, y + 3);
  }
  ctx.restore();

  // Fixed crosshair.
  ctx.strokeStyle = "#0f0";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx - 18, cy); ctx.lineTo(cx - 8, cy);
  ctx.moveTo(cx + 8, cy);  ctx.lineTo(cx + 18, cy);
  ctx.moveTo(cx, cy - 2);  ctx.lineTo(cx, cy + 2);
  ctx.stroke();

  // Outer ring.
  ctx.strokeStyle = "rgba(0,255,0,0.3)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.stroke();

  // Roll pointer.
  ctx.fillStyle = "#0f0";
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-roll);
  ctx.beginPath();
  ctx.moveTo(0, -r + 1);
  ctx.lineTo(-4, -r + 7);
  ctx.lineTo(4, -r + 7);
  ctx.fill();
  ctx.restore();
}

// ── Battery ───────────────────────────────────────────────────────────
const batText = document.getElementById("bat-text");
const batFill = document.getElementById("bat-fill");
const batBox  = document.getElementById("hud-bat");

function updateBattery(mv, lowBattery) {
  if (mv > 0) {
    const pct = Math.max(0, Math.min(100, (mv - 6000) / 24));
    batText.textContent = `${(mv / 1000).toFixed(1)}V ${Math.round(pct)}%`;
    batFill.style.width = Math.max(0, pct * 24 / 100) + "px";
    batFill.style.background = pct < 20 ? "#f44" : pct < 50 ? "#fa0" : "#0f0";
  } else {
    batText.textContent = "--";
    batFill.style.width = "0px";
  }
  batBox.classList.toggle("warn", !!lowBattery);
  if (lowBattery) batText.textContent += " LOW";
}

// ── Extra telemetry state ──────────────────────────────────────────────
let totalDist = 0;
let prevX = 0, prevY = 0;
let frameCount = 0, lastFpsTime = performance.now(), currentFps = 0;

// ── Public update ─────────────────────────────────────────────────────
export function updateHUD(state) {
  const pose = state.pose;
  const toDeg = 180 / Math.PI;

  // Info bar (minimal).
  document.getElementById("info").textContent =
    `x=${pose.x.toFixed(1)} y=${pose.y.toFixed(1)}`;

  // Battery.
  updateBattery(state.voltage_mv || 0, state.low_battery);

  // Speed.
  const spd = Math.hypot(state.twist.vx, state.twist.vy);
  document.getElementById("speed-val").textContent = spd.toFixed(1);

  // Tilt readout.
  document.getElementById("tilt-roll").textContent  = `R ${((pose.roll || 0) * toDeg).toFixed(1)}`;
  document.getElementById("tilt-pitch").textContent = `P ${((pose.pitch || 0) * toDeg).toFixed(1)}`;

  // Clock.
  const now = new Date();
  document.getElementById("hud-clock").textContent =
    now.toTimeString().slice(0, 8);

  // Uptime.
  const t = state.t || 0;
  const mins = Math.floor(t / 60);
  const secs = Math.floor(t % 60);
  document.getElementById("hud-uptime").textContent =
    `UP ${mins}m${secs.toString().padStart(2, "0")}s`;

  // Distance travelled.
  const dx = pose.x - prevX, dy = pose.y - prevY;
  totalDist += Math.hypot(dx, dy);
  prevX = pose.x; prevY = pose.y;
  document.getElementById("hud-dist").textContent =
    `DST ${totalDist.toFixed(1)}`;

  // Gait phase.
  document.getElementById("hud-phase").textContent =
    `PH ${(state.gait_phase || 0).toFixed(2)}`;

  // Heading (degrees).
  let hdg = (-pose.yaw * toDeg) % 360;
  if (hdg < 0) hdg += 360;
  document.getElementById("hud-hdg").textContent =
    `HDG ${Math.round(hdg)}`;

  // Position.
  document.getElementById("hud-pos").textContent =
    `POS ${pose.x.toFixed(1)},${pose.y.toFixed(1)}`;

  // FPS counter.
  frameCount++;
  const nowMs = performance.now();
  if (nowMs - lastFpsTime >= 1000) {
    currentFps = frameCount;
    frameCount = 0;
    lastFpsTime = nowMs;
  }
  document.getElementById("hud-fps").textContent = `FPS ${currentFps}`;

  // Active legs (contact count).
  const contactCount = Object.values(state.legs).filter(l => l.contact).length;
  document.getElementById("hud-legs").textContent = `LEGS ${contactCount}/6`;

  // Instruments.
  updateCompass(pose.yaw);
  drawAHI(pose.roll || 0, pose.pitch || 0);
}
