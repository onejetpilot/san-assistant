import type { Message } from '../../lib/types';
import AnswerModeBadge from './AnswerModeBadge';
import ConfidenceBadge from './ConfidenceBadge';
import DocumentsBlock from './DocumentsBlock';
import Feedback from './Feedback';
import MessageBubble from './MessageBubble';
import SourcesBlock from './SourcesBlock';
import WebResultsBlock from './WebResultsBlock';

export default function AssistantMessage({ message }: { message: Message }) {
  return (
    <div className="space-y-3">
      <MessageBubble role="assistant" content={message.content} />

      <div className="flex flex-wrap gap-2">
        <AnswerModeBadge mode={message.answer_mode} />
        <ConfidenceBadge value={message.confidence} />
        {message.used_web_search && (
          <span className="rounded-md border border-sky-200 bg-sky-100 px-2 py-1 text-xs text-sky-800">поиск san.team</span>
        )}
      </div>

      {!!message.tools_used?.length && (
        <div className="text-xs text-slate-600">tools: {message.tools_used.join(', ')}</div>
      )}

      <SourcesBlock sources={message.sources} />
      <DocumentsBlock documents={message.documents} />
      <WebResultsBlock webResults={message.web_results} />
      <Feedback requestId={message.request_id} />
    </div>
  );
}
