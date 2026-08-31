// Bridge between the data contract's image keys and the synced local assets.
//
// scripts/sync-images.ts downloads every image key in models.json from the
// public bucket into src/assets/crungus/ (gitignored), and this module hands
// them to astro:assets via import.meta.glob, so the build emits optimised
// derivatives. Full-size lightbox links go straight to the bucket URL.
import type { ImageMetadata } from "astro";

import { siteData } from "./data";

const assets = import.meta.glob<{ default: ImageMetadata }>("../assets/crungus/**/*.avif", {
  eager: true,
});

/** Local ImageMetadata for a contract key, or null if not yet synced. */
export function localImage(key: string): ImageMetadata | null {
  return assets[`../assets/crungus/${key}`]?.default ?? null;
}

/** Full-resolution public URL on the bucket (lightbox target). */
export function bucketUrl(key: string): string {
  return `${siteData.image_base_url}/${key}`;
}

export function syncedImageCount(): number {
  return Object.keys(assets).length;
}
