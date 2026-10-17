// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import { ResultsGrid } from '../src/renderer/ResultsGrid';
import { previewSrc } from '../src/shared/urls';
import { intersect, installFakeIntersectionObserver, lastObserverOptions } from './intersection';
import { makeResult } from './helpers';

beforeEach(installFakeIntersectionObserver);

test('tiles load their preview only once near the viewport', () => {
  const progress = vi.fn();
  render(<ResultsGrid results={[makeResult()]} generation={4} onDownload={vi.fn()} onProgress={progress} />);
  const tile = screen.getByTestId('tile');
  expect(tile.dataset.state).toBe('idle');
  expect(tile.querySelector('img')?.getAttribute('src')).toBeNull();
  expect(lastObserverOptions().rootMargin).toBe('200px 0px');
  act(() => intersect(tile));
  expect(tile.querySelector('img')!.getAttribute('src')).toBe(previewSrc(4, 'https://example.invalid/preview.png'));
  expect(progress).toHaveBeenLastCalledWith(0, 1);
  fireEvent.load(tile.querySelector('img')!);
  expect(tile.dataset.state).toBe('loaded');
  expect(progress).toHaveBeenLastCalledWith(1, 1);
});

test('a failed preview explains itself', () => {
  render(<ResultsGrid results={[makeResult()]} generation={1} onDownload={vi.fn()} onProgress={vi.fn()} />);
  const tile = screen.getByTestId('tile');
  act(() => intersect(tile));
  fireEvent.error(tile.querySelector('img')!);
  expect(tile.dataset.state).toBe('failed');
  expect(tile.title).toContain('Thumbnail unavailable');
});

test('a result with no preview is failed and already counted', () => {
  const progress = vi.fn();
  render(
    <ResultsGrid results={[makeResult({ preview_url: '' })]} generation={1} onDownload={vi.fn()} onProgress={progress} />,
  );
  expect(screen.getByTestId('tile').dataset.state).toBe('failed');
  expect(screen.getByTestId('tile').title).toContain('This result has no preview image.');
  expect(progress).toHaveBeenLastCalledWith(1, 1);
});

test('tooltip shows size, license and source page', () => {
  render(<ResultsGrid results={[makeResult()]} generation={1} onDownload={vi.fn()} onProgress={vi.fn()} />);
  const title = screen.getByTestId('tile').title;
  expect(title).toContain('100x100');
  expect(title).toContain('CC BY 4.0');
  expect(title).toContain('https://example.invalid/page');
});

test('double click downloads; tiles are not drag sources', () => {
  const onDownload = vi.fn();
  render(<ResultsGrid results={[makeResult({ source: 'a' })]} generation={1} onDownload={onDownload} onProgress={vi.fn()} />);
  const tile = screen.getByTestId('tile');
  fireEvent.doubleClick(tile);
  expect(onDownload).toHaveBeenCalledWith('a:1');
  expect(tile.getAttribute('draggable')).toBe('false');
});

test('new results reset progress', () => {
  const progress = vi.fn();
  const { rerender } = render(
    <ResultsGrid results={[makeResult()]} generation={1} onDownload={vi.fn()} onProgress={progress} />,
  );
  act(() => intersect(screen.getByTestId('tile')));
  rerender(
    <ResultsGrid
      results={[makeResult({ source_id: '2' }), makeResult({ source_id: '3' })]}
      generation={2}
      onDownload={vi.fn()}
      onProgress={progress}
    />,
  );
  expect(progress).toHaveBeenLastCalledWith(0, 0);
});
