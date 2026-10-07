const API_BASE = "/api";

export interface URLEntry {
  short_code: string;
  short_url: string;
  original_url: string;
  created_at: string;
  expires_at: string | null;
  click_count: number;
}

export interface URLStats {
  short_code: string;
  original_url: string;
  created_at: string;
  click_count: number;
  recent_clicks: { clicked_at: string; referrer: string | null; user_agent: string | null }[];
}

/**
 * Safely parse a JSON response body.
 * Returns null if the body is empty or not valid JSON.
 */
async function safeJson<T = unknown>(res: Response): Promise<T | null> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

/**
 * Handle a non-OK response by extracting the error detail.
 * Throws a descriptive Error regardless of whether the body is JSON.
 */
async function handleError(res: Response, fallbackMsg: string): never {
  const body = await safeJson<{ detail?: string }>(res);
  const detail = body?.detail || `${fallbackMsg} (HTTP ${res.status})`;
  throw new Error(detail);
}

export async function shortenUrl(url: string, customAlias?: string): Promise<URLEntry> {
  const body: Record<string, string> = { url };
  if (customAlias) body.custom_alias = customAlias;

  const res = await fetch(`${API_BASE}/shorten`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    await handleError(res, "Failed to shorten URL");
  }
  const data = await safeJson<URLEntry>(res);
  if (!data) throw new Error("Empty response from server");
  return data;
}

export async function listUrls(skip = 0, limit = 50): Promise<URLEntry[]> {
  const res = await fetch(`${API_BASE}/urls?skip=${skip}&limit=${limit}`);
  if (!res.ok) await handleError(res, "Failed to fetch URLs");
  return (await safeJson<URLEntry[]>(res)) ?? [];
}

export async function getUrlStats(shortCode: string): Promise<URLStats> {
  const res = await fetch(`${API_BASE}/urls/${shortCode}/stats`);
  if (!res.ok) await handleError(res, "Failed to fetch stats");
  const data = await safeJson<URLStats>(res);
  if (!data) throw new Error("Empty response from server");
  return data;
}

export async function deleteUrl(shortCode: string): Promise<void> {
  const res = await fetch(`${API_BASE}/urls/${shortCode}`, { method: "DELETE" });
  if (!res.ok) await handleError(res, "Failed to delete URL");
  // 204 No Content — no body to parse
}
