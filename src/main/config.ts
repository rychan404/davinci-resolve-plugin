import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export interface Config {
  path: string;
  pixabay_key: string | null;
  library_dir: string;
}

export function loadConfig(
  configPath: string = path.join(os.homedir(), '.resolvestock', 'config.json'),
  home: string = os.homedir(),
): Config {
  const defaults: Config = { path: configPath, pixabay_key: null, library_dir: path.join(home, 'ResolveStock') };
  let data: unknown;
  try {
    data = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch {
    return defaults;
  }
  if (typeof data !== 'object' || data === null || Array.isArray(data)) return defaults;
  const { pixabay_key, library_dir } = data as Record<string, unknown>;
  return {
    path: configPath,
    pixabay_key: typeof pixabay_key === 'string' && pixabay_key ? pixabay_key : null,
    library_dir: typeof library_dir === 'string' && library_dir ? library_dir : defaults.library_dir,
  };
}
