import { cn } from '../../lib/utils';

export default function MessageBubble({ role, content }: { role: 'user' | 'assistant'; content: string }) {
  const looksLikeHtml = content.includes('<html') || content.includes('<!DOCTYPE');
  const safeContent = looksLikeHtml
    ? 'Backend вернул HTML вместо JSON. Проверь NEXT_PUBLIC_API_BASE_URL или прокси /api -> backend.'
    : content;

  return (
    <div
      className={cn(
        'inline-block w-fit max-w-full rounded-xl px-4 py-3 text-sm leading-6',
        role === 'user'
          ? 'ml-auto max-w-[88%] bg-slate-900 text-white'
          : 'max-w-[95%] border border-slate-200 bg-slate-50 text-slate-800 whitespace-pre-wrap',
      )}
    >
      {safeContent}
    </div>
  );
}
