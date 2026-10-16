// Loads <model-viewer> on demand: it brings three.js with it, so pages import
// this only when there is a mesh to show.
//
// The GLBs use meshopt compression, which model-viewer decodes only once
// meshoptDecoderLocation names a script to load. Point it at meshoptimizer's
// own UMD build, bundled here, rather than the default third-party CDN. The
// relative path is deliberate: the package exports that file to `require`
// alone, which a `?url` import can't resolve.
import decoderUrl from "../../node_modules/meshoptimizer/meshopt_decoder.cjs?url";

let ready: Promise<void> | undefined;

export function loadModelViewer(): Promise<void> {
  ready ??= import("@google/model-viewer").then(({ ModelViewerElement }) => {
    ModelViewerElement.meshoptDecoderLocation = decoderUrl;
  });
  return ready;
}

/** A configured <model-viewer> for one mesh, with its source image as poster. */
export function createModelViewer(src: string, poster: string, alt: string): HTMLElement {
  const viewer = document.createElement("model-viewer");
  viewer.setAttribute("src", src);
  viewer.setAttribute("poster", poster);
  viewer.setAttribute("alt", alt);
  viewer.setAttribute("camera-controls", "");
  // vertical swipes still scroll the page on touch screens
  viewer.setAttribute("touch-action", "pan-y");
  viewer.setAttribute("shadow-intensity", "1");
  return viewer;
}
