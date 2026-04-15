<script>
  import { onMount } from "svelte";
  import { latestState } from "../lib/ws.js";

  // 18 servos: 6 legs × 3 joints. Layout is rows = legs, cols = joints.
  const LEGS = [
    ["front_left",  "FL"],
    ["front_right", "FR"],
    ["mid_left",    "ML"],
    ["mid_right",   "MR"],
    ["rear_left",   "RL"],
    ["rear_right",  "RR"],
  ];
  const JOINTS = ["coxa", "femur", "tibia"];

  // DS3235SSG mechanical limit ±135° (see config/servos/ds3235ssg.yaml).
  // WARN once we're using > 2/3 of the range in either direction.
  // DANGER once we're within ~15° of the hard stop.
  const MAX_DEG    = 135;
  const WARN_DEG   = 90;
  const DANGER_DEG = 120;

  // Datasheet max angular speed at 5 V is ~460 °/s (see same yaml).
  // WARN once commanded speed crosses 2/3 of that, DANGER at the limit.
  const MAX_DPS    = 460;
  const WARN_DPS   = 300;
  const DANGER_DPS = 460;

  // EMA smoothing for the rate so quantization in the state stream doesn't
  // make the readout flicker. ~3-sample time constant.
  const RATE_ALPHA = 0.35;

  const N = 90;  // ~3s at 30 Hz state stream
  const buffers = {};
  const rates = {};       // smoothed °/s per servo
  const prevDeg = {};
  for (const [legKey] of LEGS) {
    for (const j of JOINTS) {
      const key = `${legKey}.${j}`;
      buffers[key] = new Float32Array(N);
      rates[key] = 0;
      prevDeg[key] = null;
    }
  }
  let prevT = null;

  let canvas;
  let warnCount = $state(0);
  let dangerCount = $state(0);
  let worst = $state(null);     // { key, deg } worst absolute angle
  let fastest = $state(null);   // { key, dps } worst absolute rate

  function angleColor(absDeg) {
    if (absDeg >= DANGER_DEG) return "#ff5050";
    if (absDeg >= WARN_DEG)   return "#ffa030";
    return "#4fdf80";
  }

  function rateColor(absDps) {
    if (absDps >= DANGER_DPS) return "#ff5050";
    if (absDps >= WARN_DPS)   return "#ffa030";
    return "#9bd";
  }

  onMount(() => {
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;

    const LABEL_W = 26;
    const HEAD_H  = 14;
    const GAP     = 3;
    const COLS    = JOINTS.length;
    const ROWS    = LEGS.length;
    const cellW   = (W - LABEL_W - (COLS - 1) * GAP) / COLS;
    const cellH   = (H - HEAD_H - (ROWS - 1) * GAP) / ROWS;

    function drawCell(x, y, w, h, buf, dps) {
      const cur = buf[N - 1];
      const absCur = Math.abs(cur);
      const absDps = Math.abs(dps);
      const aColor = angleColor(absCur);
      const rColor = rateColor(absDps);

      // Cell background tinted by the worse of angle/rate severity.
      const angleSev = absCur >= DANGER_DEG ? 2 : absCur >= WARN_DEG ? 1 : 0;
      const rateSev  = absDps >= DANGER_DPS ? 2 : absDps >= WARN_DPS ? 1 : 0;
      const sev = Math.max(angleSev, rateSev);
      let bg;
      if (sev === 2) bg = "rgba(255,80,80,0.20)";
      else if (sev === 1) bg = "rgba(255,160,48,0.10)";
      else bg = "rgba(255,255,255,0.04)";
      ctx.fillStyle = bg;
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = "rgba(255,255,255,0.10)";
      ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);

      // Zero-angle mid line + warn-band shading.
      const midY = y + h / 2;
      const warnPx = (WARN_DEG / MAX_DEG) * (h / 2 - 1);
      ctx.fillStyle = "rgba(255,160,48,0.05)";
      ctx.fillRect(x, y, w, midY - warnPx - y);                 // top warn band
      ctx.fillRect(x, midY + warnPx, w, y + h - midY - warnPx); // bottom warn band
      ctx.strokeStyle = "rgba(255,255,255,0.18)";
      ctx.beginPath();
      ctx.moveTo(x, midY);
      ctx.lineTo(x + w, midY);
      ctx.stroke();

      // Trace.
      ctx.strokeStyle = aColor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let j = 0; j < N; j++) {
        const v = Math.max(-MAX_DEG, Math.min(MAX_DEG, buf[j]));
        const px = x + (j / (N - 1)) * w;
        const py = midY - (v / MAX_DEG) * (h / 2 - 1);
        if (j === 0) ctx.moveTo(px, py);
        else         ctx.lineTo(px, py);
      }
      ctx.stroke();

      // Top row: current angle (left), rate of change (right).
      ctx.font = "9px monospace";
      ctx.textBaseline = "top";
      ctx.fillStyle = aColor;
      ctx.textAlign = "left";
      ctx.fillText(`${cur.toFixed(0)}\u00B0`, x + 3, y + 2);
      ctx.fillStyle = rColor;
      ctx.textAlign = "right";
      const sign = dps >= 0 ? "+" : "\u2212";
      ctx.fillText(`${sign}${Math.abs(dps).toFixed(0)}\u00B0/s`, x + w - 3, y + 2);
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);

      // Column headers (joint names).
      ctx.fillStyle = "#aaa";
      ctx.font = "10px monospace";
      ctx.textBaseline = "middle";
      ctx.textAlign = "center";
      for (let c = 0; c < COLS; c++) {
        const x = LABEL_W + c * (cellW + GAP) + cellW / 2;
        ctx.fillText(JOINTS[c], x, HEAD_H / 2);
      }

      // Row labels + cells.
      ctx.textAlign = "right";
      ctx.fillStyle = "#bbb";
      for (let r = 0; r < ROWS; r++) {
        const [legKey, legLabel] = LEGS[r];
        const y = HEAD_H + r * (cellH + GAP);
        ctx.fillStyle = "#bbb";
        ctx.textBaseline = "middle";
        ctx.fillText(legLabel, LABEL_W - 4, y + cellH / 2);
        for (let c = 0; c < COLS; c++) {
          const j = JOINTS[c];
          const x = LABEL_W + c * (cellW + GAP);
          const k = `${legKey}.${j}`;
          drawCell(x, y, cellW, cellH, buffers[k], rates[k]);
        }
      }
    }

    const unsub = latestState.subscribe((s) => {
      if (!s || !s.legs) return;
      const t = s.t;
      const dt = (prevT !== null && t > prevT) ? (t - prevT) : 0;
      prevT = t;

      let nWarn = 0;
      let nDanger = 0;
      let worstKey = null;
      let worstAbs = 0;
      let worstDeg = 0;
      let fastKey = null;
      let fastAbs = 0;
      let fastDps = 0;
      for (const [legKey, legLabel] of LEGS) {
        const leg = s.legs[legKey];
        if (!leg) continue;
        for (const j of JOINTS) {
          const k = `${legKey}.${j}`;
          const buf = buffers[k];
          const deg = ((leg.angles?.[j]) || 0) * 180 / Math.PI;
          buf.copyWithin(0, 1);
          buf[N - 1] = deg;

          // Smoothed rate of change (°/s). Skip the first frame and any
          // tick where dt collapsed to zero.
          if (dt > 0 && prevDeg[k] !== null) {
            const inst = (deg - prevDeg[k]) / dt;
            rates[k] = rates[k] * (1 - RATE_ALPHA) + inst * RATE_ALPHA;
          }
          prevDeg[k] = deg;

          const a = Math.abs(deg);
          if (a >= DANGER_DEG) nDanger++;
          else if (a >= WARN_DEG) nWarn++;
          if (a > worstAbs) {
            worstAbs = a;
            worstKey = `${legLabel}.${j}`;
            worstDeg = deg;
          }
          const ar = Math.abs(rates[k]);
          if (ar > fastAbs) {
            fastAbs = ar;
            fastKey = `${legLabel}.${j}`;
            fastDps = rates[k];
          }
        }
      }
      warnCount = nWarn;
      dangerCount = nDanger;
      worst = worstKey ? { key: worstKey, deg: worstDeg } : null;
      fastest = (fastKey && fastAbs >= WARN_DPS) ? { key: fastKey, dps: fastDps } : null;
      draw();
    });

    return () => unsub();
  });
</script>

<div class="hud-box servos">
  <div class="hdr">
    <span class="title">servos</span>
    <span class="legend">
      angle <i class="dot ok"></i>/<i class="dot warn"></i>/<i class="dot danger"></i>
      &nbsp;rate caps {WARN_DPS}/{DANGER_DPS}&deg;/s
    </span>
  </div>
  {#if dangerCount > 0}
    <div class="alert danger">
      ⚠ {dangerCount} servo{dangerCount > 1 ? "s" : ""} near hard limit
      {#if worst}— worst {worst.key} {worst.deg.toFixed(0)}&deg;{/if}
    </div>
  {:else if warnCount > 0}
    <div class="alert warn">
      {warnCount} servo{warnCount > 1 ? "s" : ""} in warn zone
      {#if worst}— worst {worst.key} {worst.deg.toFixed(0)}&deg;{/if}
    </div>
  {/if}
  {#if fastest}
    <div class="alert warn">
      fastest {fastest.key} {fastest.dps >= 0 ? "+" : "−"}{Math.abs(fastest.dps).toFixed(0)}&deg;/s
    </div>
  {/if}
  <canvas bind:this={canvas} width="380" height="220"></canvas>
</div>

<style>
  .servos {
    position: absolute;
    bottom: 12px;
    left: 12px;
    background: rgba(0, 0, 0, 0.78);
    border: 1px solid rgba(0, 255, 0, 0.25);
    border-radius: 6px;
    padding: 6px 8px 8px;
    z-index: 5;
    font-family: monospace;
    font-size: 10px;
    color: #ccc;
    backdrop-filter: blur(4px);
    pointer-events: none;
  }
  .hdr {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
    font-size: 10px;
  }
  .title { color: #aaffaa; font-weight: bold; letter-spacing: 1px; }
  .legend { color: #888; }
  .dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    margin: 0 2px 0 6px;
    vertical-align: middle;
  }
  .dot.ok     { background: #4fdf80; }
  .dot.warn   { background: #ffa030; }
  .dot.danger { background: #ff5050; }
  .alert {
    margin-bottom: 4px;
    padding: 3px 5px;
    border-radius: 3px;
    font-size: 10px;
  }
  .alert.warn   { background: rgba(255,160,48,0.20); color: #ffd080; }
  .alert.danger {
    background: rgba(255,80,80,0.30);
    color: #ffdcdc;
    animation: blink 0.8s ease-in-out infinite;
  }
  @keyframes blink {
    0%, 100% { background: rgba(255,80,80,0.30); }
    50%      { background: rgba(255,80,80,0.55); }
  }
  canvas {
    display: block;
    border-radius: 4px;
  }
</style>
