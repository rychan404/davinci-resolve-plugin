import { STATUS_CODES } from 'node:http';
import { ResponseCache, makeKey } from './cache';

// Wikimedia rejects contactless agents with a 429 robot-policy error, so the
// project URL has to travel with every request.
export const HOMEPAGE = 'https://github.com/rychan404/davinci-resolve-plugin';
export const USER_AGENT = `resolvestock/0.1 (${HOMEPAGE}) electron`;

export const MAX_RETRY_WAIT = 5;

export type Fetch = typeof fetch;
export type Sleep = (seconds: number) => Promise<void>;
export const realSleep: Sleep = (seconds) => new Promise((resolve) => setTimeout(resolve, seconds * 1000));

/** Names the host only: the query string can carry an API key. */
export class HttpStatusError extends Error {
  constructor(
    readonly status: number,
    statusText: string,
    url: string,
  ) {
    super(`${status} ${statusText || STATUS_CODES[status] || ''} from ${new URL(url).host}`.replace(/ +/g, ' '));
    this.name = 'HttpStatusError';
  }
}

/** Seconds to wait before retrying, or null when the wait is too long. */
export function retryWait(headers: Headers): number | null {
  // Pixabay reports its window reset in X-RateLimit-Reset, not Retry-After.
  const header = headers.get('Retry-After') || headers.get('X-RateLimit-Reset') || '1';
  const parsed = Number(header);
  const seconds = Number.isNaN(parsed) ? 1 : Math.max(parsed, 0.1);
  return seconds <= MAX_RETRY_WAIT ? seconds : null;
}

export interface JsonGetter {
  getJson(url: string, params: Record<string, string | number>): Promise<any>;
}

export class CachedHttp implements JsonGetter {
  constructor(
    private readonly cache: ResponseCache,
    private readonly fetchImpl: Fetch = fetch,
    private readonly sleep: Sleep = realSleep,
  ) {}

  async getJson(url: string, params: Record<string, string | number>): Promise<any> {
    const key = makeKey(url, params);
    const cached = this.cache.get(key);
    if (cached !== null) return JSON.parse(cached);

    const full = `${url}?${new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))}`;
    const get = () =>
      this.fetchImpl(full, { headers: { 'User-Agent': USER_AGENT }, signal: AbortSignal.timeout(15000) });
    let response = await get();
    if (response.status === 429) {
      const wait = retryWait(response.headers);
      if (wait !== null) {
        await this.sleep(wait);
        response = await get();
      }
    }
    if (!response.ok) throw new HttpStatusError(response.status, response.statusText, url);
    const text = await response.text();
    this.cache.set(key, text);
    return JSON.parse(text);
  }
}
