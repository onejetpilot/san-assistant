export type SourceItem = {
  doc_id: string;
  product: string;
  brand: string;
  category: string;
  section: string;
  source_file: string;
  score?: number;
};

export type DocumentType =
  | 'passport'
  | 'certificate'
  | 'manual'
  | 'installation_manual'
  | 'warranty'
  | 'datasheet'
  | 'other';

export type DocumentItem = {
  title: string;
  type: DocumentType;
  product: string;
  brand: string;
  category?: string;
  public_url: string;
  score?: number;
};

export type WebResultItem = {
  title: string;
  url: string;
  snippet: string;
};

export type ChatRequest = {
  session_id: string | null;
  conversation_id: string | null;
  message: string;
  answer_style?: 'detailed';
};

export type ChatResponse = {
  session_id: string;
  conversation_id: string;
  request_id: string;
  answer: string;
  original_query: string;
  resolved_query: string;
  depends_on_history: boolean;
  answer_mode:
    | 'short_answer'
    | 'technical_answer'
    | 'document_answer'
    | 'comparison_answer'
    | 'selection_answer'
    | 'not_enough_data'
    | 'clarify';
  sources: SourceItem[];
  documents: DocumentItem[];
  used_web_search: boolean;
  web_results: WebResultItem[];
  confidence: 'high' | 'medium' | 'low';
  tools_used: string[];
  retrieval_trace?: Array<{
    status: string;
    query: string;
    count: number;
    results: Record<string, unknown>[];
    note?: string;
    error?: string;
    meta?: Record<string, unknown>;
    mode?: string;
  }>;
  route?: Record<string, unknown>;
};

export type FeedbackRequest = {
  request_id: string;
  rating: 'up' | 'down';
  comment: string;
};

export type AdminStatusResponse = {
  status: string;
  model: string;
  router_mode: string;
  rag_documents_count: number;
  chunks_count: number;
  sku_count: number;
  documents_count: number;
  last_rag_indexed_at: string | null;
  last_documents_indexed_at: string | null;
  chroma_status: string;
  database_status: string;
  requests_24h: number;
  negative_feedback_24h: number;
};

export type Message = {
  role: 'user' | 'assistant';
  content: string;
  request_id?: string;
  sources?: SourceItem[];
  documents?: DocumentItem[];
  web_results?: WebResultItem[];
  confidence?: 'high' | 'medium' | 'low';
  used_web_search?: boolean;
  tools_used?: string[];
  answer_mode?: ChatResponse['answer_mode'];
};
