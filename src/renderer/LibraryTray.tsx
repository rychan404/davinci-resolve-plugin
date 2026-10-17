import { useState } from 'react';
import { getLicense } from '../shared/licenses';
import type { LibraryItem } from '../shared/types';
import { librarySrc } from '../shared/urls';

const fileName = (localPath: string) => localPath.split(/[\\/]/).pop() ?? localPath;

function TrayTile(props: {
  item: LibraryItem;
  selected: boolean;
  onClick(e: React.MouseEvent): void;
  onDragStart(e: React.DragEvent): void;
}) {
  const { item, selected } = props;
  const [broken, setBroken] = useState(false);
  const { result } = item;
  return (
    <div
      className="tile tray-tile"
      data-testid="tray-item"
      data-selected={selected}
      draggable
      title={`${result.attribution}\n${getLicense(result.license_id).name}\n${result.source_page_url}`}
      onClick={props.onClick}
      onDragStart={props.onDragStart}
    >
      {broken ? (
        <span className="placeholder" />
      ) : (
        <img draggable={false} alt="" src={librarySrc(item.local_path)} onError={() => setBroken(true)} />
      )}
      <span className="label">{fileName(item.local_path)}</span>
    </div>
  );
}

export function LibraryTray({ items, onStartDrag }: { items: LibraryItem[]; onStartDrag(paths: string[]): void }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const click = (path: string, e: React.MouseEvent) =>
    setSelected((prev) => {
      if (!(e.ctrlKey || e.metaKey)) return new Set([path]);
      const next = new Set(prev);
      if (!next.delete(path)) next.add(path);
      return next;
    });

  const dragStart = (path: string, e: React.DragEvent) => {
    // Cancel the browser's own drag; main starts the native file drag instead.
    e.preventDefault();
    // Dragging a selected tile carries the whole selection, in tray order.
    const paths = selected.has(path) ? items.map((i) => i.local_path).filter((p) => selected.has(p)) : [path];
    onStartDrag(paths);
  };

  return (
    <div className="grid tray">
      {items.map((item) => (
        <TrayTile
          key={item.local_path}
          item={item}
          selected={selected.has(item.local_path)}
          onClick={(e) => click(item.local_path, e)}
          onDragStart={(e) => dragStart(item.local_path, e)}
        />
      ))}
    </div>
  );
}
