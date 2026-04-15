<script>
  import { onMount } from "svelte";
  import Scene from "./components/Scene.svelte";
  import Panel from "./components/Panel.svelte";
  import Hud from "./components/Hud.svelte";
  import InfoBar from "./components/InfoBar.svelte";
  import Camera from "./components/Camera.svelte";
  import Help from "./components/Help.svelte";
  import EStop from "./components/EStop.svelte";
  import Minimap from "./components/Minimap.svelte";
  import Sparklines from "./components/Sparklines.svelte";
  import TouchControls from "./components/TouchControls.svelte";
  import { connect } from "./lib/ws.js";
  import { installInput } from "./lib/input.js";
  import { showMinimap, showSparklines, showTouchJoy } from "./lib/ui.js";
  // Imported for the side effect of registering overlay subscriptions +
  // gamepad connect/disconnect listeners.
  import "./lib/overlays.js";
  import "./lib/gamepad.js";
  import "./lib/metrics.js";

  onMount(() => {
    installInput();
    connect(location.hostname);
  });
</script>

<Scene />
<InfoBar />
<Hud />
<Panel />
<EStop />
<Camera />
<Help />

{#if $showMinimap}<Minimap />{/if}
{#if $showSparklines}<Sparklines />{/if}
{#if $showTouchJoy}<TouchControls />{/if}
