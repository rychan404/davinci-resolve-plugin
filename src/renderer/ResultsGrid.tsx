import { useEffect, useRef, useState } from 'react';
import { getLicense } from '../shared/licenses';
import { uidOf, type SearchResult } from '../shared/types';
import { previewSrc } from '../shared/urls';

type TileState = 'idle' | 'pending' | 'loaded' | 'failed';

const NO_PREVIEW = 'This result has no preview image.';
const LOAD_FAILED = 'The preview could not be loaded.';
// Plain loading="lazy" was rejected: Chromium picks its own, much larger margin.
const PRELOAD_MARGIN = '200px 0px';

interface Model {
  states: Record<string, TileState>;
  reasons: Record<string, string>;
}

function initialModel(results: SearchResult[]): Model {
  const model: Model = { states: {}, reasons: {} };
  for (const r of results) {
    // A result with no preview never reaches the loader, so it counts as requested and resolved.
    model.states[uidOf(r)] = r.preview_url ? 'idle' : 'failed';
    if (!r.preview_url) model.reasons[uidOf(r)] = NO_PREVIEW;
  }
  return model;
}

function tooltip(r: SearchResult, reason?: string): string {
  const size = r.width && r.height ? `${r.width}x${r.height}` : 'size unknown';
  const text = `${r.title}\n${size}\n${getLicense(r.license_id).name}\nalpha=${r.has_alpha}\n${r.source_page_url}`;
  return reason ? `${text}\n\nThumbnail unavailable: ${reason}` : text;
}

interface TileProps {
  result: SearchResult;
  generation: number;
  state: TileState;
  reason?: string;
  onNear(): void;
  onSettled(state: 'loaded' | 'failed', reason?: string): void;
  onDownload(uid: string): void;
}

function Tile({ result, generation, state, reason, onNear, onSettled, onDownload }: TileProps) {
  const ref = useRef<HTMLDivElement>(null);
  const near = useRef(onNear);
  near.current = onNear;

  useEffect(() => {
    if (state !== 'idle' || !ref.current) return;
    if (typeof IntersectionObserver === 'undefined') {
      near.current();
      return;
    }
    // Each tile watches itself once, so a preview is never requested twice.
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          observer.disconnect();
          near.current();
        }
      },
      { rootMargin: PRELOAD_MARGIN },
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [state]);

  return (
    <div
      ref={ref}
      className="tile"
      data-testid="tile"
      data-state={state}
      draggable={false}
      title={tooltip(result, state === 'failed' ? reason : undefined)}
      onDoubleClick={() => onDownload(uidOf(result))}
    >
      <img
        draggable={false}
        alt=""
        src={state === 'idle' || !result.preview_url ? undefined : previewSrc(generation, result.preview_url)}
        onLoad={() => onSettled('loaded')}
        onError={() => onSettled('failed', LOAD_FAILED)}
      />
      <span className="label">
        {result.title}
        <br />[{result.source}]
      </span>
    </div>
  );
}

export function ResultsGrid(props: {
  results: SearchResult[];
  generation: number;
  onDownload(uid: string): void;
  onProgress(resolved: number, total: number): void;
}) {
  const { results, generation, onDownload } = props;
  const [model, setModel] = useState(() => initialModel(results));
  const [seen, setSeen] = useState(results);
  if (seen !== results) {
    setSeen(results);
    setModel(initialModel(results));
  }

  const onProgress = useRef(props.onProgress);
  onProgress.current = props.onProgress;
  useEffect(() => {
    const states = Object.values(model.states);
    onProgress.current(
      states.filter((s) => s === 'loaded' || s === 'failed').length,
      states.filter((s) => s !== 'idle').length,
    );
  }, [model]);

  const update = (uid: string, state: TileState, reason?: string) =>
    setModel((m) =>
      m.states[uid] === undefined
        ? m
        : { states: { ...m.states, [uid]: state }, reasons: reason ? { ...m.reasons, [uid]: reason } : m.reasons },
    );

  return (
    <div className="grid">
      {results.map((r) => {
        const uid = uidOf(r);
        return (
          <Tile
            key={`${generation}:${uid}`}
            result={r}
            generation={generation}
            state={model.states[uid] ?? 'idle'}
            reason={model.reasons[uid]}
            onNear={() => update(uid, 'pending')}
            onSettled={(state, reason) => update(uid, state, reason)}
            onDownload={onDownload}
          />
        );
      })}
    </div>
  );
}
