<script>
  import { cameraUrl } from "../lib/ws.js";

  let visible = $state(true);
  let closed = $state(false);

  $effect(() => {
    if ($cameraUrl && !closed) visible = true;
  });

  function toggle() {
    visible = !visible;
    closed = !visible;
  }
</script>

{#if $cameraUrl && visible}
  <div id="camera" class="camera">
    <img src={$cameraUrl} alt="camera feed" />
    <button onclick={toggle}>x</button>
  </div>
{/if}

<style>
  .camera {
    position: absolute;
    bottom: 8px;
    right: 8px;
    z-index: 5;
  }
  .camera img {
    border-radius: 4px;
    max-width: 320px;
    display: block;
  }
  .camera button {
    position: absolute;
    top: 4px;
    right: 4px;
    background: rgba(0, 0, 0, 0.6);
    color: #ddd;
    border: none;
    border-radius: 3px;
    cursor: pointer;
    font-size: 14px;
    padding: 2px 6px;
  }
</style>
