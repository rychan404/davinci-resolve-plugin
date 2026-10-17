import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

/** The default 24-hour TTL satisfies Pixabay terms. */
export const DAY_SECONDS = 86400;
export const SECRET_PARAMS = new Set(['key', 'api_key', 'apikey', 'token', 'access_token']);

export function makeKey(url: string, params: Record<string, string | number>): string {
  const safe: Record<string, string | number> = {};
  for (const name of Object.keys(params).sort()) {
    if (!SECRET_PARAMS.has(name.toLowerCase())) safe[name] = params[name];
  }
  return crypto.createHash('sha256').update(JSON.stringify([url, safe])).digest('hex');
}

/** One JSON file per key: a cache has no queries to run, so files are enough. */
export class ResponseCache {
  constructor(
    private readonly dir: string,
    private readonly ttlSeconds = DAY_SECONDS,
    private readonly now: () => number = () => Date.now() / 1000,
  ) {}

  get(key: string): string | null {
    try {
      const entry = JSON.parse(fs.readFileSync(path.join(this.dir, `${key}.json`), 'utf8'));
      if (typeof entry.value !== 'string' || this.now() - entry.stored_at > this.ttlSeconds) return null;
      return entry.value;
    } catch {
      return null;
    }
  }

  set(key: string, value: string): void {
    fs.mkdirSync(this.dir, { recursive: true });
    fs.writeFileSync(path.join(this.dir, `${key}.json`), JSON.stringify({ stored_at: this.now(), value }));
  }
}
