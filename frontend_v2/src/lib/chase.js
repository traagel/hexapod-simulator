import * as THREE from "three";
import { camera, controls } from "./scene.js";
import { bodyGroup } from "./hexapod.js";

const DIST = 35;
const HEIGHT = 20;
const SMOOTH = 0.06;

let active = false;
const _target = new THREE.Vector3();
const _pos = new THREE.Vector3();

export function setChaseActive(on) {
  active = on;
  controls.enabled = !on;
}

export function isChaseActive() {
  return active;
}

export function updateChaseCamera() {
  if (!active) return;
  const pos = bodyGroup.position;
  const yaw = bodyGroup.rotation.z;
  _target.set(
    pos.x - Math.cos(yaw) * DIST,
    pos.y - Math.sin(yaw) * DIST,
    pos.z + HEIGHT,
  );
  _pos.lerpVectors(camera.position, _target, SMOOTH);
  camera.position.copy(_pos);
  camera.lookAt(pos.x, pos.y, pos.z + 5);
}
