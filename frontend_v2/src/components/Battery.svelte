<script>
  let { mv = 0, lowBattery = false } = $props();

  let pct = $derived(Math.max(0, Math.min(100, (mv - 6000) / 24)));
  let fillWidth = $derived(mv > 0 ? Math.max(0, (pct * 24) / 100) : 0);
  let fillColor = $derived(pct < 20 ? "#f44" : pct < 50 ? "#fa0" : "#0f0");

  let text = $derived.by(() => {
    if (mv <= 0) return "--";
    const base = `${(mv / 1000).toFixed(1)}V ${Math.round(pct)}%`;
    return lowBattery ? `${base} LOW` : base;
  });
</script>

<div class="hud-box bat" class:warn={lowBattery}>
  <div class="icon">
    <div class="fill" style="width:{fillWidth}px;background:{fillColor}"></div>
  </div>
  <span>{text}</span>
</div>

<style>
  .bat {
    top: 40px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .icon {
    width: 28px;
    height: 14px;
    border: 1.5px solid #0f0;
    border-radius: 2px;
    position: relative;
  }
  .icon::after {
    content: "";
    position: absolute;
    right: -5px;
    top: 3px;
    width: 3px;
    height: 6px;
    background: #0f0;
    border-radius: 0 1px 1px 0;
  }
  .fill {
    position: absolute;
    left: 1px;
    top: 1px;
    bottom: 1px;
    background: #0f0;
    transition: width 0.3s;
  }
  .warn {
    color: #f44;
    text-shadow: 0 0 6px rgba(255, 0, 0, 0.5);
  }
  .warn .icon {
    border-color: #f44;
  }
  .warn .icon::after {
    background: #f44;
  }
</style>
