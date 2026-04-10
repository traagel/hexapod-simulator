/**
 * Three.js scene setup — renderer, camera, lights, ground.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111111);

export const camera = new THREE.PerspectiveCamera(
  45, window.innerWidth / window.innerHeight, 0.1, 1000
);
camera.position.set(40, 40, 40);
camera.up.set(0, 0, 1);

export const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

export const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 5);

// ── Lighting ──────────────────────────────────────────────────────────
const ambientLight = new THREE.AmbientLight(0x404050, 1.5);
scene.add(ambientLight);

export const dirLight = new THREE.DirectionalLight(0xffffff, 2.0);
dirLight.position.set(30, 20, 40);
dirLight.castShadow = true;
dirLight.shadow.mapSize.set(1024, 1024);
dirLight.shadow.camera.left = -40;
dirLight.shadow.camera.right = 40;
dirLight.shadow.camera.top = 40;
dirLight.shadow.camera.bottom = -40;
dirLight.shadow.camera.near = 1;
dirLight.shadow.camera.far = 100;
scene.add(dirLight);

const fillLight = new THREE.DirectionalLight(0x8888ff, 0.4);
fillLight.position.set(-20, -10, 15);
scene.add(fillLight);

// ── Ground ────────────────────────────────────────────────────────────
const grid = new THREE.GridHelper(100, 50, 0x444444, 0x222222);
grid.rotation.x = Math.PI / 2;
scene.add(grid);
scene.add(new THREE.AxesHelper(8));

const groundPlane = new THREE.Mesh(
  new THREE.PlaneGeometry(200, 200),
  new THREE.ShadowMaterial({ opacity: 0.3 })
);
groundPlane.position.z = -0.01;
groundPlane.receiveShadow = true;
scene.add(groundPlane);
