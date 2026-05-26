import { cn } from '../../lib/utils';

export default function ConfidenceBadge({ value }: { value?: 'high' | 'medium' | 'low' }) {
  const style =
    value === 'high'
      ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
      : value === 'medium'
      ? 'bg-amber-100 text-amber-800 border-amber-200'
      : 'bg-rose-100 text-rose-800 border-rose-200';
  return <span className={cn('rounded-md border px-2 py-1 text-xs font-medium', style)}>confidence: {value || 'low'}</span>;
}
