'use client';

import type { AnswerStyle } from '../../lib/types';

export default function ChatInput({
  value,
  setValue,
  loading,
  onSend,
  answerStyle,
  setAnswerStyle,
}: {
  value: string;
  setValue: (v: string) => void;
  loading: boolean;
  onSend: () => void;
  answerStyle: AnswerStyle;
  setAnswerStyle: (v: AnswerStyle) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-300 bg-white p-2">
      <div className="mb-2 flex items-center justify-between px-1">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Стиль ответа</label>
        <select
          className="rounded-md border border-slate-300 bg-slate-50 px-2 py-1 text-xs"
          value={answerStyle}
          onChange={(e) => setAnswerStyle(e.target.value as AnswerStyle)}
        >
          <option value="short">Кратко</option>
          <option value="detailed">Подробно</option>
        </select>
      </div>

      <textarea
        className="min-h-[88px] w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        placeholder="Напишите вопрос по сантехническим товарам"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        }}
      />

      <button
        className="mt-2 w-full rounded-lg bg-gradient-to-r from-sky-600 to-cyan-500 px-4 py-2 text-sm font-medium text-white transition hover:from-sky-500 hover:to-cyan-400 disabled:opacity-50"
        disabled={loading || value.trim().length < 2}
        onClick={onSend}
      >
        {loading ? 'Отправка...' : 'Отправить'}
      </button>
    </div>
  );
}
