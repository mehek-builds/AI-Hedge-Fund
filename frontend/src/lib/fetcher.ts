const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window === "undefined"
    ? process.env.FASTAPI_URL ?? "http://fastapi:8000"
    : "");

export async function fetcher<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} — ${res.statusText} (${url})`);
  }
  return res.json() as Promise<T>;
}
