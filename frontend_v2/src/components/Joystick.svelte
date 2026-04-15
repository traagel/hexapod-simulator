<script>
  let { onMove, label = "" } = $props();

  let host;
  let active = $state(false);
  let knobX = $state(0);
  let knobY = $state(0);
  let pointerId = null;

  function handle(e) {
    if (!host || e.pointerId !== pointerId) return;
    const r = host.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    let dx = (e.clientX - cx) / (r.width / 2);
    let dy = (e.clientY - cy) / (r.height / 2);
    const mag = Math.hypot(dx, dy);
    if (mag > 1) { dx /= mag; dy /= mag; }
    knobX = dx;
    knobY = dy;
    onMove?.(dx, dy);
  }

  function onDown(e) {
    if (pointerId !== null) return;
    pointerId = e.pointerId;
    host.setPointerCapture(e.pointerId);
    active = true;
    handle(e);
  }
  function onUp(e) {
    if (e.pointerId !== pointerId) return;
    host.releasePointerCapture(e.pointerId);
    pointerId = null;
    active = false;
    knobX = 0;
    knobY = 0;
    onMove?.(0, 0);
  }
</script>

<div
  class="joy"
  class:active
  bind:this={host}
  onpointerdown={onDown}
  onpointermove={handle}
  onpointerup={onUp}
  onpointercancel={onUp}
>
  <div class="knob" style="transform:translate({knobX * 40}px, {knobY * 40}px)"></div>
  {#if label}<span class="lbl">{label}</span>{/if}
</div>

<style>
  .joy {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.45);
    border: 1px solid rgba(0, 255, 0, 0.3);
    position: relative;
    touch-action: none;
    pointer-events: auto;
  }
  .joy.active {
    border-color: rgba(0, 255, 0, 0.7);
  }
  .knob {
    position: absolute;
    top: 30px;
    left: 30px;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: rgba(0, 255, 0, 0.35);
    border: 1px solid rgba(0, 255, 0, 0.6);
    transition: transform 0.05s;
  }
  .lbl {
    position: absolute;
    bottom: -18px;
    left: 50%;
    transform: translateX(-50%);
    font: 10px monospace;
    color: #0f0;
    opacity: 0.6;
    letter-spacing: 1px;
  }
</style>
