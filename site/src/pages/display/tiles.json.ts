import type { APIRoute } from "astro";

import { siteData } from "../../lib/data";
import { bucketUrl, imageSrcset } from "../../lib/images";
import { mosaicData } from "../../lib/mosaic";
import { itemPath } from "../../lib/permalink";

export const GET: APIRoute = () =>
  Response.json(
    mosaicData(siteData, (image) => ({
      srcset: imageSrcset(image),
      full: bucketUrl(image.key),
      page: itemPath(image.key),
    })),
  );
