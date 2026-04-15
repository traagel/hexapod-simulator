<script>
  import { onMount } from "svelte";
  import { send, onOpen, latestState } from "../lib/ws.js";
  import { setChaseActive } from "../lib/chase.js";
  import {
    enterFPV, exitFPV, fpvActive, fpvSens, speed, deadMan,
  } from "../lib/input.js";
  import { loadSettings, saveSettings } from "../lib/persist.js";
  import { loadPresets, savePresets } from "../lib/presets.js";
  import { overlays } from "../lib/overlays.js";
  import { applyCameraPreset } from "../lib/cameras.js";
  import { takeScreenshot } from "../lib/screenshot.js";
  import { startGyro, stopGyro } from "../lib/gyro.js";
  import { gamepadConnected } from "../lib/gamepad.js";
  import { showMinimap, showSparklines, showServoGraphs, showTouchJoy } from "../lib/ui.js";

  const LEG_OPTIONS = [
    { value: "", label: "-- off --" },
    { value: "front_left", label: "FL" },
    { value: "front_right", label: "FR" },
    { value: "mid_left", label: "ML" },
    { value: "mid_right", label: "MR" },
    { value: "rear_left", label: "RL" },
    { value: "rear_right", label: "RR" },
  ];

  const LEG_PILLS = [
    ["front_left", "FL"], ["front_right", "FR"],
    ["mid_left",   "ML"], ["mid_right",   "MR"],
    ["rear_left",  "RL"], ["rear_right",  "RR"],
  ];

  const saved = loadSettings();
  const or = (k, d) => (saved[k] !== undefined ? saved[k] : d);

  // Body + gait.
  let height   = $state(or("height", 12));
  let radius   = $state(or("radius", 14));
  let step     = $state(or("step", 10));
  let lift     = $state(or("lift", 3));
  let cycle    = $state(or("cycle", 0.6));
  let speedVal = $state(or("speedVal", 15));

  // Foot target.
  let targetLeg = $state("");
  let tx = $state(17);
  let ty = $state(12);
  let tz = $state(0);

  // Hardware state.
  let servosOn = $state(false);
  let zeroOn = $state(false);
  let lowPower = $state(false);
  let chaseOn = $state(false);

  // FPV sensitivity.
  let sensYaw   = $state(or("sensYaw", 5));
  let sensPitch = $state(or("sensPitch", 4));
  let sensRoll  = $state(or("sensRoll", 6));

  let gyroOn    = $state(false);
  let deadManOn = $state(or("deadManOn", false));

  // Presets.
  let presets = $state(loadPresets());
  let presetName = $state("");

  // Broadcast everything once the socket opens.
  function pushAll() {
    send({ type: "set_height",        z: height });
    send({ type: "set_stance_radius", radius });
    send({ type: "set_step_length",   length: step });
    send({ type: "set_lift_height",   height: lift });
    send({ type: "set_cycle_time",    seconds: cycle });
  }
  onOpen(pushAll);

  // Individual slider effects — fire on change (and once on mount; the
  // initial firing is a no-op because the socket isn't open yet).
  $effect(() => { send({ type: "set_height",        z: height }); });
  $effect(() => { send({ type: "set_stance_radius", radius }); });
  $effect(() => { send({ type: "set_step_length",   length: step }); });
  $effect(() => { send({ type: "set_lift_height",   height: lift }); });
  $effect(() => { send({ type: "set_cycle_time",    seconds: cycle }); });

  $effect(() => { speed.set(speedVal); });
  $effect(() => {
    fpvSens.set({ yaw: sensYaw, pitch: sensPitch, roll: sensRoll });
  });
  $effect(() => { deadMan.set(deadManOn); });

  // Persist all tracked settings (view toggles are persisted by ui.js).
  $effect(() => {
    const cur = loadSettings();
    saveSettings({
      ...cur,
      height, radius, step, lift, cycle, speedVal,
      sensYaw, sensPitch, sensRoll,
      deadManOn,
    });
  });

  // Low-battery safety: auto-disable servos.
  $effect(() => {
    const s = $latestState;
    if (s?.low_battery && servosOn) {
      servosOn = false;
      send({ type: "set_servos", enabled: false });
    }
  });

  function toggleServos() {
    servosOn = !servosOn;
    send({ type: "set_servos", enabled: servosOn });
  }
  function toggleZero() {
    zeroOn = !zeroOn;
    send({ type: "zero_stance", enabled: zeroOn });
  }
  function toggleLowPower() {
    lowPower = !lowPower;
    if (lowPower) {
      speedVal = Math.max(1, Math.round(speedVal / 2));
      cycle = Math.min(4, Number((cycle * 2).toFixed(1)));
    }
  }
  function toggleFPV() {
    if ($fpvActive) exitFPV();
    else enterFPV();
  }
  function toggleChase() {
    chaseOn = !chaseOn;
    setChaseActive(chaseOn);
  }
  async function toggleGyro() {
    if (gyroOn) {
      stopGyro();
      gyroOn = false;
    } else {
      gyroOn = await startGyro();
    }
  }

  // Foot target.
  let footTimer = null;
  function pushFootTarget() {
    if (!targetLeg) return;
    send({ type: "set_foot_target", leg: targetLeg, x: tx, y: ty, z: tz });
  }
  $effect(() => {
    if (footTimer) clearInterval(footTimer);
    footTimer = null;
    if (targetLeg) {
      const foot = $latestState?.legs?.[targetLeg]?.foot;
      if (foot) {
        tx = clampRange(snap(foot[0]), -25, 30);
        ty = clampRange(snap(foot[1]), -25, 25);
        tz = clampRange(snap(foot[2]), -10, 20);
      }
      pushFootTarget();
      footTimer = setInterval(pushFootTarget, 33);
    }
    return () => {
      if (footTimer) clearInterval(footTimer);
      footTimer = null;
    };
  });

  function snap(v) { return Math.round(v * 2) / 2; }
  function clampRange(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  let contacts = $derived($latestState?.legs || {});

  // Overlay toggles (two-way).
  let ov = $state({ ...$overlays });
  $effect(() => { overlays.set(ov); });

  // Presets.
  function savePreset() {
    const name = presetName.trim();
    if (!name) return;
    const snap = {
      height, radius, step, lift, cycle, speedVal,
      sensYaw, sensPitch, sensRoll,
    };
    presets = { ...presets, [name]: snap };
    savePresets(presets);
    presetName = "";
  }
  function applyPreset(name) {
    const p = presets[name];
    if (!p) return;
    height = p.height; radius = p.radius; step = p.step;
    lift = p.lift; cycle = p.cycle; speedVal = p.speedVal;
    sensYaw = p.sensYaw; sensPitch = p.sensPitch; sensRoll = p.sensRoll;
  }
  function deletePreset(name) {
    const { [name]: _, ...rest } = presets;
    presets = rest;
    savePresets(presets);
  }
</script>

<div class="panel">
  <div class="section">body</div>
  <label>height</label>
  <input type="range" min="2" max="18" step="0.5" bind:value={height} />
  <span class="v">{height}</span>

  <label>radius</label>
  <input type="range" min="6" max="24" step="0.5" bind:value={radius} />
  <span class="v">{radius}</span>

  <div class="section">gait</div>
  <label>step</label>
  <input type="range" min="0.5" max="200" step="0.5" bind:value={step} />
  <span class="v">{step}</span>

  <label>lift</label>
  <input type="range" min="0.5" max="15" step="0.5" bind:value={lift} />
  <span class="v">{lift}</span>

  <label>cycle</label>
  <input type="range" min="0.2" max="4" step="0.1" bind:value={cycle} />
  <span class="v">{cycle}</span>

  <label>speed</label>
  <input type="range" min="1" max="30" step="1" bind:value={speedVal} />
  <span class="v">{speedVal}</span>

  <div class="section">foot override</div>
  <label>leg</label>
  <select bind:value={targetLeg} class="leg-select">
    {#each LEG_OPTIONS as o}
      <option value={o.value}>{o.label}</option>
    {/each}
  </select>
  <span></span>

  <label>x</label>
  <input type="range" min="-25" max="30" step="0.5" bind:value={tx} />
  <span class="v">{tx}</span>

  <label>y</label>
  <input type="range" min="-25" max="25" step="0.5" bind:value={ty} />
  <span class="v">{ty}</span>

  <label>z</label>
  <input type="range" min="-10" max="20" step="0.5" bind:value={tz} />
  <span class="v">{tz}</span>

  <div class="section">hardware</div>
  <div class="btn-row">
    <button class="servo" class:on={servosOn} onclick={toggleServos}>
      {servosOn ? "ON" : "OFF"}
    </button>
    <button class:on={zeroOn} onclick={toggleZero}>ZERO</button>
    <button class:lp={lowPower} onclick={toggleLowPower}>LP</button>
    <button class:on={$fpvActive} onclick={toggleFPV}>FPV</button>
    <button class:on={chaseOn} onclick={toggleChase}>3RD</button>
  </div>

  <div class="section">fpv sensitivity</div>
  <label>yaw</label>
  <input type="range" min="1" max="100" step="1" bind:value={sensYaw} />
  <span class="v">{sensYaw}</span>

  <label>pitch</label>
  <input type="range" min="1" max="20" step="1" bind:value={sensPitch} />
  <span class="v">{sensPitch}</span>

  <label>roll</label>
  <input type="range" min="1" max="20" step="1" bind:value={sensRoll} />
  <span class="v">{sensRoll}</span>

  <div class="section">view</div>
  <div class="btn-row">
    <button onclick={() => applyCameraPreset("iso")}>ISO</button>
    <button onclick={() => applyCameraPreset("top")}>TOP</button>
    <button onclick={() => applyCameraPreset("side")}>SIDE</button>
    <button onclick={() => applyCameraPreset("front")}>FRNT</button>
    <button onclick={takeScreenshot} title="Save PNG">PNG</button>
  </div>
  <div class="checks">
    <label class="chk"><input type="checkbox" bind:checked={ov.grid}/>grid</label>
    <label class="chk"><input type="checkbox" bind:checked={ov.axes}/>axes</label>
    <label class="chk"><input type="checkbox" bind:checked={ov.trail}/>trail</label>
    <label class="chk"><input type="checkbox" bind:checked={ov.polygons}/>polys</label>
    <label class="chk"><input type="checkbox" bind:checked={$showMinimap}/>minimap</label>
    <label class="chk"><input type="checkbox" bind:checked={$showSparklines}/>plots</label>
    <label class="chk"><input type="checkbox" bind:checked={$showServoGraphs}/>servos</label>
  </div>

  <div class="section">input</div>
  <div class="checks">
    <label class="chk"><input type="checkbox" bind:checked={deadManOn}/>dead-man (hold `)</label>
    <label class="chk"><input type="checkbox" bind:checked={$showTouchJoy}/>touch joysticks</label>
    <label class="chk">
      <input type="checkbox" checked={gyroOn} onchange={toggleGyro}/>phone gyro
    </label>
    <span class="gp-indicator" class:on={$gamepadConnected}>
      🎮 {$gamepadConnected ? "gamepad" : "no gamepad"}
    </span>
  </div>

  <div class="section">presets</div>
  <div class="preset-row">
    <input
      class="preset-input"
      type="text"
      placeholder="preset name"
      bind:value={presetName}
    />
    <button onclick={savePreset}>SAVE</button>
  </div>
  <div class="preset-list">
    {#each Object.keys(presets) as name}
      <span class="preset-chip">
        <button class="apply" onclick={() => applyPreset(name)}>{name}</button>
        <button class="del" onclick={() => deletePreset(name)} title="delete">×</button>
      </span>
    {/each}
  </div>

  <div class="section">contacts</div>
  <div class="contacts">
    {#each LEG_PILLS as [key, label]}
      <span class="c" class:on={contacts[key]?.contact}>{label}</span>
    {/each}
  </div>
</div>

<style>
  .panel {
    position: absolute;
    top: 8px;
    right: 8px;
    padding: 12px 14px;
    background: rgba(0, 0, 0, 0.65);
    border-radius: 8px;
    font-size: 12px;
    display: grid;
    grid-template-columns: auto 160px auto;
    gap: 6px 10px;
    align-items: center;
    backdrop-filter: blur(4px);
    max-height: calc(100vh - 16px);
    overflow-y: auto;
    color: #ddd;
    z-index: 6;
  }
  .panel input[type="range"] {
    width: 160px;
    accent-color: #4af;
  }
  .v {
    font-variant-numeric: tabular-nums;
    min-width: 32px;
    text-align: right;
    font-family: monospace;
    opacity: 0.7;
  }
  label {
    opacity: 0.8;
    font-size: 11px;
  }
  .section {
    grid-column: span 3;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #888;
    margin: 4px 0 2px;
    border-bottom: 1px solid #333;
    padding-bottom: 4px;
  }
  button {
    padding: 5px 8px;
    border: 1px solid #444;
    border-radius: 4px;
    background: #222;
    cursor: pointer;
    font: 11px monospace;
    color: #ddd;
    transition: all 0.15s;
  }
  button:hover {
    background: #333;
    border-color: #666;
  }
  .btn-row {
    display: flex;
    gap: 6px;
    grid-column: span 3;
  }
  .btn-row button {
    flex: 1;
  }
  .servo { color: #f44; }
  .servo.on { color: #4f4; }
  button.on:not(.servo) { color: #4f4; }
  button.lp { color: #ff0; }
  .leg-select {
    display: block;
    width: 100%;
    background: #222;
    color: #ddd;
    border: 1px solid #444;
    border-radius: 3px;
    padding: 3px;
    font: 11px monospace;
  }
  .contacts {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    font: 11px monospace;
    grid-column: span 3;
  }
  .c {
    padding: 3px 7px;
    border-radius: 4px;
    background: #1a1a1a;
    color: #666;
    border: 1px solid #333;
    font-weight: bold;
    transition: all 0.15s;
  }
  .c.on {
    background: #0a3a0a;
    color: #4f4;
    border-color: #4f4;
    box-shadow: 0 0 6px rgba(68, 255, 102, 0.3);
  }
  .checks {
    grid-column: span 3;
    display: flex;
    flex-wrap: wrap;
    gap: 4px 10px;
    font-size: 11px;
  }
  .chk {
    display: flex;
    align-items: center;
    gap: 4px;
    opacity: 0.85;
    cursor: pointer;
  }
  .chk input {
    accent-color: #4af;
  }
  .gp-indicator {
    font: 11px monospace;
    color: #666;
    padding: 2px 6px;
    border-radius: 3px;
    background: #1a1a1a;
    border: 1px solid #333;
  }
  .gp-indicator.on {
    color: #4f4;
    border-color: #4f4;
  }
  .preset-row {
    grid-column: span 3;
    display: flex;
    gap: 6px;
  }
  .preset-input {
    flex: 1;
    background: #222;
    color: #ddd;
    border: 1px solid #444;
    border-radius: 3px;
    padding: 4px 6px;
    font: 11px monospace;
  }
  .preset-list {
    grid-column: span 3;
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
  }
  .preset-chip {
    display: inline-flex;
    border: 1px solid #444;
    border-radius: 3px;
    overflow: hidden;
  }
  .preset-chip .apply {
    border: 0;
    border-radius: 0;
    padding: 3px 8px;
    background: #1a1a1a;
  }
  .preset-chip .del {
    border: 0;
    border-left: 1px solid #444;
    border-radius: 0;
    padding: 3px 6px;
    color: #f66;
    background: #1a1a1a;
  }
</style>
