import { defineConfig } from "astro/config";

export default defineConfig({
  // Astro 7's default ("jsx") drops the line break between wrapped prose and
  // an inline element, running words into links. `true` collapses it to a space.
  compressHTML: true,
  site: "https://crungusamong.us",
  output: "static",
  redirects: { "/radio": "/display/?radio" },
  image: {
    service: {
      entrypoint: "astro/assets/services/sharp",
      // sharp's default effort (4) takes ~5x longer for files ~2% smaller
      config: { avif: { effort: 2 } },
    },
  },
  vite: {
    css: { transformer: "lightningcss" },
    build: { cssMinify: "lightningcss" },
  },
});
