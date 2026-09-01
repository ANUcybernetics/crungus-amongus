import { describe, expect, it } from "vitest";

import { path } from "../src/lib/paths";

describe("path", () => {
  it("keeps the site root as /", () => {
    expect(path()).toBe("/");
  });

  it("joins routes without doubling the separator", () => {
    expect(path("/atlas/")).toBe("/atlas/");
    expect(path("model/minimax--image-01/")).toBe("/model/minimax--image-01/");
  });

  // "//model/x/" is protocol-relative: the browser resolves it against the
  // host "model", not the site root
  it("never emits a protocol-relative link", () => {
    for (const route of ["/", "/atlas/", "/about/", "/model/a--b/"]) {
      expect(path(route).startsWith("//")).toBe(false);
    }
  });
});
