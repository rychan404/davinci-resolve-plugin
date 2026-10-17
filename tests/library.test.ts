import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from 'vitest';
import { buildCredits } from '../src/main/credits';
import { HttpStatusError } from '../src/main/http';
import { Library, slugify } from '../src/main/library';
import { RESULT_FIELDS } from '../src/shared/types';
import { fakeFetch, fixturePath, makeResult, tmpDir } from './helpers';

const png = () => fakeFetch([], [new Response(new Uint8Array([1, 2, 3]))]);

test('download writes the asset and a provenance sidecar', async () => {
  const library = new Library(path.join(tmpDir(), 'library'), png());
  const item = await library.download(makeResult());
  expect(path.basename(item.local_path)).toBe('smoke_plume_source_1.png');
  const sidecar = JSON.parse(fs.readFileSync(library.sidecarPath(item.local_path), 'utf8'));
  expect(Object.keys(sidecar)).toEqual([...RESULT_FIELDS, 'downloaded_at']);
  expect(library.items()[0].result.attribution).toBe('Smoke by Jane');
  expect(fs.existsSync(item.local_path + '.part')).toBe(false);
});

test('downloading an asset already in the library reuses it', async () => {
  const calls: string[] = [];
  const library = new Library(tmpDir(), fakeFetch(calls, [new Response('x')]));
  await library.download(makeResult());
  await library.download(makeResult());
  expect(calls).toHaveLength(1);
});

test('a failed download leaves no partial file', async () => {
  const root = tmpDir();
  const library = new Library(root, fakeFetch([], [new Response('', { status: 404 })]));
  await expect(library.download(makeResult())).rejects.toBeInstanceOf(HttpStatusError);
  expect(fs.readdirSync(root)).toEqual([]);
});

test('titles without ASCII letters still get a unique name', () => {
  const library = new Library(tmpDir());
  expect(
    library.normalizeFilename(makeResult({ title: '東京', source: 'openverse', source_id: '9' }), '.png'),
  ).toBe('untitled_openverse_9.png');
  expect(slugify('  Hello, World!  ')).toBe('hello_world');
});

test('items written by the Python app load', () => {
  const root = tmpDir();
  fs.writeFileSync(path.join(root, 'smoke_plume_openverse_abc.png'), 'x');
  fs.copyFileSync(
    fixturePath('python_sidecar.provenance.json'),
    path.join(root, 'smoke_plume_openverse_abc.png.provenance.json'),
  );
  const [item] = new Library(root).items();
  expect(item.result.height).toBeNull();
  expect(item.downloaded_at).toBe('2026-08-01T12:00:00.123456+00:00');
});

test('a broken sidecar skips only that item', () => {
  const root = tmpDir();
  fs.writeFileSync(path.join(root, 'a.png'), 'x');
  fs.writeFileSync(path.join(root, 'a.png.provenance.json'), '{truncated');
  fs.writeFileSync(path.join(root, 'b.png'), 'x');
  fs.copyFileSync(fixturePath('python_sidecar.provenance.json'), path.join(root, 'b.png.provenance.json'));
  expect(new Library(root).items().map((i) => path.basename(i.local_path))).toEqual(['b.png']);
});

test('contains accepts only existing assets directly inside the library', () => {
  const root = tmpDir();
  fs.writeFileSync(path.join(root, 'a.png'), 'x');
  fs.writeFileSync(path.join(path.dirname(root), 'outside.txt'), 'x');
  const library = new Library(root);
  expect(library.contains(path.join(root, 'a.png'))).toBe(true);
  expect(library.contains(path.join(root, '..', 'outside.txt'))).toBe(false);
  expect(library.contains(path.join(root, 'missing.png'))).toBe(false);
  expect(library.contains(path.join(root, 'a.png.provenance.json'))).toBe(false);
});

test('credits omit cc0 and list attribution-required assets once', () => {
  const at = new Date().toISOString();
  const text = buildCredits([
    { local_path: 'x.png', downloaded_at: at, result: makeResult() },
    { local_path: 'x2.png', downloaded_at: at, result: makeResult({ source_id: '3' }) },
    { local_path: 'y.png', downloaded_at: at, result: makeResult({ source: 'other', source_id: '2', license_id: 'cc0' }) },
  ]);
  expect(text).toBe(
    'Credits\n=======\n\n- Smoke by Jane\n  CC BY 4.0 - https://example.invalid/license\n  https://example.invalid/page\n',
  );
  expect(buildCredits([])).toBe('Credits\n=======\n\nNo attribution required for the assets in this library.\n');
});
