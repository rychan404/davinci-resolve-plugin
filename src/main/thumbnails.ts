import { HttpStatusError, USER_AGENT, realSleep, type Fetch, type Sleep } from './http';

export const ACCEPT = 'image/avif,image/webp,image/png,image/jpeg,image/svg+xml,*/*';
export const MAX_IN_FLIGHT = 3;
export const MIN_HOST_INTERVAL = 0.2;
export const RELAX_FACTOR = 0.7;
export const MAX_ATTEMPTS = 6;
export const MAX_BACKOFF = 8;

export class SupersededError extends Error {
  constructor() {
    super('superseded by a newer search');
    this.name = 'SupersededError';
  }
}

interface HostState {
  ready: number | null;
  interval: number;
}

/**
 * Fetch previews at a pace the image CDNs tolerate.
 *
 * A search asks for dozens of thumbnails at once, and Commons' CDN answers a
 * burst like that with 429 and a Retry-After of a second or two. Spacing
 * requests per host and retrying on 429 turns a transient throttle back into a
 * visible thumbnail instead of a permanently empty tile. The spacing widens
 * whenever a host pushes back and relaxes again once it stops.
 *
 * Commons also answers occasional single files with 424 (Failed Dependency)
 * when its own thumbnail render failed, unrelated to rate limiting. That gets a
 * plain retry with a short flat delay, without widening the host's pacing.
 */
export class ThumbnailFetcher {
  private readonly fetchImpl: Fetch;
  private readonly sleep: Sleep;
  private readonly clock: () => number;
  private readonly maxAttempts: number;
  private readonly minInterval: number;
  private readonly maxBackoff: number;
  private readonly hosts = new Map<string, HostState>();
  private inFlight = 0;
  private readonly waiting: (() => void)[] = [];

  constructor(
    opts: {
      fetchImpl?: Fetch;
      sleep?: Sleep;
      clock?: () => number;
      maxAttempts?: number;
      minInterval?: number;
      maxBackoff?: number;
    } = {},
  ) {
    this.fetchImpl = opts.fetchImpl ?? fetch;
    this.sleep = opts.sleep ?? realSleep;
    this.clock = opts.clock ?? (() => performance.now() / 1000);
    this.maxAttempts = opts.maxAttempts ?? MAX_ATTEMPTS;
    this.minInterval = opts.minInterval ?? MIN_HOST_INTERVAL;
    this.maxBackoff = opts.maxBackoff ?? MAX_BACKOFF;
  }

  async fetch(
    url: string,
    isCurrent: () => boolean = () => true,
  ): Promise<{ body: ArrayBuffer; contentType: string }> {
    const host = new URL(url).host;
    await this.acquire();
    try {
      for (let attempt = 1; attempt <= this.maxAttempts; attempt++) {
        if (!isCurrent()) throw new SupersededError();
        await this.waitForTurn(host);
        if (!isCurrent()) throw new SupersededError();
        const response = await this.fetchImpl(url, {
          headers: { 'User-Agent': USER_AGENT, Accept: ACCEPT },
          signal: AbortSignal.timeout(15000),
        });
        if (response.status !== 429 && response.status !== 424) {
          if (!response.ok) throw new HttpStatusError(response.status, response.statusText, url);
          this.relax(host);
          return {
            body: await response.arrayBuffer(),
            contentType: response.headers.get('Content-Type') ?? 'application/octet-stream',
          };
        }
        if (attempt === this.maxAttempts) throw new HttpStatusError(response.status, response.statusText, url);
        const wait = this.retryAfter(response.headers);
        if (response.status === 429) this.throttle(host, wait);
        else await this.sleep(wait);
      }
    } finally {
      this.release();
    }
    throw new Error('unreachable');
  }

  intervalFor(host: string): number {
    return this.state(host).interval;
  }

  private async acquire(): Promise<void> {
    if (this.inFlight < MAX_IN_FLIGHT) {
      this.inFlight++;
      return;
    }
    // The releasing request hands its slot straight to us, so inFlight stays put.
    await new Promise<void>((resolve) => this.waiting.push(resolve));
  }

  private release(): void {
    const next = this.waiting.shift();
    if (next) next();
    else this.inFlight--;
  }

  private state(host: string): HostState {
    let s = this.hosts.get(host);
    if (!s) this.hosts.set(host, (s = { ready: null, interval: this.minInterval }));
    return s;
  }

  private async waitForTurn(host: string): Promise<void> {
    const state = this.state(host);
    const now = this.clock();
    const ready = state.ready ?? now;
    state.ready = Math.max(ready, now) + state.interval;
    const delay = ready - now;
    if (delay > 0) await this.sleep(delay);
  }

  private throttle(host: string, seconds: number): void {
    const state = this.state(host);
    const now = this.clock();
    // Retry-After understates how long these CDNs stay annoyed, so widen the
    // spacing geometrically until the host stops pushing back.
    state.interval = Math.min(this.maxBackoff, Math.max(state.interval * 2, seconds));
    state.ready = Math.max(state.ready ?? now, now + seconds);
  }

  private relax(host: string): void {
    const state = this.state(host);
    // Ease off geometrically. Halving oscillated straight back into the limit.
    state.interval = Math.max(this.minInterval, state.interval * RELAX_FACTOR);
  }

  private retryAfter(headers: Headers): number {
    const parsed = Number(headers.get('Retry-After') || NaN);
    const seconds = Number.isNaN(parsed) ? 1 : parsed;
    return Math.min(this.maxBackoff, Math.max(seconds, 0.1));
  }
}
