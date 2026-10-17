import type { SearchResult } from './types';

export interface License {
  name: string;
  url: string;
  commercial_safe: boolean;
  requires_attribution: boolean;
}

export const LICENSES: Record<string, License> = {
  cc0: { name: 'CC0 1.0', url: 'https://creativecommons.org/publicdomain/zero/1.0/', commercial_safe: true, requires_attribution: false },
  'public-domain': { name: 'Public Domain', url: 'https://en.wikipedia.org/wiki/Public_domain', commercial_safe: true, requires_attribution: false },
  pixabay: { name: 'Pixabay Content License', url: 'https://pixabay.com/service/license-summary/', commercial_safe: true, requires_attribution: false },
  'cc-by': { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/', commercial_safe: true, requires_attribution: true },
  'cc-by-sa': { name: 'CC BY-SA 4.0', url: 'https://creativecommons.org/licenses/by-sa/4.0/', commercial_safe: false, requires_attribution: true },
  'cc-by-nc': { name: 'CC BY-NC 4.0', url: 'https://creativecommons.org/licenses/by-nc/4.0/', commercial_safe: false, requires_attribution: true },
  'cc-by-nc-sa': { name: 'CC BY-NC-SA 4.0', url: 'https://creativecommons.org/licenses/by-nc-sa/4.0/', commercial_safe: false, requires_attribution: true },
  'cc-by-nd': { name: 'CC BY-ND 4.0', url: 'https://creativecommons.org/licenses/by-nd/4.0/', commercial_safe: false, requires_attribution: true },
};

export const UNKNOWN: License = {
  name: 'Unknown',
  url: 'https://example.invalid/unknown',
  commercial_safe: false,
  requires_attribution: true,
};

const isCc0 = (t: string) => t === '0' || t === 'cc0' || t === 'zero';

export function normalizeLicenseId(raw: string): string {
  if (!raw) return 'unknown';
  let text = raw.trim().toLowerCase().replace(/_/g, '-').replace(/\//g, '-').replace(/ /g, '-');
  text = text.replace(/-+/g, '-').replace(/^-+|-+$/g, '');
  // CC0 is itself a license name, not a version number. Handle it before
  // stripping trailing versions such as the one in "CC0 1.0".
  if (isCc0(text)) return 'cc0';
  text = text.replace(/-?\d+(\.\d+)?$/, '');
  if (text.startsWith('cc-')) text = text.slice(3);
  if (isCc0(text)) return 'cc0';
  if (text === 'pd' || text === 'public-domain' || text === 'pdm') return 'public-domain';
  if (text === 'pixabay') return text;
  const candidate = `cc-${text}`;
  return candidate in LICENSES ? candidate : 'unknown';
}

export const getLicense = (id: string): License => LICENSES[id] ?? UNKNOWN;
export const isCommercialSafe = (id: string): boolean => getLicense(id).commercial_safe;
export const filterCommercialSafe = (results: SearchResult[]): SearchResult[] =>
  results.filter((r) => isCommercialSafe(r.license_id));
