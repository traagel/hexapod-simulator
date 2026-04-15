<script>
  let { yaw = 0 } = $props();

  const LABELS = ["N", "", "", "E", "", "", "S", "", "", "W", "", ""];

  const ticks = [];
  for (let rep = 0; rep < 3; rep++) {
    for (let i = 0; i < 12; i++) {
      ticks.push(LABELS[i] || i * 30);
    }
  }

  let left = $derived.by(() => {
    let deg = ((-yaw * 180) / Math.PI) % 360;
    if (deg < 0) deg += 360;
    return -(deg / 360) * 360 - 360 + 100;
  });
</script>

<div class="hud-box compass">
  <div class="strip" style="left:{left}px">
    {#each ticks as t}
      <span>{t}</span>
    {/each}
  </div>
  <div class="caret"></div>
</div>

<style>
  .compass {
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    overflow: hidden;
    width: 200px;
    height: 24px;
    border: 1px solid rgba(0, 255, 0, 0.3);
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.4);
  }
  .strip {
    position: absolute;
    top: 0;
    height: 100%;
    white-space: nowrap;
    font: 11px monospace;
    color: #0f0;
    line-height: 24px;
  }
  .strip span {
    display: inline-block;
    width: 30px;
    text-align: center;
  }
  .caret {
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #0f0;
  }
</style>
