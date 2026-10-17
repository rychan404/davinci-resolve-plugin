/** Custom-scheme URLs shared by the renderer (builds them) and main (parses them). */

export const previewSrc = (generation: number, url: string): string =>
  // The generation rides in the path: Chromium rewrites a numeric host on a standard scheme as IPv4.
  `preview://thumb/${generation}?u=${encodeURIComponent(url)}`;

export function parsePreviewUrl(src: string): { generation: number; target: string } | null {
  try {
    const u = new URL(src);
    const generation = u.pathname.slice(1);
    if (u.protocol !== 'preview:' || u.hostname !== 'thumb' || !/^\d+$/.test(generation)) return null;
    const target = u.searchParams.get('u');
    if (!target) return null;
    const t = new URL(target);
    if (t.protocol !== 'http:' && t.protocol !== 'https:') return null;
    return { generation: Number(generation), target };
  } catch {
    return null;
  }
}

export function librarySrc(localPath: string): string {
  const name = localPath.split(/[\\/]/).pop() ?? '';
  return `library://asset/${encodeURIComponent(name)}`;
}

export function parseLibraryUrl(src: string): string | null {
  try {
    const u = new URL(src);
    if (u.protocol !== 'library:' || u.hostname !== 'asset') return null;
    return decodeURIComponent(u.pathname.slice(1)) || null;
  } catch {
    return null;
  }
}
