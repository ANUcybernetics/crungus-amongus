import type { APIRoute } from "astro";

import { apiBase, imagesIndex } from "../../lib/api";
import { siteData } from "../../lib/data";

export const GET: APIRoute = ({ site }) =>
  Response.json(imagesIndex(siteData, apiBase(siteData, site, import.meta.env.BASE_URL)));
