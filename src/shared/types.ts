export interface SearchResult {
  source: string;
  source_id: string;
  title: string;
  preview_url: string;
  download_url: string;
  media_type: string;
  width: number | null;
  height: number | null;
  has_alpha: boolean | null;
  license_id: string;
  license_url: string;
  attribution: string;
  source_page_url: string;
}

/** Sidecar key order; must match the Python app's `SearchResult` field order. */
export const RESULT_FIELDS = [
  'source',
  'source_id',
  'title',
  'preview_url',
  'download_url',
  'media_type',
  'width',
  'height',
  'has_alpha',
  'license_id',
  'license_url',
  'attribution',
  'source_page_url',
] as const;

export const uidOf = (r: SearchResult): string => `${r.source}:${r.source_id}`;

export interface LibraryItem {
  local_path: string;
  downloaded_at: string;
  result: SearchResult;
}

export interface SearchQuery {
  text: string;
  page: number;
  per_page: number;
  transparent_only: boolean;
  vectors_only: boolean;
  commercial_safe_only: boolean;
  photos_only: boolean;
  source: string | null;
}

export function makeQuery(text: string, overrides: Partial<SearchQuery> = {}): SearchQuery {
  return {
    text,
    page: 1,
    per_page: 40,
    transparent_only: false,
    vectors_only: false,
    commercial_safe_only: true,
    photos_only: false,
    source: null,
    ...overrides,
  };
}

export interface SearchOutcome {
  results: SearchResult[];
  errors: Record<string, string>;
}

export interface SearchResponse extends SearchOutcome {
  generation: number;
}

export interface Api {
  getSources(): Promise<string[]>;
  search(q: SearchQuery): Promise<SearchResponse>;
  download(uid: string): Promise<LibraryItem>;
  listLibrary(): Promise<LibraryItem[]>;
  exportCredits(): Promise<string | null>;
  startDrag(paths: string[]): void;
}
