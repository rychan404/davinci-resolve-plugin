// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import { App } from '../src/renderer/App';
import { makeQuery, type Api, type SearchResponse } from '../src/shared/types';
import { installFakeIntersectionObserver } from './intersection';
import { makeResult } from './helpers';

beforeEach(installFakeIntersectionObserver);

const fakeApi = (overrides: Partial<Record<keyof Api, unknown>> = {}): Api =>
  ({
    getSources: vi.fn().mockResolvedValue(['openverse', 'wikimedia']),
    search: vi.fn().mockResolvedValue({ generation: 1, results: [makeResult()], errors: {} }),
    download: vi.fn(),
    listLibrary: vi.fn().mockResolvedValue([]),
    exportCredits: vi.fn().mockResolvedValue(null),
    startDrag: vi.fn(),
    ...overrides,
  }) as unknown as Api;

const type = async (text: string) =>
  fireEvent.change(screen.getByPlaceholderText('search cutouts and vectors'), { target: { value: text } });

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

test('starts ready with a tab per configured source', async () => {
  render(<App api={fakeApi()} />);
  expect(await screen.findAllByRole('tab')).toHaveLength(3);
  expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['All', 'Openverse', 'Wikimedia']);
  expect(screen.getByRole('status').textContent).toBe('ready');
});

test('a blank search stays local', async () => {
  const api = fakeApi();
  render(<App api={api} />);
  await type('   ');
  fireEvent.click(screen.getByText('Search'));
  expect(screen.getByRole('status').textContent).toBe('enter a search term');
  expect(api.search).not.toHaveBeenCalled();
});

test('search sends the filters and reports the outcome', async () => {
  const api = fakeApi();
  render(<App api={api} />);
  await type('smoke');
  fireEvent.click(screen.getByLabelText('Transparent only'));
  fireEvent.keyDown(screen.getByPlaceholderText('search cutouts and vectors'), { key: 'Enter' });
  expect(api.search).toHaveBeenCalledWith(makeQuery('smoke', { transparent_only: true }));
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('1 result(s)'));
});

test('switching tabs re-runs a non-empty search against that source', async () => {
  const api = fakeApi();
  render(<App api={api} />);
  await type('smoke');
  fireEvent.click(await screen.findByText('Wikimedia'));
  expect(api.search).toHaveBeenLastCalledWith(makeQuery('smoke', { source: 'wikimedia' }));
  fireEvent.click(screen.getByText('All'));
  expect(api.search).toHaveBeenLastCalledWith(makeQuery('smoke', { source: null }));
});

test('switching tabs with no text does nothing', async () => {
  const api = fakeApi();
  render(<App api={api} />);
  fireEvent.click(await screen.findByText('Wikimedia'));
  expect(api.search).not.toHaveBeenCalled();
  expect(screen.getByRole('status').textContent).toBe('ready');
});

test('a slower, older search never overwrites a newer one', async () => {
  const first = deferred<SearchResponse>();
  const api = fakeApi({
    search: vi
      .fn()
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce({ generation: 2, results: [makeResult({ title: 'New' })], errors: {} }),
  });
  render(<App api={api} />);
  await type('a');
  fireEvent.click(screen.getByText('Search'));
  expect(screen.getByRole('status').textContent).toBe('searching...');
  await type('b');
  fireEvent.click(screen.getByText('Search'));
  await screen.findByText(/New/);
  first.resolve({ generation: 1, results: [makeResult({ title: 'Old' })], errors: {} });
  await new Promise((r) => setTimeout(r));
  expect(screen.queryByText(/Old/)).toBeNull();
});

test('download reports progress, refreshes the tray, and shows failures', async () => {
  const api = fakeApi({
    download: vi
      .fn()
      .mockResolvedValueOnce({ local_path: 'C:\\lib\\smoke_plume_source_1.png', downloaded_at: '', result: makeResult() })
      .mockRejectedValueOnce(new Error('unknown result')),
  });
  render(<App api={api} />);
  await type('smoke');
  fireEvent.click(screen.getByText('Search'));
  fireEvent.doubleClick(await screen.findByTestId('tile'));
  expect(screen.getByRole('status').textContent).toBe('downloading Smoke Plume...');
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('saved smoke_plume_source_1.png'));
  expect(api.listLibrary).toHaveBeenCalledTimes(2);
  fireEvent.doubleClick(screen.getByTestId('tile'));
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('failed: unknown result'));
});

test('export credits reports where it wrote, and stays quiet when cancelled', async () => {
  const api = fakeApi({
    exportCredits: vi.fn().mockResolvedValueOnce('C:\\out\\CREDITS.txt').mockResolvedValueOnce(null),
  });
  render(<App api={api} />);
  fireEvent.click(screen.getByText('Export credits'));
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('credits written to C:\\out\\CREDITS.txt'));
  fireEvent.click(screen.getByText('Export credits'));
  await new Promise((r) => setTimeout(r));
  expect(screen.getByRole('status').textContent).toBe('credits written to C:\\out\\CREDITS.txt');
});
