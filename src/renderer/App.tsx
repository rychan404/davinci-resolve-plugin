import { useEffect, useRef, useState } from 'react';
import { makeQuery, type Api, type LibraryItem, type SearchResult } from '../shared/types';
import { LibraryTray } from './LibraryTray';
import { ResultsGrid } from './ResultsGrid';
import { searchMessage, withProgress } from './status';

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function App({ api }: { api: Api }) {
  const [text, setText] = useState('');
  const [filters, setFilters] = useState({
    transparent_only: false,
    vectors_only: false,
    photos_only: false,
    commercial_safe_only: true,
  });
  const [sources, setSources] = useState<string[] | null>(null);
  const [tab, setTab] = useState<string | null>(null);
  const [shown, setShown] = useState<{ generation: number; results: SearchResult[] }>({ generation: 0, results: [] });
  const [trayItems, setTrayItems] = useState<LibraryItem[]>([]);
  const [status, setStatus] = useState('ready');

  // Only the newest search may update the grid.
  const latestSearch = useRef(0);
  // The last search message, or null while a search is in flight or before the first one.
  const searchText = useRef<string | null>(null);

  const refreshTray = () => api.listLibrary().then(setTrayItems, (e) => setStatus(`failed: ${errorText(e)}`));

  useEffect(() => {
    api.getSources().then(setSources, (e) => setStatus(`failed: ${errorText(e)}`));
    refreshTray();
  }, []);

  const runSearch = async (source: string | null) => {
    const term = text.trim();
    if (!term) {
      setStatus('enter a search term');
      return;
    }
    const mine = ++latestSearch.current;
    searchText.current = null;
    setStatus('searching...');
    try {
      const response = await api.search(makeQuery(term, { ...filters, source }));
      if (mine !== latestSearch.current) return;
      const message = searchMessage(response);
      searchText.current = message;
      setStatus(message);
      setShown({ generation: response.generation, results: response.results });
    } catch (e) {
      if (mine === latestSearch.current) setStatus(`failed: ${errorText(e)}`);
    }
  };

  const selectTab = (name: string | null) => {
    setTab(name);
    // An empty box would only overwrite the status, so leave everything alone.
    if (text.trim()) runSearch(name);
  };

  const download = async (uid: string) => {
    const title = shown.results.find((r) => `${r.source}:${r.source_id}` === uid)?.title ?? uid;
    setStatus(`downloading ${title}...`);
    try {
      const item = await api.download(uid);
      setStatus(`saved ${item.local_path.split(/[\\/]/).pop()}`);
      refreshTray();
    } catch (e) {
      setStatus(`failed: ${errorText(e)}`);
    }
  };

  const exportCredits = async () => {
    try {
      const written = await api.exportCredits();
      if (written) setStatus(`credits written to ${written}`);
    } catch (e) {
      setStatus(`failed: ${errorText(e)}`);
    }
  };

  const toggle = (key: keyof typeof filters, label: string) => (
    <label>
      <input
        type="checkbox"
        checked={filters[key]}
        onChange={(e) => setFilters({ ...filters, [key]: e.target.checked })}
      />
      {label}
    </label>
  );

  return (
    <div className="app">
      <div className="row">
        <input
          type="text"
          placeholder="search cutouts and vectors"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && runSearch(tab)}
        />
        <button onClick={() => runSearch(tab)}>Search</button>
      </div>
      <div className="row">
        {toggle('transparent_only', 'Transparent only')}
        {toggle('vectors_only', 'Vectors only')}
        {toggle('photos_only', 'Photos only')}
      </div>
      <div className="row">
        {toggle('commercial_safe_only', 'Commercial-safe only')}
        <span className="spacer" />
        <button onClick={exportCredits}>Export credits</button>
      </div>
      {sources && (
        <div className="tabs" role="tablist">
          {[null, ...sources].map((name) => (
            <button
              key={name ?? 'all'}
              role="tab"
              aria-selected={tab === name}
              onClick={() => selectTab(name)}
            >
              {name ? capitalize(name) : 'All'}
            </button>
          ))}
        </div>
      )}
      <div className="caption">Results — double click to download</div>
      <div className="results">
        <ResultsGrid
          results={shown.results}
          generation={shown.generation}
          onDownload={download}
          onProgress={(resolved, total) => {
            if (searchText.current !== null) setStatus(withProgress(searchText.current, resolved, total));
          }}
        />
      </div>
      <div className="caption">Library — drag into Resolve's media pool</div>
      <div className="tray-panel">
        <LibraryTray items={trayItems} onStartDrag={api.startDrag} />
      </div>
      <div className="status" role="status">
        {status}
      </div>
    </div>
  );
}
