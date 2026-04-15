<script>
  import { get } from "svelte/store";
  import Joystick from "./Joystick.svelte";
  import { speed, sendTwist } from "../lib/input.js";
  import { send } from "../lib/ws.js";

  let move = { x: 0, y: 0 };
  let turn = { x: 0, y: 0 };
  let throttleLast = 0;

  function push() {
    const now = performance.now();
    if (now - throttleLast < 33 && (move.x || move.y || turn.x)) return;
    throttleLast = now;
    const s = get(speed);
    if (!move.x && !move.y && !turn.x) {
      send({ type: "stop" });
      return;
    }
    sendTwist(-move.y * s, -move.x * s, -turn.x * s * 0.1);
  }

  function onMove(x, y) { move = { x, y }; push(); }
  function onTurn(x, y) { turn = { x, y }; push(); }
</script>

<div class="wrap left">
  <Joystick {onMove} label="MOVE" />
</div>
<div class="wrap right">
  <Joystick onMove={onTurn} label="TURN" />
</div>

<style>
  .wrap {
    position: fixed;
    bottom: 50px;
    z-index: 6;
    pointer-events: none;
  }
  .wrap :global(.joy) {
    pointer-events: auto;
  }
  .left { left: 30px; }
  .right { right: 30px; }
</style>
