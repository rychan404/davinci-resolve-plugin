import { filterCommercialSafe } from '../../shared/licenses';
import { uidOf, type SearchOutcome, type SearchQuery, type SearchResult } from '../../shared/types';
import type { Config } from '../config';
import type { JsonGetter } from '../http';
import { OpenverseSource } from './openverse';
import { PixabaySource } from './pixabay';
import { WikimediaSource } from './wikimedia';

export interface Source {
  readonly name: string;
  search(q: SearchQuery): Promise<SearchResult[]>;
}

/** Fault-tolerant fan-out across configured sources. */
export class SourceRegistry {
  constructor(readonly sources: Source[]) {}

  async search(q: SearchQuery): Promise<SearchOutcome> {
    const errors: Record<string, string> = {};
    const selected = this.sources.filter((s) => q.source === null || q.source === s.name);
    if (q.source && selected.length === 0) errors[q.source] = 'not configured';

    const settled = await Promise.allSettled(selected.map((s) => s.search(q)));
    const groups: SearchResult[][] = [];
    settled.forEach((outcome, i) => {
      if (outcome.status === 'fulfilled') groups.push(outcome.value);
      else errors[selected[i].name] = outcome.reason instanceof Error ? outcome.reason.message : String(outcome.reason);
    });

    // Interleave like zip_longest so no single source dominates the top of the grid.
    let merged: SearchResult[] = [];
    const longest = Math.max(0, ...groups.map((g) => g.length));
    for (let i = 0; i < longest; i++) for (const g of groups) if (i < g.length) merged.push(g[i]);

    if (q.commercial_safe_only) merged = filterCommercialSafe(merged);
    const seen = new Set<string>();
    const results = merged.filter((r) => {
      const uid = uidOf(r);
      if (seen.has(uid)) return false;
      seen.add(uid);
      return true;
    });
    return { results, errors };
  }
}

export function buildRegistry(http: JsonGetter, config: Config): SourceRegistry {
  const sources: Source[] = [new OpenverseSource(http), new WikimediaSource(http)];
  if (config.pixabay_key) sources.push(new PixabaySource(http, config.pixabay_key));
  return new SourceRegistry(sources);
}
