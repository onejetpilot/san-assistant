import type { SourceItem } from '../../lib/types';

export default function SourcesBlock({ sources }: { sources?: SourceItem[] }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-slate-800">Источники</h3>
      <div className="space-y-2">
        {sources.map((s, i) => (
          <div key={i} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-700">
            <div className="font-medium text-slate-900">{s.product} / {s.section}</div>
            <div>{s.brand} · {s.category}</div>
            <div className="text-slate-500">{s.source_file}{typeof s.score === 'number' ? ` · score: ${s.score.toFixed(2)}` : ''}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
