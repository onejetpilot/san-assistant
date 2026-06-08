const TOKEN_KEY = 'san_access_token';
const SESSION_KEY = 'san_rag_session_id';
const CONVERSATION_KEY = 'san_rag_conversation_id';

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export function getSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(SESSION_KEY);
}

export function setSessionId(sessionId: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(SESSION_KEY, sessionId);
}

export function clearSessionId(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(SESSION_KEY);
}


export function getConversationId(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(CONVERSATION_KEY);
}

export function setConversationId(conversationId: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(CONVERSATION_KEY, conversationId);
}

export function clearConversationId(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(CONVERSATION_KEY);
}
