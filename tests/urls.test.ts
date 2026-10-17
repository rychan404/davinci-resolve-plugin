import { expect, test } from 'vitest';
import { librarySrc, parseLibraryUrl, parsePreviewUrl, previewSrc } from '../src/shared/urls';

test('preview URLs round-trip', () => {
  const url = 'https://upload.example.org/a b/ü.png?x=1';
  expect(parsePreviewUrl(previewSrc(7, url))).toEqual({ generation: 7, target: url });
});

test('preview URLs reject non-http targets and bad generations', () => {
  expect(parsePreviewUrl('preview://7/?u=' + encodeURIComponent('file:///C:/secret.txt'))).toBeNull();
  expect(parsePreviewUrl('preview://x/?u=' + encodeURIComponent('https://a.example/b.png'))).toBeNull();
});

test('library URLs carry only the file name', () => {
  expect(parseLibraryUrl(librarySrc('C:\\Users\\me\\ResolveStock\\smoke plume_openverse_1.png'))).toBe(
    'smoke plume_openverse_1.png',
  );
});
