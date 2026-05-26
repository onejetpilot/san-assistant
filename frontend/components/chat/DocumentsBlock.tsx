import type { DocumentItem } from '../../lib/types';

export default function DocumentsBlock({ documents }: { documents?: DocumentItem[] }) {
  if (!documents || documents.length === 0) return null;
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-800">Документы</h3>
      <div className="space-y-2">
        {documents.map((d, i) => (
          <div key={i} className="rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs text-slate-700">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-slate-900">{d.title}</span>
              <span className="rounded border border-emerald-300 bg-emerald-100 px-1.5 py-0.5 text-[10px] uppercase text-emerald-800">{d.type}</span>
            </div>
            <div>{d.brand} · {d.product}</div>
            {d.public_url && (
              <a className="inline-block pt-1 text-sky-700 underline" href={d.public_url} target="_blank" rel="noreferrer">
                Открыть документ
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
