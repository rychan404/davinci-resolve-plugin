// TEMPORARY wiring check (Task 9). Task 12 replaces this file.
import { useState } from 'react';
import { makeQuery, type LibraryItem, type SearchResult } from '../shared/types';
import { librarySrc, previewSrc } from '../shared/urls';

export function App() {
  const [shown, setShown] = useState<{ generation: number; results: SearchResult[] } | null>(null);
  const [item, setItem] = useState<LibraryItem | null>(null);
  const [error, setError] = useState('');

  const check = async () => {
    try {
      const response = await window.api.search(makeQuery('smoke'));
      setShown({ generation: response.generation, results: response.results.slice(0, 5) });
      setItem((await window.api.listLibrary())[0] ?? null);
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div>
      <h1>resolvestock</h1>
      <button onClick={check}>check wiring</button>
      <p>{error}</p>
      <div>
        {shown?.results.map((r) => (
          <img key={r.source_id} width={120} src={previewSrc(shown.generation, r.preview_url)} />
        ))}
      </div>
      {item && (
        <img
          width={120}
          draggable
          src={librarySrc(item.local_path)}
          onDragStart={(e) => {
            e.preventDefault();
            window.api.startDrag([item.local_path]);
          }}
        />
      )}
    </div>
  );
}
