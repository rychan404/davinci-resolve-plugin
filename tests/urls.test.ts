import { expect, test } from 'vitest';
import { librarySrc, parseLibraryUrl, parsePreviewUrl, previewSrc } from '../src/shared/urls';

test('preview URLs round-trip', () => {
  const url = 'https://upload.example.org/a b/ü.png?x=1';
  expect(parsePreviewUrl(previewSrc(7, url))).toEqual({ generation: 7, target: url });
});

test('preview URLs keep the generation out of the host', () => {
  // Chromium canonicalizes a numeric host on a standard scheme as IPv4 (7 -> 0.0.0.7).
  expect(new URL(previewSrc(7, 'https://a.example/b.png')).hostname).not.toMatch(/^[\d.]+$/);
});

test('preview URLs reject non-http targets and bad generations', () => {
  expect(parsePreviewUrl('preview://thumb/7?u=' + encodeURIComponent('file:///C:/secret.txt'))).toBeNull();
  expect(parsePreviewUrl('preview://thumb/x?u=' + encodeURIComponent('https://a.example/b.png'))).toBeNull();
});

test('library URLs carry only the file name', () => {
  expect(parseLibraryUrl(librarySrc('C:\\Users\\me\\ResolveStock\\smoke plume_openverse_1.png'))).toBe(
    'smoke plume_openverse_1.png',
  );
});
