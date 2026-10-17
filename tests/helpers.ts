import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
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

export const tmpDir = (): string => fs.mkdtempSync(path.join(os.tmpdir(), 'resolvestock-'));

export const fixturePath = (name: string): string => path.join(__dirname, 'fixtures', name);

export const json = (status: number, body: unknown, headers: Record<string, string> = {}): Response =>
  new Response(JSON.stringify(body), { status, headers });

/** A fetch that records each URL into `calls` and returns the next canned response. */
export function fakeFetch(calls: string[], responses: Response[]): typeof fetch {
  const queue = [...responses];
  return (async (input: string | URL | Request) => {
    calls.push(String(input));
    const next = queue.shift();
    if (!next) throw new Error('fakeFetch: no response left');
    return next;
  }) as typeof fetch;
}
