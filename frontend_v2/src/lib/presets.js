const KEY = "hexapod.presets";

export function loadPresets() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || {};
  } catch {
    return {};
  }
}

export function savePresets(obj) {
  try {
    localStorage.setItem(KEY, JSON.stringify(obj));
  } catch {}
}
