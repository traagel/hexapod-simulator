/**
 * WebSocket connection — single send() function and event dispatch.
 */

let _ws = null;
let _onState = null;
let _onConfig = null;
let _onOpen = null;

export function connect(host) {
  _ws = new WebSocket(`ws://${host}:8765`);
  _ws.onopen = () => {
    document.getElementById("info").textContent = "connected";
    if (_onOpen) _onOpen();
  };
  _ws.onclose = () => {
    document.getElementById("info").textContent = "disconnected";
  };
  _ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "state" && _onState) _onState(msg.data);
    if (msg.type === "config" && _onConfig) _onConfig(msg);
  };
}

export function send(obj) {
  if (_ws && _ws.readyState === WebSocket.OPEN) _ws.send(JSON.stringify(obj));
}

export function onState(fn) { _onState = fn; }
export function onConfig(fn) { _onConfig = fn; }
export function onOpen(fn) { _onOpen = fn; }
