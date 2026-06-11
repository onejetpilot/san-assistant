import type { AdminStatusResponse, ChatRequest, ChatResponse, FeedbackRequest, StreamDonePayload } from './types';
import { getAccessToken, setAccessToken, clearAccessToken } from './storage';
import { safeJson } from './utils';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function candidateBases(): string[] {
  const envBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (envBase) return [envBase.replace(/\/+$/, '')];
  if (typeof window === 'undefined') return [''];
  return [''];
}

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
    const friendly =
      resp.status === 404
        ? 'API endpoint не найден. Проверь NEXT_PUBLIC_API_BASE_URL или доступность backend на :8000.'
        : `Ошибка API: HTTP ${resp.status}`;
    throw new ApiError(body && body.length < 300 ? body : friendly, resp.status);
  }
  return safeJson<T>(resp);
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  let lastError: Error | null = null;
  const bases = candidateBases();

  for (const base of bases) {
    const url = `${base}${path}`;
    try {
      const resp = await fetch(url, init);
      const contentType = resp.headers.get('content-type') || '';
      if (!resp.ok) return handle<T>(resp);
      if (!contentType.includes('application/json')) {
        throw new ApiError(
          `API вернула не JSON (проверь прокси на ${url})`,
          resp.status || 500,
        );
      }
      return safeJson<T>(resp);
    } catch (e) {
      lastError = e instanceof Error ? e : new Error('Network error');
    }
  }

  throw lastError ?? new Error('Не удалось обратиться к API');
}

export async function chat(payload: ChatRequest): Promise<ChatResponse> {
  return requestJson<ChatResponse>('/api/chat', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(payload),
  });
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  const lines = block.replace(/\r/g, '').split('\n');
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!dataLines.length) return null;
  return { event, data: dataLines.join('\n') };
}

export async function chatStream(
  payload: ChatRequest,
  onMeta: (meta: Partial<ChatResponse>) => void,
  onDelta: (text: string) => void,
  onDone: (final: Partial<StreamDonePayload>) => void,
  onError: (message: string) => void,
): Promise<void> {
  let lastError: Error | null = null;
  const bases = candidateBases();

  for (const base of bases) {
    const url = `${base}/api/chat/stream`;
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify(payload),
      });
      if (resp.status === 401) {
        throw new ApiError('Требуется access token', 401);
      }
      if (!resp.ok) {
        throw new ApiError(`Ошибка API: HTTP ${resp.status}`, resp.status);
      }
      if (!resp.body) {
        throw new ApiError('Streaming не поддерживается backend ответом', 500);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      const flushBlock = (rawBlock: string) => {
        const parsed = parseSseBlock(rawBlock);
        if (!parsed) return;
        let payloadData: Record<string, unknown> = {};
        try {
          payloadData = JSON.parse(parsed.data);
        } catch {
          payloadData = {};
        }

        if (parsed.event === 'meta') {
          onMeta(payloadData as Partial<ChatResponse>);
        } else if (parsed.event === 'delta') {
          onDelta(String(payloadData.text || ''));
        } else if (parsed.event === 'done') {
          onDone(payloadData as Partial<StreamDonePayload>);
        } else if (parsed.event === 'error') {
          onError(String(payloadData.message || 'Не удалось обработать сообщение.'));
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let sep = buffer.indexOf('\n\n');
        while (sep !== -1) {
          const block = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          flushBlock(block);
          sep = buffer.indexOf('\n\n');
        }
      }

      buffer += decoder.decode();
      if (buffer.trim()) {
        flushBlock(buffer.trim());
      }
      return;
    } catch (e) {
      lastError = e instanceof Error ? e : new Error('Network error');
    }
  }

  throw lastError ?? new Error('Не удалось обратиться к API');
}

export async function sendFeedback(payload: FeedbackRequest): Promise<{ status: string }> {
  return requestJson<{ status: string }>('/api/feedback', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(payload),
  });
}

export async function getAdminStatus(): Promise<AdminStatusResponse> {
  return requestJson<AdminStatusResponse>('/api/admin/status', {
    method: 'GET',
    headers: headers(),
  });
}

export { getAccessToken, setAccessToken, clearAccessToken };
