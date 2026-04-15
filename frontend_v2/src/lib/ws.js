import { writable } from "svelte/store";

export const connected = writable(false);
export const latestState = writable(null);
export const cameraUrl = writable(null);

let _ws = null;
const _openListeners = [];

export function connect(host) {
  _ws = new WebSocket(`ws://${host}:8765`);
  _ws.onopen = () => {
    connected.set(true);
    _openListeners.forEach((fn) => fn());
  };
  _ws.onclose = () => connected.set(false);
  _ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "state") latestState.set(msg.data);
    else if (msg.type === "config" && msg.camera_url) {
      const url = new URL(msg.camera_url);
      url.hostname = location.hostname;
      cameraUrl.set(url.toString());
    }
  };
}

export function send(obj) {
  if (_ws && _ws.readyState === WebSocket.OPEN) {
    _ws.send(JSON.stringify(obj));
  }
}

export function onOpen(fn) {
  _openListeners.push(fn);
}
