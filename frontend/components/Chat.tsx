'use client';
import { useEffect, useState } from 'react';

const SESSION_KEY = 'san_rag_session_id';

export default function Chat() {
  const [message, setMessage] = useState('');
  const [resp, setResp] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [answerStyle, setAnswerStyle] = useState<'short' | 'detailed'>('detailed');

  useEffect(() => {
    const sid = window.localStorage.getItem(SESSION_KEY);
    if (sid) setSessionId(sid);
  }, []);

  const send = async () => {
    setLoading(true);
    const r = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({session_id: sessionId, message, answer_style: answerStyle}),
    });
    const data = await r.json();
    if (data.session_id) {
      window.localStorage.setItem(SESSION_KEY, data.session_id);
      setSessionId(data.session_id);
    }
    setResp(data);
    setLoading(false);
  };

  const newChat = () => {
    window.localStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setResp(null);
    setMessage('');
  };

  return (
    <div className="max-w-4xl mx-auto bg-white rounded-xl p-6 shadow">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">SAN RAG Bot</h1>
        <button className="border border-slate-300 px-3 py-1 rounded" onClick={newChat}>Новый чат</button>
      </div>
      <div className="mb-3 flex gap-3">
        <select className="border rounded px-2 py-1" value={answerStyle} onChange={e => setAnswerStyle(e.target.value as 'short' | 'detailed')}>
          <option value="detailed">Подробный</option>
          <option value="short">Краткий</option>
        </select>
      </div>
      <textarea className="w-full border rounded p-3" rows={4} value={message} onChange={e => setMessage(e.target.value)} />
      <button className="mt-3 bg-slate-900 text-white px-4 py-2 rounded" onClick={send} disabled={loading}>{loading ? 'Загрузка...' : 'Отправить'}</button>
      {resp && (
        <div className="mt-4">
          <button className="mb-2 border border-slate-300 px-3 py-1 rounded" onClick={() => navigator.clipboard.writeText(resp.answer || '')}>Скопировать ответ</button>
          <pre className="whitespace-pre-wrap">{JSON.stringify(resp, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
