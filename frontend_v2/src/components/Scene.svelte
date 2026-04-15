<script>
  import { onMount } from "svelte";
  import { scene, camera, renderer, controls, dirLight } from "../lib/scene.js";
  import { bodyGroup, applyState } from "../lib/hexapod.js";
  import { latestState } from "../lib/ws.js";
  import { updateChaseCamera, isChaseActive } from "../lib/chase.js";
  import { fpvOrientationTick } from "../lib/input.js";

  let host;

  onMount(() => {
    host.appendChild(renderer.domElement);

    const unsub = latestState.subscribe((s) => {
      if (s) applyState(s);
    });

    let raf;
    function tick() {
      fpvOrientationTick();
      updateChaseCamera();
      dirLight.position.set(
        bodyGroup.position.x + 30,
        bodyGroup.position.y + 20,
        40,
      );
      dirLight.target.position.copy(bodyGroup.position);
      dirLight.target.updateMatrixWorld();
      if (!isChaseActive()) controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    }
    tick();

    return () => {
      cancelAnimationFrame(raf);
      unsub();
    };
  });
</script>

<div bind:this={host} class="scene-host"></div>

<style>
  .scene-host {
    position: fixed;
    inset: 0;
    z-index: 0;
  }
  .scene-host :global(canvas) {
    display: block;
  }
</style>
