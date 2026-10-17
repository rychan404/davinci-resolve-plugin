import path from 'node:path';
import { expect, test } from 'vitest';
import { Library } from '../src/main/library';
import { Session } from '../src/main/session';
import { SourceRegistry } from '../src/main/sources/registry';
import { makeQuery, type SearchResult } from '../src/shared/types';
import { fakeFetch, makeResult, tmpDir } from './helpers';

const registry = (results: SearchResult[]) => new SourceRegistry([{ name: 'a', search: async () => results }]);

test('each search starts a new generation and only the newest is current', async () => {
  const session = new Session(registry([]), new Library(tmpDir()));
  const first = await session.search(makeQuery('a'));
  const second = await session.search(makeQuery('b'));
  expect(second.generation).toBe(first.generation + 1);
  expect(session.isCurrent(first.generation)).toBe(false);
  expect(session.isCurrent(second.generation)).toBe(true);
});

test('downloads only results a search returned', async () => {
  const library = new Library(tmpDir(), fakeFetch([], [new Response('x')]));
  const session = new Session(registry([makeResult({ source: 'a' })]), library);
  await expect(session.download('a:1')).rejects.toThrow('unknown result');
  await session.search(makeQuery('smoke'));
  expect(path.basename((await session.download('a:1')).local_path)).toBe('smoke_plume_a_1.png');
});

test('source names come from the registry', () => {
  expect(new Session(registry([]), new Library(tmpDir())).sourceNames()).toEqual(['a']);
});
