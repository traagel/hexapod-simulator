<script>
  import { onMount } from "svelte";
  import { latestState } from "../lib/ws.js";

  const N = 120;
  const series = [
    { label: "V",   color: "#0f0", scale: (s) => (s.voltage_mv || 0) / 1000, max: 30 },
    { label: "SPD", color: "#4af", scale: (s) => Math.hypot(s.twist.vx, s.twist.vy), max: 30 },
    { label: "PH",  color: "#fa0", scale: (s) => s.gait_phase || 0, max: 1 },
  ];
  const buffers = series.map(() => new Float32Array(N));

  let canvas;

  onMount(() => {
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    const rowH = H / series.length;

    function draw() {
      ctx.clearRect(0, 0, W, H);
      for (let i = 0; i < series.length; i++) {
        const sp = series[i];
        const y0 = i * rowH;
        ctx.fillStyle = "rgba(0,0,0,0.35)";
        ctx.fillRect(0, y0, W, rowH);
        ctx.strokeStyle = sp.color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let j = 0; j < N; j++) {
          const v = Math.max(0, Math.min(sp.max, buffers[i][j]));
          const x = (j / (N - 1)) * W;
          const y = y0 + rowH - 2 - (v / sp.max) * (rowH - 4);
          if (j === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.fillStyle = sp.color;
        ctx.font = "9px monospace";
        ctx.textBaseline = "top";
        ctx.fillText(sp.label, 4, y0 + 2);
        const current = buffers[i][N - 1];
        ctx.textAlign = "right";
        ctx.fillText(current.toFixed(1), W - 4, y0 + 2);
        ctx.textAlign = "left";
      }
    }

    const unsub = latestState.subscribe((s) => {
      if (!s) return;
      for (let i = 0; i < series.length; i++) {
        buffers[i].copyWithin(0, 1);
        buffers[i][N - 1] = series[i].scale(s);
      }
      draw();
    });

    return () => unsub();
  });
</script>

<div class="hud-box sparks">
  <canvas bind:this={canvas} width="200" height="66"></canvas>
</div>

<style>
  .sparks {
    bottom: 160px;
    right: 12px;
    z-index: 5;
    pointer-events: none;
  }
  canvas {
    border: 1px solid rgba(0, 255, 0, 0.25);
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.4);
    display: block;
  }
</style>
