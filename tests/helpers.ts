import type { SearchResult } from '../src/shared/types';

export function makeResult(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    source: 'source',
    source_id: '1',
    title: 'Smoke Plume',
    preview_url: 'https://example.invalid/preview.png',
    download_url: 'https://example.invalid/smoke.png',
    media_type: 'image',
    width: 100,
    height: 100,
    has_alpha: true,
    license_id: 'cc-by',
    license_url: 'https://example.invalid/license',
    attribution: 'Smoke by Jane',
    source_page_url: 'https://example.invalid/page',
    ...overrides,
  };
}
