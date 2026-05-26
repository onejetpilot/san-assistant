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
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Стиль ответа</label>
        <select
          className="rounded border border-slate-300 px-2 py-1 text-xs"
          value={answerStyle}
          onChange={(e) => setAnswerStyle(e.target.value as AnswerStyle)}
        >
          <option value="short">Кратко</option>
          <option value="detailed">Подробно</option>
        </select>
      </div>

      <textarea
        className="min-h-[110px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
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
        className="mt-3 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        disabled={loading || value.trim().length < 2}
        onClick={onSend}
      >
        {loading ? 'Отправка...' : 'Отправить'}
      </button>
    </div>
  );
}
