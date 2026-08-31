/* oxlint-disable no-await-in-loop -- bounded worker pool: each worker
   deliberately awaits sequentially; parallelism comes from CONCURRENCY workers */
// Download every image key in models.json from the public bucket into
// src/assets/crungus/ (gitignored). Idempotent: existing files are kept, so
// this is cheap locally and CI-cacheable keyed on the models.json hash.
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { siteDataSchema } from "../src/lib/schema";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const assetsDir = join(root, "src", "assets", "crungus");
const CONCURRENCY = 16;

const raw = await readFile(join(root, "src", "data", "models.json"), "utf-8");
const data = siteDataSchema.parse(JSON.parse(raw));

const keys = data.models.flatMap((m) => m.prompts.flatMap((p) => p.images.map((i) => i.key)));

const pending: string[] = [];
for (const key of keys) {
  try {
    await stat(join(assetsDir, key));
  } catch {
    pending.push(key);
  }
}

console.log(`sync-images: ${keys.length} images, ${pending.length} to fetch`);

let fetched = 0;
async function worker(queue: string[]): Promise<void> {
  for (let key = queue.pop(); key !== undefined; key = queue.pop()) {
    const url = `${data.image_base_url}/${key}`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`${url}: HTTP ${response.status}`);
    }
    const target = join(assetsDir, key);
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, Buffer.from(await response.arrayBuffer()));
    fetched += 1;
    if (fetched % 100 === 0) console.log(`  ${fetched}/${pending.length}`);
  }
}

const queue = [...pending];
await Promise.all(Array.from({ length: Math.min(CONCURRENCY, queue.length) }, () => worker(queue)));
console.log(`sync-images: fetched ${fetched}`);
