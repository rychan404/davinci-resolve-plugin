// @vitest-environment jsdom
import { createEvent, fireEvent, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { LibraryTray } from '../src/renderer/LibraryTray';
import { librarySrc } from '../src/shared/urls';
import { makeResult } from './helpers';

const item = (name: string) => ({
  local_path: `C:\\lib\\${name}`,
  downloaded_at: '2026-10-17T00:00:00Z',
  result: makeResult(),
});

test('shows each library file with its attribution', () => {
  render(<LibraryTray items={[item('a.png')]} onStartDrag={vi.fn()} />);
  const tile = screen.getByTestId('tray-item');
  expect(tile.textContent).toContain('a.png');
  expect(tile.title).toContain('Smoke by Jane');
  expect(tile.title).toContain('CC BY 4.0');
  expect(tile.querySelector('img')!.getAttribute('src')).toBe(librarySrc('C:\\lib\\a.png'));
});

test('dragging a tile starts a native drag of that file', () => {
  const onStartDrag = vi.fn();
  render(<LibraryTray items={[item('a.png'), item('b.png')]} onStartDrag={onStartDrag} />);
  const event = createEvent.dragStart(screen.getAllByTestId('tray-item')[1]);
  fireEvent(screen.getAllByTestId('tray-item')[1], event);
  expect(event.defaultPrevented).toBe(true);
  expect(onStartDrag).toHaveBeenCalledWith(['C:\\lib\\b.png']);
});

test('dragging a selected tile carries the whole selection', () => {
  const onStartDrag = vi.fn();
  render(<LibraryTray items={[item('a.png'), item('b.png'), item('c.png')]} onStartDrag={onStartDrag} />);
  const [a, b, c] = screen.getAllByTestId('tray-item');
  fireEvent.click(a);
  fireEvent.click(b, { ctrlKey: true });
  fireEvent.dragStart(a);
  expect(onStartDrag).toHaveBeenLastCalledWith(['C:\\lib\\a.png', 'C:\\lib\\b.png']);
  fireEvent.dragStart(c);
  expect(onStartDrag).toHaveBeenLastCalledWith(['C:\\lib\\c.png']);
});
