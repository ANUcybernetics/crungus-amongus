import { defineConfig } from "astro/config";

export default defineConfig({
  // Astro 7's default ("jsx") drops the line break between wrapped prose and
  // an inline element, running words into links. `true` collapses it to a space.
  compressHTML: true,
  site: "https://crungusamong.us",
  output: "static",
  vite: {
    css: { transformer: "lightningcss" },
    build: { cssMinify: "lightningcss" },
  },
});
