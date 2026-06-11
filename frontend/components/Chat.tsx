'use client';

import { useEffect, useMemo, useState } from 'react';

type ChatResponse = {
  session_id?: string;
  request_id?: string;
  answer?: string;
  answer_mode?: string;
  confidence?: 'high' | 'medium' | 'low' | string;
  used_web_search?: boolean;
  tools_used?: string[];
  sources?: Array<{
    doc_id?: string;
    product?: string;
    brand?: string;
    category?: string;
    section?: string;
    source_file?: string;
    score?: number;
  }>;
  documents?: Array<{
    title?: string;
    type?: string;
    product?: string;
    brand?: string;
    public_url?: string;
  }>;
};

type Turn = {
  id: string;
  question: string;
  response: ChatResponse;
};

const SESSION_KEY = 'san_rag_session_id';

function confidenceTone(value?: string): string {
  if (value === 'high') return 'bg-emerald-100 text-emerald-800 border-emerald-200';
  if (value === 'medium') return 'bg-amber-100 text-amber-800 border-amber-200';
  return 'bg-rose-100 text-rose-800 border-rose-200';
}

export default function Chat() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);

  useEffect(() => {
    const sid = window.localStorage.getItem(SESSION_KEY);
    if (sid) setSessionId(sid);
  }, []);

  const canSend = useMemo(() => message.trim().length > 1 && !loading, [message, loading]);

  const send = async () => {
    if (!canSend) return;
    const userText = message.trim();
    setLoading(true);
    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: userText, answer_style: 'detailed' }),
      });
      const data: ChatResponse = await r.json();
      if (data.session_id) {
        window.localStorage.setItem(SESSION_KEY, data.session_id);
        setSessionId(data.session_id);
      }
      setTurns(prev => [...prev, { id: data.request_id || String(Date.now()), question: userText, response: data }]);
      setMessage('');
    } finally {
      setLoading(false);
    }
  };

  const newChat = () => {
    window.localStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setTurns([]);
    setMessage('');
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 rounded-2xl border border-slate-200 bg-white/90 p-5 shadow-sm backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">SAN Assistant</h1>
            <p className="text-sm text-slate-600">Внутренний консультант по сантехническим товарам</p>
          </div>
          <button className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50" onClick={newChat}>
            Новый чат
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.8fr,1fr]">
        <section className="space-y-4">
          {turns.length === 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-600 shadow-sm">
              Спроси про артикул, монтаж, гарантию, паспорт или подбор оборудования.
            </div>
          )}

          {turns.map((t) => (
            <article key={t.id} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="rounded-xl bg-slate-900 px-4 py-3 text-sm text-white">{t.question}</div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-800 whitespace-pre-wrap">
                {t.response.answer || 'Пустой ответ'}
              </div>

              <div className="flex flex-wrap gap-2">
                <span className={`rounded-md border px-2 py-1 text-xs font-medium ${confidenceTone(t.response.confidence)}`}>
                  confidence: {t.response.confidence || 'unknown'}
                </span>
                <span className="rounded-md border border-slate-200 bg-slate-100 px-2 py-1 text-xs text-slate-700">
                  mode: {t.response.answer_mode || 'n/a'}
                </span>
                {t.response.used_web_search && (
                  <span className="rounded-md border border-sky-200 bg-sky-100 px-2 py-1 text-xs text-sky-800">поиск san.team</span>
                )}
              </div>

              {t.response.sources && t.response.sources.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-slate-800">Источники</h3>
                  <div className="space-y-2">
                    {t.response.sources.slice(0, 5).map((s, idx) => (
                      <div key={`${t.id}-s-${idx}`} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-700">
                        {(s.product || 'Без продукта')} / {(s.section || 'section')} / {(s.source_file || 'file')}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {t.response.documents && t.response.documents.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-slate-800">Документы</h3>
                  <div className="space-y-2">
                    {t.response.documents.map((d, idx) => (
                      <div key={`${t.id}-d-${idx}`} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-700">
                        <div className="font-medium text-slate-900">{d.title || 'Документ'}</div>
                        <div>{d.brand || ''} {d.product || ''}</div>
                        {d.public_url && (
                          <a className="text-sky-700 underline" href={d.public_url} target="_blank" rel="noreferrer">Открыть</a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-1">
                <button
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                  onClick={() => navigator.clipboard.writeText(t.response.answer || '')}
                >
                  Скопировать ответ
                </button>
              </div>
            </article>
          ))}
        </section>

        <aside className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">Вопрос</label>
            <textarea
              className="min-h-[140px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800"
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="Например: Дай паспорт на OXF01612"
            />

            <button
              className="mt-3 w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
              onClick={send}
              disabled={!canSend}
            >
              {loading ? 'Отправка...' : 'Отправить'}
            </button>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600 shadow-sm">
            Session: <span className="font-mono text-slate-800">{sessionId || 'новая'}</span>
          </div>
        </aside>
      </div>
    </div>
  );
}
