import type { APIRoute } from "astro";

import { apiBase, audioIndex } from "../../lib/api";
import { siteData } from "../../lib/data";

export const GET: APIRoute = ({ site }) =>
  Response.json(audioIndex(siteData, apiBase(siteData, site, import.meta.env.BASE_URL)));
