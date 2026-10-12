import type { APIRoute } from "astro";

import { apiBase, modelsIndex } from "../../lib/api";
import { siteData } from "../../lib/data";

export const GET: APIRoute = ({ site }) =>
  Response.json(modelsIndex(siteData, apiBase(siteData, site, import.meta.env.BASE_URL)));
