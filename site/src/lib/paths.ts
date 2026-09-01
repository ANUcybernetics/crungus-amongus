// `import.meta.env.BASE_URL` is "/" at a domain root and "/prefix" under a
// subpath deploy. Stripping the trailing slash before joining keeps links from
// coming out as "//model/x", which a browser reads as protocol-relative and
// resolves against the host "model".
const prefix = import.meta.env.BASE_URL.replace(/\/+$/, "");

export function path(route = "/"): string {
  return `${prefix}${route.startsWith("/") ? route : `/${route}`}`;
}
