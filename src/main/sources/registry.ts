import type { SearchQuery, SearchResult } from '../../shared/types';

export interface Source {
  readonly name: string;
  search(q: SearchQuery): Promise<SearchResult[]>;
}
