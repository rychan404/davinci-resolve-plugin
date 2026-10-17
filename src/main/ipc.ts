import { dialog, ipcMain, nativeImage, net, protocol, type BrowserWindow } from 'electron';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseLibraryUrl, parsePreviewUrl } from '../shared/urls';
import { writeCredits } from './credits';
import type { Library } from './library';
import type { Session } from './session';
import type { ThumbnailFetcher } from './thumbnails';

type Reply<T> = { ok: true; value: T } | { ok: false; message: string };

/** Errors travel as data so the page sees the bare message, not Electron's invoke prefix. */
function handle<T>(channel: string, fn: (...args: any[]) => T | Promise<T>): void {
  ipcMain.handle(channel, async (_event, ...args): Promise<Reply<T>> => {
    try {
      return { ok: true, value: await fn(...args) };
    } catch (error) {
      return { ok: false, message: error instanceof Error ? error.message : String(error) };
    }
  });
}

export function registerIpc(win: BrowserWindow, session: Session, library: Library, fetcher: ThumbnailFetcher): void {
  handle('get-sources', () => session.sourceNames());
  handle('search', (q) => session.search(q));
  handle('download', (uid) => session.download(String(uid)));
  handle('list-library', () => library.items());
  handle('export-credits', async () => {
    const { canceled, filePath } = await dialog.showSaveDialog(win, {
      title: 'Export credits',
      defaultPath: 'CREDITS.txt',
      filters: [{ name: 'Text files', extensions: ['txt'] }],
    });
    return canceled || !filePath ? null : writeCredits(library.items(), filePath);
  });

  protocol.handle('preview', async (request) => {
    const parsed = parsePreviewUrl(request.url);
    if (!parsed) return new Response('bad preview url', { status: 400 });
    // A newer search replaced these tiles; refuse without touching the network.
    if (!session.isCurrent(parsed.generation)) return new Response('superseded', { status: 410 });
    try {
      const { body, contentType } = await fetcher.fetch(parsed.target, () => session.isCurrent(parsed.generation));
      return new Response(body, { headers: { 'Content-Type': contentType } });
    } catch (error) {
      return new Response(error instanceof Error ? error.message : String(error), { status: 502 });
    }
  });

  protocol.handle('library', (request) => {
    const name = parseLibraryUrl(request.url);
    const file = name === null ? null : path.join(library.root, name);
    if (file === null || !library.contains(file)) return new Response('not found', { status: 404 });
    return net.fetch(pathToFileURL(file).toString());
  });

  ipcMain.on('start-drag', (event, requested: unknown) => {
    if (!Array.isArray(requested)) return;
    const paths = requested.filter((p): p is string => typeof p === 'string' && library.contains(p));
    if (paths.length === 0) return;
    let icon = nativeImage.createFromPath(paths[0]);
    // nativeImage cannot load SVG, and macOS refuses an empty drag icon.
    icon = icon.isEmpty()
      ? nativeImage.createFromBitmap(Buffer.alloc(32 * 32 * 4, 128), { width: 32, height: 32 })
      : icon.resize({ width: 64 });
    event.sender.startDrag({ file: paths[0], files: paths, icon });
  });
}
