import { camera, controls } from "./scene.js";
import { setChaseActive } from "./chase.js";

export function applyCameraPreset(name) {
  setChaseActive(false);
  controls.enabled = true;
  controls.target.set(0, 0, 5);
  switch (name) {
    case "iso":
      camera.position.set(40, 40, 40);
      break;
    case "top":
      camera.position.set(0, 0, 70);
      break;
    case "side":
      camera.position.set(60, 0, 20);
      break;
    case "front":
      camera.position.set(0, -60, 20);
      break;
  }
  controls.update();
}
