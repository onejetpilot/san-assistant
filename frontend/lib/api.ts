import type { AdminStatusResponse, ChatRequest, ChatResponse, FeedbackRequest } from './types';
import { getAccessToken, setAccessToken, clearAccessToken } from './storage';
import { safeJson } from './utils';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

function headers(): HeadersInit {
  const h: HeadersInit = { 'Content-Type': 'application/json' };
  const token = getAccessToken();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function handle<T>(resp: Response): Promise<T> {
  if (resp.status === 401) {
    throw new ApiError('Требуется access token', 401);
  }
  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(body || `HTTP ${resp.status}`, resp.status);
  }
  return safeJson<T>(resp);
}

export async function chat(payload: ChatRequest): Promise<ChatResponse> {
  const resp = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return handle<ChatResponse>(resp);
}

export async function sendFeedback(payload: FeedbackRequest): Promise<{ status: string }> {
  const resp = await fetch(`${API_BASE}/api/feedback`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return handle<{ status: string }>(resp);
}

export async function getAdminStatus(): Promise<AdminStatusResponse> {
  const resp = await fetch(`${API_BASE}/api/admin/status`, {
    method: 'GET',
    headers: headers(),
  });
  return handle<AdminStatusResponse>(resp);
}

export { getAccessToken, setAccessToken, clearAccessToken };
