'use client';

import { useEffect, useState } from 'react';
import { chat, clearAccessToken, ApiError } from '../../lib/api';
import { clearSessionId, getSessionId, setSessionId } from '../../lib/storage';
import type { AnswerStyle, Message } from '../../lib/types';
import TokenGate from '../auth/TokenGate';
import ChatInput from './ChatInput';
import MessageBubble from './MessageBubble';
import AssistantMessage from './AssistantMessage';

export default function ChatLayout() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setLocalSessionId] = useState<string | null>(null);
  const [answerStyle, setAnswerStyle] = useState<AnswerStyle>('detailed');
  const [needsToken, setNeedsToken] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLocalSessionId(getSessionId());
  }, []);

  const onSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setError(null);
    setLoading(true);
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');

    try {
      const res = await chat({ session_id: sessionId, message: text, answer_style: answerStyle });
      if (res.session_id) {
        setSessionId(res.session_id);
        setLocalSessionId(res.session_id);
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          request_id: res.request_id,
          sources: res.sources,
          documents: res.documents,
          web_results: res.web_results,
          confidence: res.confidence,
          used_web_search: res.used_web_search,
          tools_used: res.tools_used,
          answer_mode: res.answer_mode,
        },
      ]);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setNeedsToken(true);
      } else {
        setError(e instanceof Error ? e.message : 'Ошибка запроса');
      }
    } finally {
      setLoading(false);
    }
  };

  if (needsToken) {
    return <TokenGate onSaved={() => setNeedsToken(false)} />;
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">SAN Assistant</h1>
            <div className="mt-1 inline-flex rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600">Internal RAG Assistant</div>
          </div>
          <div className="flex gap-2">
            <button
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                clearSessionId();
                setLocalSessionId(null);
                setMessages([]);
              }}
            >
              Новый чат
            </button>
            <button
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => setNeedsToken(true)}
            >
              Сменить токен
            </button>
            <button
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                clearAccessToken();
                setNeedsToken(true);
              }}
            >
              Выйти
            </button>
          </div>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1.8fr,1fr]">
        <section className="space-y-4">
          {messages.length === 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
              Задай вопрос по товару, артикулу, документу, монтажу или гарантии.
            </div>
          )}

          {messages.map((m, idx) => (
            <article key={idx} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              {m.role === 'user' ? <MessageBubble role="user" content={m.content} /> : <AssistantMessage message={m} />}
            </article>
          ))}

          {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
        </section>

        <aside className="space-y-4">
          <ChatInput
            value={input}
            setValue={setInput}
            loading={loading}
            onSend={onSend}
            answerStyle={answerStyle}
            setAnswerStyle={setAnswerStyle}
          />

          <div className="rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600 shadow-sm">
            session_id: <span className="font-mono text-slate-800">{sessionId || 'null'}</span>
          </div>
        </aside>
      </div>
    </div>
  );
}
