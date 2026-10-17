import fs from 'node:fs';
import path from 'node:path';
import { getLicense } from '../shared/licenses';
import type { LibraryItem } from '../shared/types';

const HEADER = 'Credits\n=======\n';

export function buildCredits(items: LibraryItem[]): string {
  const lines: string[] = [];
  const seen = new Set<string>();
  for (const { result } of items) {
    const license = getLicense(result.license_id);
    if (!license.requires_attribution || seen.has(result.attribution)) continue;
    seen.add(result.attribution);
    lines.push(`- ${result.attribution}\n  ${license.name} - ${result.license_url}\n  ${result.source_page_url}`);
  }
  return `${HEADER}\n${lines.length ? lines.join('\n') + '\n' : 'No attribution required for the assets in this library.\n'}`;
}

export function writeCredits(items: LibraryItem[], filePath: string): string {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, buildCredits(items), 'utf8');
  return filePath;
}
