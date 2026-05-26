'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { chat, clearAccessToken, ApiError } from '../../lib/api';
import { clearSessionId, getSessionId, setSessionId } from '../../lib/storage';
import type { AnswerStyle, Message } from '../../lib/types';
import TokenGate from '../auth/TokenGate';
import ChatInput from './ChatInput';
import MessageBubble from './MessageBubble';
import AssistantMessage from './AssistantMessage';

function shortSession(value: string | null): string {
  if (!value) return 'session';
  return value.slice(0, 8);
}

export default function ChatLayout() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setLocalSessionId] = useState<string | null>(null);
  const [answerStyle, setAnswerStyle] = useState<AnswerStyle>('detailed');
  const [needsToken, setNeedsToken] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [followScroll, setFollowScroll] = useState(true);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setLocalSessionId(getSessionId());
  }, []);

  useEffect(() => {
    const el = listRef.current;
    if (!el || !followScroll) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, loading, followScroll]);

  const inputLength = useMemo(() => input.length, [input]);

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
    <div className="mx-auto w-full max-w-7xl px-3 py-4 sm:px-4 sm:py-6">
      <div className="overflow-hidden rounded-2xl border border-slate-300 bg-white/70 shadow-2xl backdrop-blur">
        <div className="grid min-h-[86vh] grid-cols-1 lg:grid-cols-[280px_1fr]">
          <aside className="border-b border-slate-200 bg-slate-950 px-4 py-4 text-slate-100 lg:border-b-0 lg:border-r lg:border-r-slate-800">
            <div className="rounded-xl border border-slate-700 bg-slate-900 p-3">
              <div className="flex items-center gap-3">
                <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-sky-400 to-cyan-300" />
                <div>
                  <h1 className="text-sm font-semibold">SAN Assistant</h1>
                  <p className="text-xs text-slate-400">Консультант по сантехнике</p>
                </div>
              </div>
            </div>

            <div className="mt-3 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  Session
                </span>
                <span className="font-mono">{shortSession(sessionId)}</span>
              </div>
            </div>

            <div className="mt-3 grid gap-2">
              <button
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-left text-sm hover:bg-slate-800"
                onClick={() => {
                  clearSessionId();
                  setLocalSessionId(null);
                  setMessages([]);
                  setError(null);
                }}
              >
                Новый чат
              </button>
              <button
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-left text-sm hover:bg-slate-800"
                onClick={() => setNeedsToken(true)}
              >
                Сменить токен
              </button>
              <button
                className="rounded-lg border border-rose-800 bg-rose-950/40 px-3 py-2 text-left text-sm text-rose-100 hover:bg-rose-900/40"
                onClick={() => {
                  clearAccessToken();
                  setNeedsToken(true);
                }}
              >
                Выйти
              </button>
            </div>
          </aside>

          <section className="grid min-h-0 grid-rows-[auto_1fr_auto] bg-gradient-to-b from-slate-50 to-slate-100">
            <header className="border-b border-slate-200 bg-white/70 px-4 py-3 backdrop-blur">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">Чат SAN Assistant</h2>
                  <p className="text-xs text-slate-500">SKU lookup · RAG · документы · san.team fallback</p>
                </div>
                <span className="rounded-full border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600">
                  {loading ? 'Генерация ответа...' : 'Готов к запросу'}
                </span>
              </div>
            </header>

            <main
              ref={listRef}
              className="min-h-0 space-y-3 overflow-y-auto px-3 py-3 sm:px-4"
              onScroll={(e) => {
                const el = e.currentTarget;
                const nearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
                setFollowScroll(nearBottom);
              }}
            >
              {messages.length === 0 && (
                <div className="max-w-3xl rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                  Привет. Помогу с подбором и проверкой сантехнических товаров. Можно писать название, задачу или точный артикул.
                </div>
              )}

              {messages.map((m, idx) => (
                <div key={idx} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                  <div className="max-w-[92%] sm:max-w-[86%]">
                    {m.role === 'user' ? <MessageBubble role="user" content={m.content} /> : <AssistantMessage message={m} />}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-600">
                    <span>SAN Assistant печатает</span>
                    <span className="flex gap-1">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:120ms]" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-400 [animation-delay:240ms]" />
                    </span>
                  </div>
                </div>
              )}

              {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
            </main>

            <footer className="border-t border-slate-200 bg-white/80 px-3 py-3 sm:px-4">
              <ChatInput
                value={input}
                setValue={setInput}
                loading={loading}
                onSend={onSend}
                answerStyle={answerStyle}
                setAnswerStyle={setAnswerStyle}
              />
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>Ответы только по сантехническим товарам</span>
                <span>{inputLength} / 2000</span>
              </div>
            </footer>
          </section>
        </div>
      </div>
    </div>
  );
}
