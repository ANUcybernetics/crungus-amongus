// One address per archive item: its model page, with an anchor that scrolls to
// a clip or opens an image (and its mesh) in the lightbox. Keys are
// "<model-slug>/<prompt-slug>/<index>.<ext>" with the index from 0; anchors
// number from 1, as the pages do.
import { path } from "./paths";

function parts(key: string): { model: string; prompt: string; index: number } {
  const [model, prompt, file] = key.split("/");
  const index = Number.parseInt(file ?? "", 10);
  if (!model || !prompt || Number.isNaN(index)) throw new Error(`not an item key: ${key}`);
  return { model, prompt, index };
}

/** The item's number within its prompt, from 1. */
export function itemNumber(key: string): number {
  return parts(key).index + 1;
}

/** The element id on the model page, e.g. "crungus-7". */
export function itemAnchor(key: string): string {
  const { prompt, index } = parts(key);
  return `${prompt}-${index + 1}`;
}

/** The item's address relative to the site root, for resolving against a base URL. */
export function itemRoute(key: string): string {
  return `model/${parts(key).model}/#${itemAnchor(key)}`;
}

/** The item's address on this site. */
export function itemPath(key: string): string {
  return path(`/${itemRoute(key)}`);
}
