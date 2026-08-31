// The single data-binding point: parse models.json once through the schema.
import rawData from "../data/models.json";
import { siteDataSchema } from "./schema";

export const siteData = siteDataSchema.parse(rawData);
