import { normalizeLicenseId } from '../../shared/licenses';
import type { SearchQuery, SearchResult } from '../../shared/types';
import type { JsonGetter } from '../http';
import type { Source } from './registry';

const ENDPOINT = 'https://api.openverse.org/v1/images/';
// Anonymous clients may not ask for more than this; Openverse answers 401, and
// the registry then reports the whole source as failed.
const ANONYMOUS_PAGE_SIZE = 20;

export class OpenverseSource implements Source {
  readonly name = 'openverse';

  constructor(private readonly http: JsonGetter) {}

  async search(q: SearchQuery): Promise<SearchResult[]> {
    const params: Record<string, string | number> = {
      q: q.text,
      page: q.page,
      page_size: Math.min(q.per_page, ANONYMOUS_PAGE_SIZE),
    };
    if (q.vectors_only) params.extension = 'svg';
    else if (q.transparent_only) params.extension = 'png,svg';
    if (q.commercial_safe_only) params.license_type = 'commercial,modification';
    return this.parse(await this.http.getJson(ENDPOINT, params));
  }

  parse(payload: any): SearchResult[] {
    return (payload?.results ?? []).map((record: any): SearchResult => {
      const filetype = String(record.filetype ?? '').toLowerCase();
      const title = record.title || 'untitled';
      const creator = record.creator || '';
      return {
        source: this.name,
        source_id: String(record.id ?? ''),
        title,
        preview_url: record.thumbnail || record.url || '',
        download_url: record.url || '',
        media_type: filetype === 'svg' ? 'vector' : 'image',
        width: record.width ?? null,
        height: record.height ?? null,
        has_alpha: filetype ? ['png', 'svg', 'gif', 'webp'].includes(filetype) : null,
        license_id: normalizeLicenseId(record.license || ''),
        license_url: record.license_url || '',
        attribution: creator ? `${title} by ${creator} (Openverse)` : `${title} (Openverse)`,
        source_page_url: record.foreign_landing_url || record.url || '',
      };
    });
  }
}
