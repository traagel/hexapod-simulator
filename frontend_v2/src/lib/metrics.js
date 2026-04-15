import { writable } from "svelte/store";
import { latestState } from "./ws.js";

export const msgRate = writable(0);

let count = 0;
let last = performance.now();

latestState.subscribe((s) => {
  if (!s) return;
  count++;
  const now = performance.now();
  if (now - last >= 1000) {
    msgRate.set(count);
    count = 0;
    last = now;
  }
});
