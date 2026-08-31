import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://anucybernetics.github.io",
  base: "/crungus-amongus",
  output: "static",
  vite: {
    css: { transformer: "lightningcss" },
    build: { cssMinify: "lightningcss" },
  },
});
