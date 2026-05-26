from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class ChatRequestModel(Base):
    __tablename__ = 'chat_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_message: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(64))
    answer_mode: Mapped[str] = mapped_column(String(64))
    router_mode: Mapped[str] = mapped_column(String(32))
    tools_used_json: Mapped[list] = mapped_column(JSON)
    sources_json: Mapped[list] = mapped_column(JSON)
    documents_json: Mapped[list] = mapped_column(JSON)
    used_web_search: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[str] = mapped_column(String(16))
    model_name: Mapped[str] = mapped_column(String(128))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    rag_index_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    documents_index_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeedbackModel(Base):
    __tablename__ = 'feedback'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    rating: Mapped[str] = mapped_column(String(8))
    comment: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IngestionRun(Base):
    __tablename__ = 'ingestion_runs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(32), default='knowledge')
    status: Mapped[str] = mapped_column(String(32))
    documents_count: Mapped[int] = mapped_column(Integer, default=0)
    chunks_count: Mapped[int] = mapped_column(Integer, default=0)
    sku_count: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[list] = mapped_column(JSON, default=[])
    warnings_json: Mapped[list] = mapped_column(JSON, default=[])
    index_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentIndexRun(Base):
    __tablename__ = 'document_index_runs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32))
    documents_count: Mapped[int] = mapped_column(Integer, default=0)
    document_types_count_json: Mapped[dict] = mapped_column(JSON, default={})
    index_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeGap(Base):
    __tablename__ = 'knowledge_gaps'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    original_query: Mapped[str] = mapped_column(Text)
    resolved_query: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(64))
    tools_used_json: Mapped[list] = mapped_column(JSON, default=[])
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default='open')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConversationState(Base):
    __tablename__ = 'conversation_state'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    current_product: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_article: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_category: Mapped[str | None] = mapped_column(String(256), nullable=True)
    current_doc_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_answer_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_sources_json: Mapped[list] = mapped_column(JSON, default=[])
    last_documents_json: Mapped[list] = mapped_column(JSON, default=[])
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
