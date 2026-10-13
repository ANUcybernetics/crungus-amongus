import type { APIRoute } from "astro";
import { getImage } from "astro:assets";

import { siteData } from "../../lib/data";
import { localImage } from "../../lib/images";
import { generatedModels } from "../../lib/models";
import { mosaicData } from "../../lib/mosaic";

// the same transform the model pages ask for, so the wall reuses their
// derivatives instead of adding its own
const WIDTHS = [240, 480];

async function thumbUrl(key: string): Promise<string | null> {
  const src = localImage(key);
  if (!src) return null;
  const image = await getImage({ src, format: "avif", widths: WIDTHS });
  return image.srcSet.values[0]?.url ?? image.src;
}

export const GET: APIRoute = async () => {
  const keys = generatedModels(siteData, "image").flatMap((m) =>
    m.prompts.flatMap((p) => p.images.map((i) => i.key)),
  );
  const thumbs = new Map(
    await Promise.all(keys.map(async (key) => [key, await thumbUrl(key)] as const)),
  );
  return Response.json(mosaicData(siteData, (key) => thumbs.get(key) ?? null));
};
