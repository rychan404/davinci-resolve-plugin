import type { SearchOutcome } from '../shared/types';

export function searchMessage(outcome: SearchOutcome): string {
  const message = `${outcome.results.length} result(s)`;
  const failed = Object.entries(outcome.errors).map(([name, error]) => `${name}: ${error}`);
  return failed.length ? `${message} — some sources failed — ${failed.join('; ')}` : message;
}

export function withProgress(message: string, resolved: number, total: number): string {
  return total > 0 && resolved < total ? `${message} — ${resolved}/${total} previews loaded` : message;
}
