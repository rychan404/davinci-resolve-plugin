import { normalizeLicenseId } from '../../shared/licenses';
import type { SearchQuery, SearchResult } from '../../shared/types';
import type { JsonGetter } from '../http';
import type { Source } from './registry';

const ENDPOINT = 'https://commons.wikimedia.org/w/api.php';
const stripHtml = (value: string): string => value.replace(/<[^>]+>/g, '').trim();

export class WikimediaSource implements Source {
  readonly name = 'wikimedia';

  constructor(private readonly http: JsonGetter) {}

  async search(q: SearchQuery): Promise<SearchResult[]> {
    let terms = q.text;
    if (q.vectors_only) terms = `filetype:drawing ${terms}`;
    else if (q.transparent_only) terms = `filemime:png ${terms}`;
    const params = {
      action: 'query',
      format: 'json',
      generator: 'search',
      gsrsearch: terms,
      gsrnamespace: 6,
      gsrlimit: q.per_page,
      gsroffset: (q.page - 1) * q.per_page,
      prop: 'imageinfo',
      iiprop: 'url|size|mime|extmetadata',
      iiurlwidth: 320,
    };
    return this.parse(await this.http.getJson(ENDPOINT, params));
  }

  parse(payload: any): SearchResult[] {
    // Object.values on integer-like keys sorts by page id, not search rank, so
    // order by `index`; pages without one go last in their original order.
    const pages: any[] = Object.values(payload?.query?.pages ?? {});
    pages.sort((a, b) => (a.index ?? Infinity) - (b.index ?? Infinity) || 0);
    const results: SearchResult[] = [];
    for (const page of pages) {
      const info = page.imageinfo?.[0];
      if (!info) continue;
      const meta = info.extmetadata ?? {};
      const mime = String(info.mime ?? '').toLowerCase();
      const title = String(page.title ?? '').replace(/^File:/, '') || 'untitled';
      const artist = stripHtml(meta.Artist?.value ?? '');
      results.push({
        source: this.name,
        source_id: String(page.pageid ?? ''),
        title,
        preview_url: info.thumburl || info.url || '',
        download_url: info.url || '',
        media_type: mime === 'image/svg+xml' ? 'vector' : 'image',
        width: info.width ?? null,
        height: info.height ?? null,
        has_alpha: mime ? ['image/png', 'image/svg+xml', 'image/webp', 'image/gif'].includes(mime) : null,
        license_id: normalizeLicenseId(meta.LicenseShortName?.value ?? ''),
        license_url: meta.LicenseUrl?.value ?? '',
        attribution: artist ? `${title} by ${artist} (Wikimedia Commons)` : `${title} (Wikimedia Commons)`,
        source_page_url: info.descriptionurl || '',
      });
    }
    return results;
  }
}
