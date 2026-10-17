import { expect, test } from 'vitest';
import { searchMessage, withProgress } from '../src/renderer/status';
import { makeResult } from './helpers';

test('search message lists failed sources', () => {
  expect(
    searchMessage({
      results: [makeResult(), makeResult()],
      errors: { pixabay: '429 Too Many Requests from pixabay.com' },
    }),
  ).toBe('2 result(s) — some sources failed — pixabay: 429 Too Many Requests from pixabay.com');
  expect(searchMessage({ results: [], errors: {} })).toBe('0 result(s)');
});

test('progress shows only while previews are outstanding', () => {
  expect(withProgress('1 result(s)', 3, 10)).toBe('1 result(s) — 3/10 previews loaded');
  expect(withProgress('1 result(s)', 10, 10)).toBe('1 result(s)');
  expect(withProgress('1 result(s)', 0, 0)).toBe('1 result(s)');
});
