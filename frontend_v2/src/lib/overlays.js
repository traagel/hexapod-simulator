import { writable } from "svelte/store";
import { grid, axesHelper } from "./scene.js";
import { trailLine, polyMeshes } from "./hexapod.js";

export const overlays = writable({
  trail: true,
  polygons: true,
  axes: true,
  grid: true,
});

overlays.subscribe((o) => {
  grid.visible = o.grid;
  axesHelper.visible = o.axes;
  trailLine.visible = o.trail;
  for (const { mesh, edge } of polyMeshes) {
    mesh.visible = o.polygons;
    edge.visible = o.polygons;
  }
});
