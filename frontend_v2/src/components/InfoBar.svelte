<script>
  import { connected, latestState } from "../lib/ws.js";

  let text = $state("connecting...");

  $effect(() => {
    const c = $connected;
    const s = $latestState;
    if (!c) {
      text = "disconnected";
    } else if (s) {
      text = `x=${s.pose.x.toFixed(1)} y=${s.pose.y.toFixed(1)}`;
    } else {
      text = "connected";
    }
  });
</script>

<div class="info">{text}</div>

<style>
  .info {
    position: absolute;
    top: 8px;
    left: 8px;
    padding: 8px 12px;
    background: rgba(0, 0, 0, 0.65);
    border-radius: 6px;
    font-size: 12px;
    font-family: monospace;
    backdrop-filter: blur(4px);
    z-index: 5;
  }
</style>
