import { expect, test } from 'vitest';
import { ResponseCache, makeKey } from '../src/main/cache';
import { CachedHttp, HttpStatusError, USER_AGENT } from '../src/main/http';
import { fakeFetch, json, tmpDir } from './helpers';

test('cache keys ignore secret params', () => {
  expect(makeKey('https://api.example/x', { key: 'secret', q: 'x' })).toBe(
    makeKey('https://api.example/x', { q: 'x' }),
  );
});

test('cache round-trips and expires after the TTL', () => {
  let now = 1000;
  const cache = new ResponseCache(tmpDir(), 60, () => now);
  cache.set('k', 'v');
  expect(cache.get('k')).toBe('v');
  now += 61;
  expect(cache.get('k')).toBeNull();
});

test('a successful request is served from cache the second time', async () => {
  const calls: string[] = [];
  const http = new CachedHttp(new ResponseCache(tmpDir()), fakeFetch(calls, [json(200, { ok: true })]));
  expect(await http.getJson('https://api.example/x', { q: 'x' })).toEqual({ ok: true });
  expect(await http.getJson('https://api.example/x', { q: 'x' })).toEqual({ ok: true });
  expect(calls).toHaveLength(1);
});

test('retries once after a short 429', async () => {
  const waits: number[] = [];
  const http = new CachedHttp(
    new ResponseCache(tmpDir()),
    fakeFetch([], [json(429, {}, { 'X-RateLimit-Reset': '2' }), json(200, { ok: true })]),
    async (s) => {
      waits.push(s);
    },
  );
  expect(await http.getJson('https://api.example/x', { q: 'x' })).toEqual({ ok: true });
  expect(waits).toEqual([2]);
});

test('gives up on a long 429 without waiting', async () => {
  const calls: string[] = [];
  const waits: number[] = [];
  const http = new CachedHttp(
    new ResponseCache(tmpDir()),
    fakeFetch(calls, [json(429, {}, { 'Retry-After': '60' })]),
    async (s) => {
      waits.push(s);
    },
  );
  await expect(http.getJson('https://api.example/x', { q: 'x' })).rejects.toBeInstanceOf(HttpStatusError);
  expect(calls).toHaveLength(1);
  expect(waits).toEqual([]);
});

test('error messages never contain the API key', async () => {
  const http = new CachedHttp(new ResponseCache(tmpDir()), fakeFetch([], [json(400, {})]));
  const error = await http.getJson('https://pixabay.com/api/', { key: 'SECRET', q: 'x' }).catch((e) => e);
  expect(error.message).not.toContain('SECRET');
  expect(error.message).toContain('pixabay.com');
});

test('user agent identifies the tool and a way to reach it', () => {
  expect(USER_AGENT.startsWith('resolvestock/')).toBe(true);
  expect(USER_AGENT).toContain('https://github.com/rychan404/davinci-resolve-plugin');
});
