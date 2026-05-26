'use client';

import { useState } from 'react';
import { setAccessToken } from '../../lib/api';

export default function TokenGate({ onSaved }: { onSaved: () => void }) {
  const [token, setToken] = useState('');

  return (
    <div className="mx-auto mt-20 max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Требуется доступ</h2>
      <p className="mt-1 text-sm text-slate-600">Введите access token для работы с SAN Assistant.</p>
      <input
        type="password"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        className="mt-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        placeholder="Bearer token"
      />
      <button
        className="mt-4 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        onClick={() => {
          setAccessToken(token.trim());
          onSaved();
        }}
      >
        Сохранить токен
      </button>
    </div>
  );
}
