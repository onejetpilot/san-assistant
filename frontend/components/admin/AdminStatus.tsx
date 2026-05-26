'use client';

import { useEffect, useState } from 'react';
import { ApiError, getAdminStatus } from '../../lib/api';
import type { AdminStatusResponse } from '../../lib/types';
import TokenGate from '../auth/TokenGate';

function Item({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-medium text-slate-900">{String(value ?? '—')}</div>
    </div>
  );
}

export default function AdminStatus() {
  const [data, setData] = useState<AdminStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [needsToken, setNeedsToken] = useState(false);

  const load = async () => {
    try {
      setError(null);
      const res = await getAdminStatus();
      setData(res);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setNeedsToken(true);
      } else {
        setError(e instanceof Error ? e.message : 'Ошибка загрузки');
      }
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (needsToken) return <TokenGate onSaved={() => { setNeedsToken(false); load(); }} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Admin Status</h1>
        <button className="rounded border border-slate-300 px-3 py-1.5 text-xs" onClick={load}>Обновить</button>
      </div>

      {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

      {data && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Item label="Backend status" value={data.status} />
          <Item label="Model" value={data.model} />
          <Item label="Router mode" value={data.router_mode} />
          <Item label="RAG documents" value={data.rag_documents_count} />
          <Item label="Chunks" value={data.chunks_count} />
          <Item label="SKU" value={data.sku_count} />
          <Item label="Documents" value={data.documents_count} />
          <Item label="Last RAG index" value={data.last_rag_indexed_at} />
          <Item label="Last docs index" value={data.last_documents_indexed_at} />
          <Item label="Chroma" value={data.chroma_status} />
          <Item label="Database" value={data.database_status} />
          <Item label="Requests 24h" value={data.requests_24h} />
          <Item label="Negative feedback 24h" value={data.negative_feedback_24h} />
        </div>
      )}
    </div>
  );
}
