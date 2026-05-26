import { cn } from '../../lib/utils';

export default function MessageBubble({ role, content }: { role: 'user' | 'assistant'; content: string }) {
  return (
    <div className={cn('rounded-xl px-4 py-3 text-sm', role === 'user' ? 'bg-slate-900 text-white' : 'border border-slate-200 bg-slate-50 text-slate-800 whitespace-pre-wrap')}>
      {content}
    </div>
  );
}
