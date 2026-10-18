import type { APIRoute } from "astro";
import { getImage } from "astro:assets";

import { siteData } from "../../lib/data";
import { bucketUrl, localImage } from "../../lib/images";
import { generatedModels } from "../../lib/models";
import { mosaicData } from "../../lib/mosaic";
import type { MosaicImage } from "../../lib/mosaic";

// the same transform the model pages ask for, so the wall reuses their
// derivatives instead of adding its own
const WIDTHS = [240, 480];

async function mosaicImage(key: string): Promise<MosaicImage | null> {
  const src = localImage(key);
  if (!src) return null;
  const image = await getImage({ src, format: "avif", widths: WIDTHS });
  return { srcset: image.srcSet.attribute, full: bucketUrl(key) };
}

export const GET: APIRoute = async () => {
  const keys = generatedModels(siteData, "image").flatMap((m) =>
    m.prompts.flatMap((p) => p.images.map((i) => i.key)),
  );
  const images = new Map(
    await Promise.all(keys.map(async (key) => [key, await mosaicImage(key)] as const)),
  );
  return Response.json(mosaicData(siteData, (key) => images.get(key) ?? null));
};
