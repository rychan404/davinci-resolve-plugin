import { expect, test } from 'vitest';
import { filterCommercialSafe, isCommercialSafe, normalizeLicenseId } from '../src/shared/licenses';
import { makeResult } from './helpers';

test('normalizes license names and judges commercial safety', () => {
  expect(normalizeLicenseId('CC BY-SA 4.0')).toBe('cc-by-sa');
  expect(normalizeLicenseId('CC0 1.0')).toBe('cc0');
  expect(normalizeLicenseId('pdm')).toBe('public-domain');
  expect(normalizeLicenseId('')).toBe('unknown');
  expect(isCommercialSafe('cc0')).toBe(true);
  expect(isCommercialSafe('cc-by-nc')).toBe(false);
  expect(isCommercialSafe('unrecognized')).toBe(false);
});

test('filters out restricted licenses', () => {
  const kept = filterCommercialSafe([
    makeResult({ license_id: 'cc-by' }),
    makeResult({ source_id: '2', license_id: 'cc-by-sa' }),
  ]);
  expect(kept.map((r) => r.source_id)).toEqual(['1']);
});
