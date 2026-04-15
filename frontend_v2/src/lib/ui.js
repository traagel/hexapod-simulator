/**
 * Shared UI toggles. Kept in a module so Panel and App can both drive them
 * without a parent/child plumbing relationship.
 */
import { writable } from "svelte/store";
import { loadSettings, saveSettings } from "./persist.js";

const saved = loadSettings();

function persisted(key, init) {
  const s = writable(saved[key] !== undefined ? saved[key] : init);
  s.subscribe((v) => {
    const cur = loadSettings();
    cur[key] = v;
    saveSettings(cur);
  });
  return s;
}

export const showMinimap     = persisted("showMinimap", false);
export const showSparklines  = persisted("showSparklines", true);
export const showTouchJoy    = persisted("showTouchJoy", false);
export const showServoGraphs = persisted("showServoGraphs", false);
