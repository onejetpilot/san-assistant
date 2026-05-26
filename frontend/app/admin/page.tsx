'use client';
import { useEffect, useState } from 'react';

export default function AdminPage() {
  const [status, setStatus] = useState<any>(null);
  const [requests, setRequests] = useState<any[]>([]);
  const [gaps, setGaps] = useState<any[]>([]);

  useEffect(() => {
    fetch('http://localhost:8000/api/admin/status').then(r => r.json()).then(setStatus);
    fetch('http://localhost:8000/api/admin/recent-requests').then(r => r.json()).then(setRequests);
    fetch('http://localhost:8000/api/admin/knowledge-gaps').then(r => r.json()).then(setGaps);
  }, []);

  return (
    <main className="p-6 bg-slate-50 min-h-screen space-y-4">
      <h1 className="text-xl font-semibold">Admin</h1>
      <pre>{JSON.stringify(status, null, 2)}</pre>
      <h2 className="text-lg font-semibold">Recent Requests</h2>
      <pre>{JSON.stringify(requests, null, 2)}</pre>
      <h2 className="text-lg font-semibold">Knowledge Gaps</h2>
      <pre>{JSON.stringify(gaps, null, 2)}</pre>
    </main>
  );
}
