import type { APIRoute } from "astro";

import { apiBase, videosIndex } from "../../lib/api";
import { siteData } from "../../lib/data";

export const GET: APIRoute = ({ site }) =>
  Response.json(videosIndex(siteData, apiBase(siteData, site, import.meta.env.BASE_URL)));
