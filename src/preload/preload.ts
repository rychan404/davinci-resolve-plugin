import { contextBridge, ipcRenderer } from 'electron';
import type { Api } from '../shared/types';

type Reply<T> = { ok: true; value: T } | { ok: false; message: string };

async function call<T>(channel: string, ...args: unknown[]): Promise<T> {
  const reply: Reply<T> = await ipcRenderer.invoke(channel, ...args);
  if (!reply.ok) throw new Error(reply.message);
  return reply.value;
}

const api: Api = {
  getSources: () => call('get-sources'),
  search: (q) => call('search', q),
  download: (uid) => call('download', uid),
  listLibrary: () => call('list-library'),
  exportCredits: () => call('export-credits'),
  startDrag: (paths) => ipcRenderer.send('start-drag', paths),
};

contextBridge.exposeInMainWorld('api', api);
