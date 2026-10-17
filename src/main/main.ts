import { app, BrowserWindow, protocol } from 'electron';
import path from 'node:path';
import started from 'electron-squirrel-startup';
import { ResponseCache } from './cache';
import { loadConfig } from './config';
import { CachedHttp } from './http';
import { registerIpc } from './ipc';
import { Library } from './library';
import { Session } from './session';
import { buildRegistry } from './sources/registry';
import { ThumbnailFetcher } from './thumbnails';

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (started) {
  app.quit();
}

protocol.registerSchemesAsPrivileged(
  ['preview', 'library'].map((scheme) => ({
    scheme,
    privileges: { standard: true, secure: true, supportFetchAPI: true },
  })),
);

const createWindow = () => {
  const win = new BrowserWindow({
    width: 1100,
    height: 760,
    title: 'resolvestock',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Dropping a file on the window must not navigate away from the app.
  win.webContents.on('will-navigate', (event, url) => {
    // The dev server may reload the page; anything else (e.g. a dropped file) is refused.
    if (!(MAIN_WINDOW_VITE_DEV_SERVER_URL && url.startsWith(MAIN_WINDOW_VITE_DEV_SERVER_URL))) event.preventDefault();
  });
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));

  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    win.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(path.join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`));
  }
  return win;
};

app.whenReady().then(() => {
  const config = loadConfig();
  const cache = new ResponseCache(path.join(config.library_dir, '.cache', 'responses'));
  const library = new Library(config.library_dir);
  const session = new Session(buildRegistry(new CachedHttp(cache), config), library);
  const fetcher = new ThumbnailFetcher();

  const win = createWindow();
  registerIpc(win, session, library, fetcher);
});

// Quit when all windows are closed, on every platform.
app.on('window-all-closed', () => {
  app.quit();
});
