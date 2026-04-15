<script>
  let { roll = 0, pitch = 0 } = $props();

  let canvas;

  $effect(() => {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    draw(ctx, roll, pitch);
  });

  function draw(ctx, roll, pitch) {
    const w = 100, h = 100, cx = w / 2, cy = h / 2, r = 42;
    ctx.clearRect(0, 0, w, h);

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();

    const pitchPx = pitch * 100;
    ctx.translate(cx, cy);
    ctx.rotate(-roll);

    ctx.fillStyle = "#1a3a5a";
    ctx.fillRect(-r * 2, -r * 2, r * 4, r * 2 + pitchPx);
    ctx.fillStyle = "#3a2a1a";
    ctx.fillRect(-r * 2, pitchPx, r * 4, r * 2);
    ctx.strokeStyle = "#0f0";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(-r, pitchPx);
    ctx.lineTo(r, pitchPx);
    ctx.stroke();

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

    ctx.strokeStyle = "#0f0";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx - 18, cy); ctx.lineTo(cx - 8, cy);
    ctx.moveTo(cx + 8, cy);  ctx.lineTo(cx + 18, cy);
    ctx.moveTo(cx, cy - 2);  ctx.lineTo(cx, cy + 2);
    ctx.stroke();

    ctx.strokeStyle = "rgba(0,255,0,0.3)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();

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
</script>

<div class="hud-box ahi">
  <canvas bind:this={canvas} width="100" height="100"></canvas>
</div>

<style>
  .ahi {
    bottom: 50px;
    left: 50%;
    transform: translateX(-50%);
  }
  canvas {
    border: 1px solid rgba(0, 255, 0, 0.3);
    border-radius: 50%;
  }
</style>
