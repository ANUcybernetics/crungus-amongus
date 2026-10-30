import { defineConfig } from "astro/config";

import siteData from "./src/data/models.json" with { type: "json" };

export default defineConfig({
  // Astro 7's default ("jsx") drops the line break between wrapped prose and
  // an inline element, running words into links. `true` collapses it to a space.
  compressHTML: true,
  site: "https://crungusamong.us",
  output: "static",
  redirects: { "/radio": "/display/?radio" },
  image: {
    // the corpus is served from the bucket; the build fetches only the link
    // preview images (layouts/Base.astro) to make JPEGs of them
    domains: [new URL(siteData.image_base_url).hostname],
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
