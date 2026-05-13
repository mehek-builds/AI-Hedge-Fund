/**
 * Server-side fetcher for Next.js Server Components.
 * Throws on non-OK responses so callers can catch and return fallback data.
 */
export async function fetcher<T>(path: string): Promise<T> {
  const base = process.env.FASTAPI_URL ?? "http://fastapi:8000";
  // Strip leading /api/v1 prefix because Next.js rewrites only apply client-side;
  // on the server we call the FastAPI backend directly.
  const strippedPath = path.replace(/^\/api/, "");
  const url = `${base}${strippedPath}`;

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`[fetcher] ${url} responded ${res.status}`);
  }
  return res.json() as Promise<T>;
}
