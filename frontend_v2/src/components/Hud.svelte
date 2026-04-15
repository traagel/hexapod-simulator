<script>
  import { latestState } from "../lib/ws.js";
  import { msgRate } from "../lib/metrics.js";
  import Battery from "./Battery.svelte";
  import Compass from "./Compass.svelte";
  import Ahi from "./Ahi.svelte";

  const TO_DEG = 180 / Math.PI;

  let totalDist = 0;
  let prevX = 0, prevY = 0;
  let frameCount = 0;
  let lastFpsTime = performance.now();

  let state = $state(null);
  let fps = $state(0);
  let clock = $state("00:00:00");
  let distDisplay = $state(0);

  $effect(() => {
    const s = $latestState;
    if (!s) return;

    const dx = s.pose.x - prevX;
    const dy = s.pose.y - prevY;
    totalDist += Math.hypot(dx, dy);
    prevX = s.pose.x;
    prevY = s.pose.y;
    distDisplay = totalDist;

    frameCount++;
    const nowMs = performance.now();
    if (nowMs - lastFpsTime >= 1000) {
      fps = frameCount;
      frameCount = 0;
      lastFpsTime = nowMs;
    }

    clock = new Date().toTimeString().slice(0, 8);
    state = s;
  });

  let spd = $derived(
    state ? Math.hypot(state.twist.vx, state.twist.vy) : 0,
  );
  let roll = $derived(state ? (state.pose.roll || 0) : 0);
  let pitch = $derived(state ? (state.pose.pitch || 0) : 0);
  let yaw = $derived(state ? state.pose.yaw : 0);
  let hdg = $derived.by(() => {
    let v = (-yaw * TO_DEG) % 360;
    if (v < 0) v += 360;
    return Math.round(v);
  });
  let contactCount = $derived(
    state ? Object.values(state.legs).filter((l) => l.contact).length : 0,
  );
  let uptime = $derived.by(() => {
    const t = state?.t || 0;
    const m = Math.floor(t / 60);
    const sec = Math.floor(t % 60);
    return `UP ${m}m${sec.toString().padStart(2, "0")}s`;
  });
</script>

<div class="hud">
  <Battery
    mv={state?.voltage_mv || 0}
    lowBattery={state?.low_battery || false}
  />
  <Compass {yaw} />
  <Ahi {roll} {pitch} />

  <div class="hud-box speed">
    <div class="speed-val">{spd.toFixed(1)}</div>
    <div class="speed-lbl">SPD</div>
  </div>

  <div class="hud-box tilt">
    <div>R {(roll * TO_DEG).toFixed(1)}</div>
    <div>P {(pitch * TO_DEG).toFixed(1)}</div>
  </div>

  <div class="hud-box telemetry">
    <div>{clock}</div>
    <div>{uptime}</div>
    <div>DST {distDisplay.toFixed(1)}</div>
    <div>PH {(state?.gait_phase || 0).toFixed(2)}</div>
  </div>

  <div class="hud-box right">
    <div>HDG {hdg}</div>
    <div>POS {state ? state.pose.x.toFixed(1) : "0.0"},{state ? state.pose.y.toFixed(1) : "0.0"}</div>
    <div>FPS {fps || "--"}</div>
    <div>LEGS {contactCount}/6</div>
    <div>WS {$msgRate}/s</div>
  </div>
</div>

<style>
  .hud {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 5;
  }
  .hud :global(*) {
    pointer-events: none;
  }
  :global(.hud-box) {
    position: absolute;
    font: 12px monospace;
    color: #0f0;
    text-shadow: 0 0 4px rgba(0, 255, 0, 0.4);
  }
  .speed {
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    text-align: right;
    line-height: 1.8;
  }
  .speed-val {
    font-size: 12px;
  }
  .speed-lbl {
    font-size: 9px;
    opacity: 0.6;
  }
  .tilt {
    bottom: 50px;
    left: 50%;
    margin-left: 60px;
    line-height: 1.8;
  }
  .telemetry {
    top: 42px;
    left: 12px;
    line-height: 1.8;
    font-size: 11px;
    opacity: 0.7;
  }
  .right {
    bottom: 50px;
    right: 12px;
    text-align: right;
    line-height: 1.8;
    font-size: 11px;
    opacity: 0.7;
  }
</style>
