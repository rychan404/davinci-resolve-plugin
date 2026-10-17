import { expect, test, vi } from 'vitest';
import { HttpStatusError, type Fetch } from '../src/main/http';
import { SupersededError, ThumbnailFetcher } from '../src/main/thumbnails';
import { fakeFetch } from './helpers';

function fakeClock() {
  let now = 0;
  const slept: number[] = [];
  return {
    slept,
    clock: () => now,
    sleep: async (s: number) => {
      slept.push(s);
      now += s;
    },
  };
}
const status = (code: number, headers: Record<string, string> = {}) => new Response(null, { status: code, headers });
const ok = () => new Response('ok');
const build = (responses: Response[], opts: ConstructorParameters<typeof ThumbnailFetcher>[0], calls: string[] = []) =>
  new ThumbnailFetcher({ fetchImpl: fakeFetch(calls, responses), ...opts });

test('retries after a 429', async () => {
  const c = fakeClock();
  const f = build([status(429, { 'Retry-After': '1' }), ok()], { ...c, minInterval: 0 });
  expect((await f.fetch('https://upload.example.org/a.jpg')).body.byteLength).toBeGreaterThan(0);
  expect(c.slept).toEqual([1]);
});

test('fails after exhausting attempts', async () => {
  const calls: string[] = [];
  const f = build(
    [status(429, { 'Retry-After': '1' }), status(429, { 'Retry-After': '1' }), status(429, { 'Retry-After': '1' })],
    { ...fakeClock(), minInterval: 0, maxAttempts: 3 },
    calls,
  );
  await expect(f.fetch('https://upload.example.org/a.jpg')).rejects.toBeInstanceOf(HttpStatusError);
  expect(calls).toHaveLength(3);
});

test('retries a 424 with a flat delay and does not widen host pacing', async () => {
  const c = fakeClock();
  const f = build([status(424), ok(), ok()], { ...c, minInterval: 0 });
  await f.fetch('https://upload.example.org/a.jpg');
  expect(c.slept).toEqual([1]);
  c.slept.length = 0;
  await f.fetch('https://upload.example.org/b.jpg');
  expect(c.slept).toEqual([]);
});

test('paces the same host and leaves other hosts alone', async () => {
  const c = fakeClock();
  const f = build([ok(), ok(), ok()], { ...c, minInterval: 0.5 });
  await f.fetch('https://upload.example.org/a.jpg');
  await f.fetch('https://cdn.example.net/b.jpg');
  expect(c.slept).toEqual([]);
  await f.fetch('https://upload.example.org/c.jpg');
  expect(c.slept).toEqual([0.5]);
});

test('a 429 backs off the whole host, then pace recovers', async () => {
  const c = fakeClock();
  const f = build([status(429, { 'Retry-After': '2' }), ...Array(7).fill(0).map(ok)], { ...c, minInterval: 0.2 });
  await f.fetch('https://upload.example.org/0.jpg');
  c.slept.length = 0;
  await f.fetch('https://upload.example.org/1.jpg');
  expect(c.slept).toEqual([2]);
  for (let i = 2; i < 6; i++) await f.fetch(`https://upload.example.org/${i}.jpg`);
  expect(f.intervalFor('upload.example.org')).toBeCloseTo(0.2, 1);
});

test('a superseded request makes no network call', async () => {
  const calls: string[] = [];
  const f = build([ok()], { ...fakeClock() }, calls);
  await expect(f.fetch('https://upload.example.org/a.jpg', () => false)).rejects.toBeInstanceOf(SupersededError);
  expect(calls).toEqual([]);
});

test('at most three requests are in flight', async () => {
  let inFlight = 0;
  let peak = 0;
  const release: (() => void)[] = [];
  const fetchImpl = (async () => {
    inFlight++;
    peak = Math.max(peak, inFlight);
    await new Promise<void>((r) => release.push(r));
    inFlight--;
    return new Response('x');
  }) as Fetch;
  const f = new ThumbnailFetcher({ fetchImpl, minInterval: 0, ...fakeClock() });
  const all = [1, 2, 3, 4].map((i) => f.fetch(`https://h${i}.example/x.jpg`));
  await vi.waitFor(() => expect(inFlight).toBe(3));
  while (release.length || inFlight) {
    release.shift()?.();
    await new Promise((r) => setTimeout(r));
  }
  await Promise.all(all);
  expect(peak).toBe(3);
});

test('returns the upstream content type', async () => {
  const f = build([new Response('<svg/>', { headers: { 'Content-Type': 'image/svg+xml' } })], {
    ...fakeClock(),
    minInterval: 0,
  });
  expect((await f.fetch('https://upload.example.org/a.svg')).contentType).toBe('image/svg+xml');
});
