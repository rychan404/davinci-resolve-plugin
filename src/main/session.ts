import { uidOf, type LibraryItem, type SearchQuery, type SearchResponse, type SearchResult } from '../shared/types';
import type { Library } from './library';
import type { SourceRegistry } from './sources/registry';

/**
 * State one app run keeps between calls: which search is newest, and which
 * results the user has been shown (so `download` can take a uid, not a URL).
 */
export class Session {
  private generation = 0;
  private readonly seen = new Map<string, SearchResult>();

  constructor(
    private readonly registry: SourceRegistry,
    private readonly library: Library,
  ) {}

  sourceNames(): string[] {
    return this.registry.sources.map((s) => s.name);
  }

  async search(q: SearchQuery): Promise<SearchResponse> {
    // Bump before awaiting so in-flight preview requests of the old search are refused.
    const generation = ++this.generation;
    const outcome = await this.registry.search(q);
    for (const r of outcome.results) this.seen.set(uidOf(r), r);
    return { generation, ...outcome };
  }

  isCurrent(generation: number): boolean {
    return generation === this.generation;
  }

  async download(uid: string): Promise<LibraryItem> {
    const result = this.seen.get(uid);
    if (!result) throw new Error('unknown result');
    return this.library.download(result);
  }
}
