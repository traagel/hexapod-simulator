/**
 * Entry point — wires modules together and starts the render loop.
 */
import * as THREE from "three";
import { scene, camera, renderer, controls, dirLight } from "./scene.js";
import { bodyGroup, applyState } from "./hexapod.js";
import { updateHUD } from "./hud.js";
import {
  initSliders, initServoControls, initFootTarget,
  initFPV, initMouseTilt, fpvOrientationTick,
  setLatestState, syncLowBattery, handleCameraConfig,
} from "./controls.js";
import { connect, onState, onConfig } from "./ws.js";

// ── Init controls ─────────────────────────────────────────────────────
initSliders();
initServoControls();
initFootTarget();
initFPV();
initMouseTilt();

// ── 3rd person chase camera ───────────────────────────────────────────
let chaseActive = false;
const chaseBtn = document.getElementById("chase-btn");
const CHASE_DIST = 35;    // distance behind
const CHASE_HEIGHT = 20;  // height above
const CHASE_SMOOTH = 0.06; // lerp factor per frame

chaseBtn.onclick = () => {
  chaseActive = !chaseActive;
  chaseBtn.style.color = chaseActive ? "#4f4" : "#ddd";
  controls.enabled = !chaseActive;
};

const _chaseTarget = new THREE.Vector3();
const _chasePos = new THREE.Vector3();

function updateChaseCamera() {
  if (!chaseActive) return;
  const pos = bodyGroup.position;
  const yaw = bodyGroup.rotation.z;

  // Desired camera position: behind and above the robot.
  _chaseTarget.set(
    pos.x - Math.cos(yaw) * CHASE_DIST,
    pos.y - Math.sin(yaw) * CHASE_DIST,
    pos.z + CHASE_HEIGHT,
  );
  // Smooth follow.
  _chasePos.lerpVectors(camera.position, _chaseTarget, CHASE_SMOOTH);
  camera.position.copy(_chasePos);
  camera.lookAt(pos.x, pos.y, pos.z + 5);
}

// ── WebSocket ─────────────────────────────────────────────────────────
onState((state) => {
  setLatestState(state);
  applyState(state);
  updateHUD(state);
  syncLowBattery(state.low_battery);
});
onConfig(handleCameraConfig);
connect(location.hostname);

// ── Render loop ───────────────────────────────────────────────────────
function tick() {
  fpvOrientationTick();
  updateChaseCamera();

  // Keep the shadow light centred on the robot.
  dirLight.position.set(
    bodyGroup.position.x + 30,
    bodyGroup.position.y + 20,
    40,
  );
  dirLight.target.position.copy(bodyGroup.position);
  dirLight.target.updateMatrixWorld();

  if (!chaseActive) controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();
