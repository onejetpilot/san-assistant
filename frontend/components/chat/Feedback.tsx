'use client';

import { useState } from 'react';
import { sendFeedback } from '../../lib/api';

export default function Feedback({ requestId }: { requestId?: string }) {
  const [mode, setMode] = useState<'idle' | 'down' | 'done'>('idle');
  const [comment, setComment] = useState('');
  if (!requestId) return null;

  return (
    <div className="pt-2">
      <div className="flex items-center gap-2">
        <button
          className="rounded-lg border border-slate-300 px-2 py-1 text-xs transition hover:bg-slate-50"
          onClick={async () => {
            await sendFeedback({ request_id: requestId, rating: 'up', comment: '' });
            setMode('done');
          }}
        >
          👍
        </button>
        <button className="rounded-lg border border-slate-300 px-2 py-1 text-xs transition hover:bg-slate-50" onClick={() => setMode('down')}>
          👎
        </button>
      </div>

      {mode === 'down' && (
        <div className="mt-2 space-y-2">
          <textarea
            className="w-full rounded-lg border border-slate-300 px-2 py-1 text-xs outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Что было не так?"
          />
          <button
            className="rounded-lg border border-slate-300 px-2 py-1 text-xs transition hover:bg-slate-50"
            onClick={async () => {
              await sendFeedback({ request_id: requestId, rating: 'down', comment });
              setMode('done');
            }}
          >
            Отправить
          </button>
        </div>
      )}

      {mode === 'done' && <p className="mt-2 text-xs text-emerald-700">Спасибо, оценка сохранена.</p>}
    </div>
  );
}
