'use client';

import { ActionBarPrimitive, ComposerPrimitive, MessagePrimitive, ThreadPrimitive, useThread } from '@assistant-ui/react';
import { CopyIcon, PlusIcon, RefreshCwIcon, SendIcon, SquareIcon } from 'lucide-react';
import { clearConversationId, clearSessionId } from '../../lib/storage';
import { cn } from '../../lib/utils';

function Welcome() {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-3xl items-center justify-center px-4 py-10">
      <div className="w-full rounded-[28px] border border-slate-200 bg-white/90 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur">
        <div className="mx-auto max-w-2xl text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-cyan-400 text-white shadow-lg">
            <span className="text-lg font-semibold">SAN</span>
          </div>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-slate-950">
            Чем помочь по сантехническим товарам?
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Напишите артикул, название товара или вопрос по подбору, документам и совместимости.
          </p>
        </div>
      </div>
    </div>
  );
}

function NewChatButton() {
  return (
    <button
      className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
      onClick={() => {
        clearSessionId();
        clearConversationId();
        window.location.reload();
      }}
      type="button"
    >
      <PlusIcon className="h-4 w-4" />
      Новый чат
    </button>
  );
}

function StatusBadge() {
  const isRunning = useThread((state) => state.isRunning);

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white/80 px-3 py-1.5 text-xs text-slate-600">
      <span className={cn('h-2 w-2 rounded-full', isRunning ? 'bg-amber-400' : 'bg-emerald-400')} />
      {isRunning ? 'Генерация ответа...' : 'Готов к запросу'}
    </span>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end px-3 py-2 sm:px-4">
      <div className="max-w-[88%] rounded-3xl rounded-br-lg bg-slate-950 px-4 py-3 text-sm leading-6 text-white shadow-sm">
        <MessagePrimitive.Content
          components={{
            Text: ({ text }) => <div className="whitespace-pre-wrap break-words">{text}</div>,
          }}
        />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="px-3 py-2 sm:px-4">
      <div className="max-w-[92%]">
        <div className="rounded-3xl rounded-bl-lg border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-800 shadow-sm">
          <MessagePrimitive.Content
            components={{
              Text: ({ text }) => <div className="whitespace-pre-wrap break-words">{text}</div>,
            }}
          />
        </div>

        <ActionBarPrimitive.Root className="mt-2 flex items-center gap-2 text-xs text-slate-500">
          <ActionBarPrimitive.Copy className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 transition hover:border-slate-300 hover:bg-slate-50">
            <CopyIcon className="h-3.5 w-3.5" />
            Скопировать
          </ActionBarPrimitive.Copy>
          <ActionBarPrimitive.Reload className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 transition hover:border-slate-300 hover:bg-slate-50">
            <RefreshCwIcon className="h-3.5 w-3.5" />
            Повторить
          </ActionBarPrimitive.Reload>
        </ActionBarPrimitive.Root>
      </div>
    </MessagePrimitive.Root>
  );
}

function Composer() {
  return (
    <div className="border-t border-slate-200 bg-white/85 px-3 py-3 backdrop-blur sm:px-4">
      <ComposerPrimitive.Root className="mx-auto max-w-4xl">
        <div className="overflow-hidden rounded-[28px] border border-slate-300 bg-white shadow-[0_12px_36px_rgba(15,23,42,0.08)]">
          <ComposerPrimitive.Input
            autoFocus
            className="min-h-[96px] w-full resize-none border-0 bg-transparent px-4 py-4 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400"
            placeholder="Введите артикул или вопрос по товару..."
          />
          <div className="flex items-center justify-end gap-2 border-t border-slate-100 px-3 py-3">
            <ThreadPrimitive.If running>
              <ComposerPrimitive.Cancel className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50">
                <SquareIcon className="h-4 w-4" />
                Стоп
              </ComposerPrimitive.Cancel>
            </ThreadPrimitive.If>
            <ThreadPrimitive.If running={false}>
              <ComposerPrimitive.Send className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-sky-600 to-cyan-500 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:from-sky-500 hover:to-cyan-400 disabled:cursor-not-allowed disabled:opacity-50">
                <SendIcon className="h-4 w-4" />
                Отправить
              </ComposerPrimitive.Send>
            </ThreadPrimitive.If>
          </div>
        </div>
      </ComposerPrimitive.Root>
    </div>
  );
}

export function Thread() {
  return (
    <ThreadPrimitive.Root className="mx-auto flex h-screen w-full max-w-7xl flex-col px-3 py-4 sm:px-4 sm:py-6">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.12),_transparent_38%),linear-gradient(180deg,_rgba(248,250,252,0.96)_0%,_rgba(241,245,249,0.96)_100%)] shadow-[0_30px_120px_rgba(15,23,42,0.12)] backdrop-blur">
        <header className="border-b border-slate-200 bg-white/75 px-4 py-4 backdrop-blur sm:px-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-950">SAN Assistant</h2>
              <p className="text-xs text-slate-500">Консультант по сантехническим товарам</p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge />
              <NewChatButton />
            </div>
          </div>
        </header>

        <ThreadPrimitive.Viewport autoScroll className="min-h-0 flex-1 overflow-y-auto">
          <ThreadPrimitive.Empty>
            <Welcome />
          </ThreadPrimitive.Empty>
          <ThreadPrimitive.Messages
            components={{
              UserMessage,
              AssistantMessage,
            }}
          />
        </ThreadPrimitive.Viewport>

        <Composer />
      </div>
    </ThreadPrimitive.Root>
  );
}
