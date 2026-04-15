<script>
  import { send } from "../lib/ws.js";

  function estop() {
    send({ type: "stop" });
    send({ type: "set_servos", enabled: false });
  }
</script>

<button class="estop" onclick={estop} title="Emergency stop (also disables servos)">
  E-STOP
</button>

<style>
  .estop {
    position: absolute;
    top: 8px;
    left: calc(50% - 230px);
    z-index: 7;
    padding: 6px 14px;
    border-radius: 18px;
    border: 2px solid #800;
    background: radial-gradient(ellipse at 30% 30%, #f44, #900);
    color: #fff;
    font: bold 12px monospace;
    letter-spacing: 2px;
    cursor: pointer;
    box-shadow: 0 0 12px rgba(255, 0, 0, 0.35);
    text-shadow: 0 1px 1px rgba(0, 0, 0, 0.6);
    transition: transform 0.08s;
  }
  .estop:hover {
    transform: scale(1.04);
  }
  .estop:active {
    transform: scale(0.95);
  }
</style>
