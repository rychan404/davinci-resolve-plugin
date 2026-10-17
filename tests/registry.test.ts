import fs from 'node:fs';
import path from 'node:path';
import { expect, test, vi } from 'vitest';
import { loadConfig } from '../src/main/config';
import { SourceRegistry, buildRegistry, type Source } from '../src/main/sources/registry';
import { makeQuery, uidOf, type SearchResult } from '../src/shared/types';
import { makeResult, tmpDir } from './helpers';

const src = (name: string, values: SearchResult[] = [], error?: Error): Source => ({
  name,
  search: vi.fn(async () => {
    if (error) throw error;
    return values;
  }),
});

test('interleaves, deduplicates and keeps source failures', async () => {
  const outcome = await new SourceRegistry([
    src('a', [makeResult({ source: 'a', source_id: '1' }), makeResult({ source: 'a', source_id: '2' })]),
    src('b', [makeResult({ source: 'b', source_id: '1' })]),
    src('bad', [], new Error('offline')),
  ]).search(makeQuery('smoke'));
  expect(outcome.results.map(uidOf)).toEqual(['a:1', 'b:1', 'a:2']);
  expect(outcome.errors).toEqual({ bad: 'offline' });
});

test('searches only the selected source', async () => {
  const a = src('a', [], new Error('should not be called'));
  const outcome = await new SourceRegistry([a, src('b', [makeResult({ source: 'b' })])]).search(
    makeQuery('smoke', { source: 'b' }),
  );
  expect(outcome.results.map(uidOf)).toEqual(['b:1']);
  expect(a.search).not.toHaveBeenCalled();
});

test('reports an unconfigured source', async () => {
  const outcome = await new SourceRegistry([src('a', [makeResult()])]).search(
    makeQuery('smoke', { source: 'pixabay' }),
  );
  expect(outcome).toEqual({ results: [], errors: { pixabay: 'not configured' } });
});

test('drops restricted licenses when commercial-safe is on', async () => {
  const registry = new SourceRegistry([src('a', [makeResult({ source: 'a', license_id: 'cc-by-nc' })])]);
  expect((await registry.search(makeQuery('x'))).results).toEqual([]);
  expect((await registry.search(makeQuery('x', { commercial_safe_only: false }))).results).toHaveLength(1);
});

test('pixabay is registered only with a key', () => {
  const http = { getJson: async () => ({}) };
  const names = (key: string | null) =>
    buildRegistry(http, { path: '', pixabay_key: key, library_dir: '' }).sources.map((s) => s.name);
  expect(names(null)).toEqual(['openverse', 'wikimedia']);
  expect(names('k')).toEqual(['openverse', 'wikimedia', 'pixabay']);
});

test('config falls back to defaults for a missing or broken file', () => {
  const home = tmpDir();
  expect(loadConfig(path.join(home, 'missing.json'), home)).toMatchObject({
    pixabay_key: null,
    library_dir: path.join(home, 'ResolveStock'),
  });
  fs.writeFileSync(path.join(home, 'broken.json'), '{nope');
  expect(loadConfig(path.join(home, 'broken.json'), home).pixabay_key).toBeNull();
  fs.writeFileSync(path.join(home, 'null.json'), 'null');
  expect(loadConfig(path.join(home, 'null.json'), home).pixabay_key).toBeNull();
  fs.writeFileSync(path.join(home, 'ok.json'), JSON.stringify({ pixabay_key: 'k', library_dir: 'D:\\Stock' }));
  expect(loadConfig(path.join(home, 'ok.json'), home)).toMatchObject({ pixabay_key: 'k', library_dir: 'D:\\Stock' });
});
