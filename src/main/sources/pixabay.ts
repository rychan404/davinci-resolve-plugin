import type { SearchQuery, SearchResult } from '../../shared/types';
import type { JsonGetter } from '../http';
import type { Source } from './registry';

const ENDPOINT = 'https://pixabay.com/api/';
// Pixabay answers 400 rather than an empty page once a request leaves the
// documented ranges, and the registry would report that as a failed source.
const MIN_PER_PAGE = 3;
const MAX_PER_PAGE = 200;
const MAX_QUERY_CHARS = 100;
// Only the first 500 hits of any query are reachable, whatever totalHits says.
const RESULT_CEILING = 500;
const ALPHA_EXTENSIONS = ['png', 'svg', 'gif', 'webp'];

const imageTypeFor = (q: SearchQuery): string => (q.vectors_only ? 'vector' : q.photos_only ? 'photo' : 'all');

function extensionOf(url: string): string {
  const last = url.split('/').pop() ?? '';
  return last.includes('.') ? (url.split('.').pop() ?? '').toLowerCase() : '';
}

export class PixabaySource implements Source {
  readonly name = 'pixabay';

  constructor(
    private readonly http: JsonGetter,
    private readonly apiKey: string,
  ) {}

  async search(q: SearchQuery): Promise<SearchResult[]> {
    const perPage = Math.min(Math.max(q.per_page, MIN_PER_PAGE), MAX_PER_PAGE);
    if ((q.page - 1) * perPage >= RESULT_CEILING) return [];
    const params: Record<string, string | number> = {
      key: this.apiKey,
      q: q.text.slice(0, MAX_QUERY_CHARS).trim(),
      page: q.page,
      per_page: perPage,
      image_type: imageTypeFor(q),
      safesearch: 'true',
    };
    if (q.transparent_only) params.colors = 'transparent';
    return this.parse(await this.http.getJson(ENDPOINT, params));
  }

  parse(payload: any): SearchResult[] {
    const results: SearchResult[] = [];
    for (const hit of payload?.hits ?? []) {
      // An empty id collapses uid to "pixabay:", which the registry's dedupe
      // would then treat as one repeated result.
      const sourceId = String(hit.id ?? '');
      if (!sourceId) continue;
      const title = String(hit.tags ?? '').split(',')[0].trim() || 'untitled';
      const downloadUrl = hit.largeImageURL || hit.webformatURL || hit.previewURL || '';
      const ext = extensionOf(downloadUrl);
      results.push({
        source: this.name,
        source_id: sourceId,
        title,
        preview_url: hit.previewURL || '',
        download_url: downloadUrl,
        media_type: String(hit.type ?? '').toLowerCase().includes('vector') ? 'vector' : 'image',
        width: hit.imageWidth ?? null,
        height: hit.imageHeight ?? null,
        has_alpha: ext ? ALPHA_EXTENSIONS.includes(ext) : null,
        license_id: 'pixabay',
        license_url: 'https://pixabay.com/service/license-summary/',
        attribution: hit.user ? `${title} by ${hit.user} (Pixabay)` : `${title} (Pixabay)`,
        source_page_url: hit.pageURL || '',
      });
    }
    return results;
  }
}
