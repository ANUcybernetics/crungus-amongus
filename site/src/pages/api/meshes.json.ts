import type { APIRoute } from "astro";

import { apiBase, meshesIndex } from "../../lib/api";
import { siteData } from "../../lib/data";

export const GET: APIRoute = ({ site }) =>
  Response.json(meshesIndex(siteData, apiBase(siteData, site, import.meta.env.BASE_URL)));
