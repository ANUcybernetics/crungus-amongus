// Meshes that have been 3D-printed, by their source image's key without the
// extension, e.g. "nvidia--sana-sprint-1-6b/crungus/9". Hand-kept and
// site-only: the pipeline knows nothing of prints, so this stays out of the
// models.json contract. The meshes page lights these and dims the rest.
// Keys index from 0, page anchors from 1: #crungus-80 is "…/crungus/79".
export const printed: ReadonlySet<string> = new Set<string>([
  "ai-forever--kandinsky-2/crungus/79",
  "black-forest-labs--flux-2-flex/crungus/79",
  "black-forest-labs--flux-dev/crungus/23",
  "bria--fibo/crungus/68",
  "prunaai--flux-fast/crungus/15",
  "prunaai--flux-fast/crungus/76",
]);

const extension = /\.[^./]+$/;

export const isPrinted = (imageKey: string): boolean =>
  printed.has(imageKey.replace(extension, ""));
