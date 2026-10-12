import type { APIRoute, GetStaticPaths } from "astro";

import { apiBase, modelDetail } from "../../../lib/api";
import { siteData } from "../../../lib/data";
import { generatedModels } from "../../../lib/models";
import type { ModelEntry } from "../../../lib/schema";

export const getStaticPaths: GetStaticPaths = () =>
  generatedModels(siteData).map((model) => ({ params: { slug: model.slug }, props: { model } }));

export const GET: APIRoute<{ model: ModelEntry }> = ({ site, props }) =>
  Response.json(
    modelDetail(siteData, props.model, apiBase(siteData, site, import.meta.env.BASE_URL)),
  );
