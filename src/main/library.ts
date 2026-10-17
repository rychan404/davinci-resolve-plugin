import fs from 'node:fs';
import path from 'node:path';
import { RESULT_FIELDS, type LibraryItem, type SearchResult } from '../shared/types';
import { HttpStatusError, USER_AGENT, type Fetch } from './http';

export const SIDECAR_SUFFIX = '.provenance.json';

export function slugify(text: string, maxLength = 48): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, maxLength)
    .replace(/_+$/, '');
}

export class Library {
  constructor(
    readonly root: string,
    private readonly fetchImpl: Fetch = fetch,
  ) {}

  normalizeFilename(r: SearchResult, suffix: string): string {
    return `${slugify(r.title) || 'untitled'}_${r.source}_${r.source_id}${suffix}`;
  }

  sidecarPath(p: string): string {
    return p + SIDECAR_SUFFIX;
  }

  async download(r: SearchResult): Promise<LibraryItem> {
    fs.mkdirSync(this.root, { recursive: true });
    const suffix = path.posix.extname(new URL(r.download_url).pathname).toLowerCase() || '.bin';
    const target = path.join(this.root, this.normalizeFilename(r, suffix));
    if (fs.existsSync(target) && fs.existsSync(this.sidecarPath(target))) {
      try {
        return this.readItem(target);
      } catch {
        // A broken sidecar means the asset has lost its provenance; fetch it again.
      }
    }
    const response = await this.fetchImpl(r.download_url, {
      headers: { 'User-Agent': USER_AGENT },
      signal: AbortSignal.timeout(60000),
    });
    if (!response.ok) throw new HttpStatusError(response.status, response.statusText, r.download_url);
    const body = Buffer.from(await response.arrayBuffer());

    const temporary = target + '.part';
    try {
      fs.writeFileSync(temporary, body);
      fs.renameSync(temporary, target);
      const downloaded_at = new Date().toISOString();
      const record: Record<string, unknown> = {};
      for (const field of RESULT_FIELDS) record[field] = r[field];
      record.downloaded_at = downloaded_at;
      fs.writeFileSync(this.sidecarPath(target), JSON.stringify(record, null, 2), 'utf8');
      return { local_path: target, downloaded_at, result: r };
    } catch (error) {
      fs.rmSync(temporary, { force: true });
      throw error;
    }
  }

  items(): LibraryItem[] {
    if (!fs.existsSync(this.root)) return [];
    const found: LibraryItem[] = [];
    for (const name of fs.readdirSync(this.root).sort()) {
      if (!name.endsWith(SIDECAR_SUFFIX)) continue;
      const asset = path.join(this.root, name.slice(0, -SIDECAR_SUFFIX.length));
      if (!fs.existsSync(asset)) continue;
      try {
        found.push(this.readItem(asset));
      } catch {
        // One hand-edited or truncated sidecar must not empty the whole tray.
      }
    }
    return found;
  }

  /** True only for an existing, non-sidecar file directly inside the library folder. */
  contains(filePath: string): boolean {
    const norm = (p: string) => (process.platform === 'win32' ? p.toLowerCase() : p);
    const resolved = path.resolve(filePath);
    if (norm(path.dirname(resolved)) !== norm(path.resolve(this.root))) return false;
    if (resolved.endsWith(SIDECAR_SUFFIX)) return false;
    try {
      return fs.statSync(resolved).isFile();
    } catch {
      return false;
    }
  }

  private readItem(asset: string): LibraryItem {
    const data = JSON.parse(fs.readFileSync(this.sidecarPath(asset), 'utf8'));
    if (typeof data !== 'object' || data === null || typeof data.source !== 'string' || typeof data.source_id !== 'string') {
      throw new Error('invalid sidecar');
    }
    const result = {} as Record<string, unknown>;
    for (const field of RESULT_FIELDS) result[field] = data[field] ?? null;
    return { local_path: asset, downloaded_at: String(data.downloaded_at ?? ''), result: result as unknown as SearchResult };
  }
}
