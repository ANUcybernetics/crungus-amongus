// Corpus images come straight from the public bucket: the optimised image at
// its key, and beneath it the pipeline's thumbnails (models.json's
// thumb_template, at each of thumb_widths narrower than the image). The build
// fetches and transforms none of them.
import { siteData } from "./data";
import type { ImageRef } from "./schema";

const AVIF_SUFFIX = /\.avif$/;

const refs = new Map(
  siteData.models.flatMap((m) =>
    m.prompts.flatMap((p) => p.images.map((i) => [i.key, i] as const)),
  ),
);

/** The contract's entry for a corpus key. */
export function imageRef(key: string): ImageRef {
  const ref = refs.get(key);
  if (!ref) throw new Error(`no image ${key} in models.json`);
  return ref;
}

/** Full-resolution public URL on the bucket (lightbox target). */
export function bucketUrl(key: string): string {
  return `${siteData.image_base_url}/${key}`;
}

/** Every width the image is served at, thumbnails first, then the image itself. */
export function servedWidths(image: ImageRef): number[] {
  return [...siteData.thumb_widths.filter((w) => w < image.width), image.width];
}

/** The URL of the image at one of its servedWidths. */
export function imageUrl(image: ImageRef, width: number): string {
  if (width === image.width) return bucketUrl(image.key);
  const thumb = siteData.thumb_template
    .replace("{stem}", image.key.replace(AVIF_SUFFIX, ""))
    .replace("{width}", String(width));
  return bucketUrl(thumb);
}

/** A srcset over all its servedWidths, for the browser to choose from by `sizes`. */
export function imageSrcset(image: ImageRef): string {
  return servedWidths(image)
    .map((w) => `${imageUrl(image, w)} ${w}w`)
    .join(", ");
}
