from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.storage.db import SessionLocal
from app.storage.models import ChatSession, ChatMessage, ConversationState


class ConversationMemoryService:
    def ensure_session(self, session_id: str | None) -> str:
        sid = session_id or str(uuid4())
        db = SessionLocal()
        row = db.execute(select(ChatSession).where(ChatSession.session_id == sid)).scalars().first()
        now = datetime.utcnow()
        if not row:
            db.add(ChatSession(session_id=sid, created_at=now, updated_at=now))
            # Defensive reset for a brand-new session id to avoid any stale state collisions.
            stale_state = db.execute(select(ConversationState).where(ConversationState.session_id == sid)).scalars().first()
            if stale_state:
                db.delete(stale_state)
        else:
            row.updated_at = now
        db.commit()
        db.close()
        return sid

    def get_state(self, session_id: str) -> dict[str, Any]:
        db = SessionLocal()
        row = db.execute(select(ConversationState).where(ConversationState.session_id == session_id)).scalars().first()
        db.close()
        if not row:
            return {
                'current_product': None,
                'current_brand': None,
                'current_article': None,
                'current_category': None,
                'current_doc_id': None,
                'last_intent': None,
                'last_answer_mode': None,
                'last_sources_json': [],
                'last_documents_json': [],
            }
        return {
            'current_product': row.current_product,
            'current_brand': row.current_brand,
            'current_article': row.current_article,
            'current_category': row.current_category,
            'current_doc_id': row.current_doc_id,
            'last_intent': row.last_intent,
            'last_answer_mode': row.last_answer_mode,
            'last_sources_json': row.last_sources_json or [],
            'last_documents_json': row.last_documents_json or [],
        }

    def get_recent_messages(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        db = SessionLocal()
        rows = db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.desc()).limit(limit)
        ).scalars().all()
        db.close()
        out = []
        for r in reversed(rows):
            out.append({'role': r.role, 'content': r.content, 'request_id': r.request_id, 'metadata_json': r.metadata_json or {}})
        return out

    def append_message(self, session_id: str, role: str, content: str, request_id: str | None = None, metadata_json: dict | None = None) -> None:
        db = SessionLocal()
        db.add(ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            request_id=request_id,
            metadata_json=metadata_json or {},
            created_at=datetime.utcnow(),
        ))
        session = db.execute(select(ChatSession).where(ChatSession.session_id == session_id)).scalars().first()
        if session:
            session.updated_at = datetime.utcnow()
        db.commit()
        db.close()

    def update_state(self, session_id: str, **kwargs) -> None:
        db = SessionLocal()
        row = db.execute(select(ConversationState).where(ConversationState.session_id == session_id)).scalars().first()
        now = datetime.utcnow()
        if not row:
            row = ConversationState(session_id=session_id, updated_at=now)
            db.add(row)
        for key, value in kwargs.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = now
        db.commit()
        db.close()
