import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://crungusamong.us",
  output: "static",
  vite: {
    css: { transformer: "lightningcss" },
    build: { cssMinify: "lightningcss" },
  },
});
