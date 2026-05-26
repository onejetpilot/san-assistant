import type { WebResultItem } from '../../lib/types';

export default function WebResultsBlock({ webResults }: { webResults?: WebResultItem[] }) {
  if (!webResults || webResults.length === 0) return null;
  return (
    <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-800">Результаты san.team</h3>
      <div className="space-y-2">
        {webResults.map((r, i) => (
          <div key={i} className="rounded-lg border border-sky-200 bg-white px-3 py-2 text-xs text-slate-700">
            <a className="font-medium text-sky-700 underline" href={r.url} target="_blank" rel="noreferrer">
              {r.title}
            </a>
            <div>{r.snippet}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
