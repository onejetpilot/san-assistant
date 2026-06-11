'use client';

import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import {
  AssistantRuntimeProvider,
  useLocalRuntime,
  type ChatModelAdapter,
  type ThreadMessage,
} from '@assistant-ui/react';
import TokenGate from '../components/auth/TokenGate';
import { getAccessToken, getConversationId, getSessionId, setConversationId, setSessionId } from '../lib/storage';

function extractLastUserText(messages: readonly ThreadMessage[]): string {
  const last = [...messages].reverse().find((message) => message.role === 'user');
  const parts = last?.content ?? [];

  return parts
    .map((part) => {
      if (part.type === 'text') return part.text;
      return '';
    })
    .join('')
    .trim();
}

export function MyRuntimeProvider({ children }: { children?: ReactNode }) {
  const [needsToken, setNeedsToken] = useState(false);

  const adapter = useMemo<ChatModelAdapter>(
    () => ({
      async run({ messages, abortSignal }) {
        const message = extractLastUserText(messages);
        const token = getAccessToken();

        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            session_id: getSessionId(),
            conversation_id: getConversationId(),
            message,
            answer_style: 'detailed',
          }),
          signal: abortSignal,
        });

        if (response.status === 401) {
          setNeedsToken(true);
          throw new Error('Требуется access token');
        }

        if (!response.ok) {
          throw new Error(`Ошибка API: ${response.status}`);
        }

        const data = await response.json();

        if (data.session_id) setSessionId(data.session_id);
        if (data.conversation_id) setConversationId(data.conversation_id);

        return {
          content: [{ type: 'text', text: data.answer || '' }],
        };
      },
    }),
    [],
  );

  const runtime = useLocalRuntime(adapter);

  if (needsToken) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-slate-100 via-zinc-100 to-slate-200 px-4 py-8">
        <TokenGate onSaved={() => setNeedsToken(false)} />
      </main>
    );
  }

  return <AssistantRuntimeProvider runtime={runtime}>{children ?? null}</AssistantRuntimeProvider>;
}
