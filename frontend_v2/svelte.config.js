import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

export default {
  preprocess: vitePreprocess(),
  compilerOptions: {
    warningFilter: (w) =>
      w.code !== "a11y_label_has_associated_control" &&
      w.code !== "a11y_no_static_element_interactions",
  },
};
