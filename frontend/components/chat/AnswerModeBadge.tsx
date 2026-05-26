export default function AnswerModeBadge({ mode }: { mode?: string }) {
  return <span className="rounded-md border border-slate-200 bg-slate-100 px-2 py-1 text-xs text-slate-700">mode: {mode || 'n/a'}</span>;
}
