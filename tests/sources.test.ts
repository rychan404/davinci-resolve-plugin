import fs from 'node:fs';
import { expect, test } from 'vitest';
import type { JsonGetter } from '../src/main/http';
import { OpenverseSource } from '../src/main/sources/openverse';
import { PixabaySource } from '../src/main/sources/pixabay';
import { WikimediaSource } from '../src/main/sources/wikimedia';
import { makeQuery } from '../src/shared/types';
import { fixturePath } from './helpers';

const captured: Record<string, string | number>[] = [];

function fake(payload: unknown): JsonGetter {
  captured.length = 0;
  return {
    getJson: async (_url, params) => {
      captured.push(params);
      return payload;
    },
  };
}

const fixture = (name: string) => JSON.parse(fs.readFileSync(fixturePath(name), 'utf8'));

test('openverse keeps page size within the anonymous limit', async () => {
  await new OpenverseSource(fake({ results: [] })).search(makeQuery('piano', { per_page: 40 }));
  expect(captured[0].page_size).toBe(20);
});

test('openverse normalizes svg and attribution', async () => {
  const [first] = await new OpenverseSource(fake(fixture('openverse_transparent.json'))).search(makeQuery('arrow'));
  expect(first.media_type).toBe('vector');
  expect(first.license_id).toBe('cc-by');
});

test('wikimedia reads extmetadata', async () => {
  const [first] = await new WikimediaSource(fake(fixture('wikimedia_search.json'))).search(makeQuery('x'));
  expect(first.license_id).toBe('cc-by');
  expect(first.attribution).toContain('Fixture Author');
});

test('wikimedia keeps search rank order, not page-id order', async () => {
  // JS orders integer-like object keys numerically, so Object.values would sort by page id.
  const page = (id: number, index: number) => ({
    pageid: id,
    index,
    title: `File:${id}.png`,
    imageinfo: [{ url: `https://e.invalid/${id}.png`, mime: 'image/png', extmetadata: {} }],
  });
  const results = await new WikimediaSource(
    fake({ query: { pages: { '300': page(300, 2), '200': page(200, 1) } } }),
  ).search(makeQuery('x'));
  expect(results.map((r) => r.source_id)).toEqual(['200', '300']);
});

test('pixabay uses the largest asset and the transparent filter', async () => {
  const [first] = await new PixabaySource(fake(fixture('pixabay_transparent.json')), 'key').search(
    makeQuery('arrow', { transparent_only: true }),
  );
  expect(first.download_url).toBe('https://example.invalid/large.png');
  expect(captured[0].colors).toBe('transparent');
});

test('pixabay stops before the reachable result ceiling', async () => {
  expect(
    await new PixabaySource(fake({ hits: [] }), 'key').search(makeQuery('arrow', { page: 14, per_page: 40 })),
  ).toEqual([]);
  expect(captured).toEqual([]);
});

test('pixabay clamps page size and query length', async () => {
  const source = new PixabaySource(fake({ hits: [] }), 'key');
  await source.search(makeQuery('arrow', { per_page: 500 }));
  await source.search(makeQuery('dog '.repeat(40)));
  expect(captured[0].per_page).toBe(200);
  expect(String(captured[1].q).length).toBeLessThanOrEqual(100);
});

test('pixabay asks for photos when the query wants photos', async () => {
  await new PixabaySource(fake(fixture('pixabay_photos.json')), 'key').search(
    makeQuery('retriever', { photos_only: true }),
  );
  expect(captured[0].image_type).toBe('photo');
});

test('pixabay parsing: alpha, first-tag titles, id-less hits skipped', async () => {
  const transparent = await new PixabaySource(fake(fixture('pixabay_transparent.json')), 'k').search(makeQuery('a'));
  const photos = await new PixabaySource(fake(fixture('pixabay_photos.json')), 'k').search(makeQuery('r'));
  expect(transparent[0].has_alpha).toBe(true);
  expect(photos[0].has_alpha).toBe(false);
  expect(photos[0].title).toBe('golden retriever');
  expect(photos.map((r) => r.source_id)).toEqual(['2002']);
});
