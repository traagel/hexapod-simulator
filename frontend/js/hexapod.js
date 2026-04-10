/**
 * Hexapod 3D model — body plate, legs, support polygons, trail.
 */
import * as THREE from "three";
import { scene } from "./scene.js";

export const LEG_NAMES = [
  "front_left", "front_right",
  "mid_left",   "mid_right",
  "rear_left",  "rear_right",
];

export const bodyGroup = new THREE.Group();
scene.add(bodyGroup);

// ── Materials ─────────────────────────────────────────────────────────
const bodyMat  = new THREE.MeshStandardMaterial({ color: 0x2a2a2a, metalness: 0.4, roughness: 0.5 });
const coxaMat  = new THREE.MeshStandardMaterial({ color: 0x555555, metalness: 0.3, roughness: 0.6 });
const femurMat = new THREE.MeshStandardMaterial({ color: 0x444444, metalness: 0.3, roughness: 0.6 });
const tibiaMat = new THREE.MeshStandardMaterial({ color: 0x333333, metalness: 0.3, roughness: 0.6 });
const jointMat = new THREE.MeshStandardMaterial({ color: 0x888888, metalness: 0.6, roughness: 0.3 });
const footMatOff = new THREE.MeshStandardMaterial({ color: 0xff5050, metalness: 0.2, roughness: 0.4 });
const footMatOn  = new THREE.MeshStandardMaterial({
  color: 0x44ff66, metalness: 0.2, roughness: 0.4, emissive: 0x114422, emissiveIntensity: 0.5,
});

// ── Shared geometry ───────────────────────────────────────────────────
const segGeo   = new THREE.CylinderGeometry(1, 1, 1, 8);
const jointGeo = new THREE.SphereGeometry(1, 10, 8);
const footGeo  = new THREE.SphereGeometry(1, 12, 8);

// ── Body plate ────────────────────────────────────────────────────────
const bodyMesh = new THREE.Mesh(new THREE.BufferGeometry(), bodyMat);
bodyMesh.castShadow = true;
bodyGroup.add(bodyMesh);

// Forward arrow.
const arrowShape = new THREE.Shape();
arrowShape.moveTo(0, 0);
arrowShape.lineTo(-1.2, 2);
arrowShape.lineTo(1.2, 2);
arrowShape.closePath();
const arrowGeo = new THREE.ExtrudeGeometry(arrowShape, { depth: 0.3, bevelEnabled: false });
const arrowMat = new THREE.MeshStandardMaterial({ color: 0x44aaff, metalness: 0.3, roughness: 0.4 });
const arrowMesh = new THREE.Mesh(arrowGeo, arrowMat);
arrowMesh.castShadow = true;
bodyGroup.add(arrowMesh);

// ── Leg parts ─────────────────────────────────────────────────────────
function makeSeg(mat, radius) {
  const m = new THREE.Mesh(segGeo, mat);
  m.castShadow = true;
  m.userData.radius = radius;
  bodyGroup.add(m);
  return m;
}
function makeJoint(mat, radius) {
  const m = new THREE.Mesh(jointGeo, mat);
  m.castShadow = true;
  m.scale.setScalar(radius);
  bodyGroup.add(m);
  return m;
}

const legParts = {};
const footMarkers = {};
for (const name of LEG_NAMES) {
  const coxa  = makeSeg(coxaMat, 0.6);
  const femur = makeSeg(femurMat, 0.5);
  const tibia = makeSeg(tibiaMat, 0.4);
  const j1 = makeJoint(jointMat, 0.7);
  const j2 = makeJoint(jointMat, 0.6);
  const foot = new THREE.Mesh(footGeo, footMatOff);
  foot.castShadow = true;
  foot.scale.setScalar(0.5);
  bodyGroup.add(foot);
  footMarkers[name] = foot;
  legParts[name] = { coxa, femur, tibia, j1, j2, foot };
}

// ── Segment positioning ───────────────────────────────────────────────
const _vA = new THREE.Vector3();
const _vB = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _yAxis = new THREE.Vector3(0, 1, 0);
const _quat = new THREE.Quaternion();

function positionSeg(mesh, a, b) {
  _vA.set(a[0], a[1], a[2]);
  _vB.set(b[0], b[1], b[2]);
  _dir.subVectors(_vB, _vA);
  const len = _dir.length();
  mesh.position.lerpVectors(_vA, _vB, 0.5);
  _dir.normalize();
  _quat.setFromUnitVectors(_yAxis, _dir);
  mesh.quaternion.copy(_quat);
  mesh.scale.set(mesh.userData.radius, len, mesh.userData.radius);
}

// ── Support polygons (tripod groups) ──────────────────────────────────
const TRIPOD_GROUPS = [
  { color: 0x4488ff, legs: ["front_right", "mid_left",  "rear_right"] },
  { color: 0xff8844, legs: ["front_left",  "mid_right", "rear_left"]  },
];
const polyMeshes = TRIPOD_GROUPS.map((g) => {
  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(9), 3));
  geom.setIndex([0, 1, 2]);
  const mesh = new THREE.Mesh(geom, new THREE.MeshBasicMaterial({
    color: g.color, transparent: true, opacity: 0.25, side: THREE.DoubleSide, depthWrite: false,
  }));
  scene.add(mesh);
  const edgeGeom = new THREE.BufferGeometry();
  edgeGeom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(12), 3));
  const edge = new THREE.Line(edgeGeom, new THREE.LineBasicMaterial({ color: g.color }));
  scene.add(edge);
  return { mesh, edge };
});

function updatePolygons(state) {
  const pose = state.pose;
  bodyGroup.updateMatrixWorld();
  const _v = new THREE.Vector3();
  const toWorld = (b) => {
    _v.set(b[0], b[1], b[2] - pose.z);
    bodyGroup.localToWorld(_v);
    return [_v.x, _v.y, 0.02];
  };
  TRIPOD_GROUPS.forEach((group, i) => {
    const feetWorld = group.legs.map((name) => toWorld(state.legs[name].foot));
    const cx = (feetWorld[0][0] + feetWorld[1][0] + feetWorld[2][0]) / 3;
    const cy = (feetWorld[0][1] + feetWorld[1][1] + feetWorld[2][1]) / 3;
    feetWorld.sort((a, b) =>
      Math.atan2(a[1] - cy, a[0] - cx) - Math.atan2(b[1] - cy, b[0] - cx)
    );
    const { mesh, edge } = polyMeshes[i];
    const arr = mesh.geometry.attributes.position.array;
    for (let k = 0; k < 3; k++) {
      arr[k * 3] = feetWorld[k][0]; arr[k * 3 + 1] = feetWorld[k][1]; arr[k * 3 + 2] = feetWorld[k][2];
    }
    mesh.geometry.attributes.position.needsUpdate = true;
    mesh.geometry.computeBoundingSphere();
    const earr = edge.geometry.attributes.position.array;
    for (let k = 0; k < 3; k++) {
      earr[k * 3] = feetWorld[k][0]; earr[k * 3 + 1] = feetWorld[k][1]; earr[k * 3 + 2] = feetWorld[k][2];
    }
    earr[9] = feetWorld[0][0]; earr[10] = feetWorld[0][1]; earr[11] = feetWorld[0][2];
    edge.geometry.attributes.position.needsUpdate = true;
  });
}

// ── Body trail ────────────────────────────────────────────────────────
const trailMax = 600;
const trailGeom = new THREE.BufferGeometry();
trailGeom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(trailMax * 3), 3));
const trailLine = new THREE.Line(trailGeom, new THREE.LineBasicMaterial({ color: 0x66aaff }));
scene.add(trailLine);
let trailCount = 0;

// ── Apply state ───────────────────────────────────────────────────────
export function applyState(state) {
  const pose = state.pose;
  bodyGroup.position.set(pose.x, pose.y, pose.z);
  bodyGroup.rotation.set(pose.roll || 0, pose.pitch || 0, pose.yaw, "ZYX");

  // Body plate.
  const bodyVerts = LEG_NAMES.map((name) => {
    const cs = state.legs[name].coxa_start;
    return new THREE.Vector2(cs[0], cs[1]);
  });
  const cx = bodyVerts.reduce((s, v) => s + v.x, 0) / 6;
  const cy = bodyVerts.reduce((s, v) => s + v.y, 0) / 6;
  bodyVerts.sort((a, b) =>
    Math.atan2(a.y - cy, a.x - cx) - Math.atan2(b.y - cy, b.x - cx)
  );
  bodyMesh.geometry.dispose();
  bodyMesh.geometry = new THREE.ExtrudeGeometry(new THREE.Shape(bodyVerts), {
    depth: 1.5, bevelEnabled: true, bevelThickness: 0.3, bevelSize: 0.3, bevelSegments: 2,
  });
  const mountZ = state.legs[LEG_NAMES[0]].coxa_start[2] - pose.z;
  bodyMesh.geometry.translate(0, 0, -0.75);
  bodyMesh.position.z = mountZ;

  arrowMesh.position.set(4, 0, mountZ + 0.8);
  arrowMesh.rotation.z = Math.PI / 2;

  // Legs.
  LEG_NAMES.forEach((name) => {
    const leg = state.legs[name];
    if (!leg) return;
    const oz = (p) => [p[0], p[1], p[2] - pose.z];
    const p0 = oz(leg.coxa_start), p1 = oz(leg.coxa_end);
    const p2 = oz(leg.femur_end), p3 = oz(leg.foot);
    const parts = legParts[name];
    positionSeg(parts.coxa, p0, p1);
    positionSeg(parts.femur, p1, p2);
    positionSeg(parts.tibia, p2, p3);
    parts.j1.position.set(p1[0], p1[1], p1[2]);
    parts.j2.position.set(p2[0], p2[1], p2[2]);
    parts.foot.position.set(p3[0], p3[1], p3[2]);
    parts.foot.material = leg.contact ? footMatOn : footMatOff;
  });

  updatePolygons(state);

  // Contacts UI.
  document.querySelectorAll("#contacts .c").forEach((el) => {
    const name = el.dataset.leg;
    el.classList.toggle("on", !!(state.legs[name] && state.legs[name].contact));
  });

  // Trail.
  const tarr = trailGeom.attributes.position.array;
  const idx = (trailCount % trailMax) * 3;
  tarr[idx] = pose.x; tarr[idx + 1] = pose.y; tarr[idx + 2] = 0;
  trailCount++;
  trailGeom.attributes.position.needsUpdate = true;
  trailGeom.setDrawRange(0, Math.min(trailCount, trailMax));
}
