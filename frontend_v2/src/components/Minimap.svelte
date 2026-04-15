<script>
  import { onMount } from "svelte";
  import * as THREE from "three";
  import { scene } from "../lib/scene.js";
  import { bodyGroup } from "../lib/hexapod.js";

  const SIZE = 180;
  const HALF = 40;

  let host;

  onMount(() => {
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(SIZE, SIZE);
    host.appendChild(renderer.domElement);

    const cam = new THREE.OrthographicCamera(-HALF, HALF, HALF, -HALF, 0.1, 500);
    cam.up.set(0, 1, 0);

    let raf;
    function tick() {
      cam.position.set(bodyGroup.position.x, bodyGroup.position.y, 80);
      cam.lookAt(bodyGroup.position.x, bodyGroup.position.y, 0);
      renderer.render(scene, cam);
      raf = requestAnimationFrame(tick);
    }
    tick();

    return () => {
      cancelAnimationFrame(raf);
      renderer.dispose();
      if (renderer.domElement.parentNode === host) host.removeChild(renderer.domElement);
    };
  });
</script>

<div class="mini" bind:this={host}></div>

<style>
  .mini {
    position: absolute;
    bottom: 60px;
    left: 8px;
    z-index: 5;
    width: 180px;
    height: 180px;
    border: 1px solid rgba(0, 255, 0, 0.35);
    border-radius: 4px;
    overflow: hidden;
    background: rgba(0, 0, 0, 0.5);
  }
</style>
