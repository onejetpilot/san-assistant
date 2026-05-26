from datetime import datetime, timedelta
from sqlalchemy import desc, func, select, update

from app.storage.db import SessionLocal
from app.storage.models import ChatRequestModel, FeedbackModel, IngestionRun, DocumentIndexRun, KnowledgeGap


def save_chat_request(**kwargs) -> None:
    session = SessionLocal()
    session.add(ChatRequestModel(**kwargs))
    session.commit()
    session.close()


def save_feedback(request_id: str, rating: str, comment: str) -> None:
    session = SessionLocal()
    session.add(FeedbackModel(request_id=request_id, rating=rating, comment=comment))
    if rating == 'down':
        session.execute(update(ChatRequestModel).where(ChatRequestModel.request_id == request_id).values(needs_human_review=True))
    session.commit()
    session.close()


def save_knowledge_gap(request_id: str, original_query: str, resolved_query: str, intent: str, tools_used: list[str], reason: str) -> None:
    session = SessionLocal()
    session.add(KnowledgeGap(
        request_id=request_id,
        original_query=original_query,
        resolved_query=resolved_query,
        intent=intent,
        tools_used_json=tools_used,
        reason=reason,
        status='open',
    ))
    session.commit()
    session.close()


def get_recent_knowledge_gaps(limit: int = 50) -> list[dict]:
    session = SessionLocal()
    rows = session.execute(select(KnowledgeGap).order_by(desc(KnowledgeGap.created_at)).limit(limit)).scalars().all()
    session.close()
    return [{
        'created_at': r.created_at.isoformat(),
        'request_id': r.request_id,
        'original_query': r.original_query,
        'resolved_query': r.resolved_query,
        'intent': r.intent,
        'reason': r.reason,
        'status': r.status,
    } for r in rows]


def get_recent_requests(limit: int = 50) -> list[dict]:
    session = SessionLocal()
    rows = session.execute(select(ChatRequestModel).order_by(desc(ChatRequestModel.created_at)).limit(limit)).scalars().all()
    result = []
    for r in rows:
        f = session.execute(select(FeedbackModel).where(FeedbackModel.request_id == r.request_id).order_by(desc(FeedbackModel.created_at))).scalars().first()
        result.append({
            'timestamp': r.created_at.isoformat(),
            'query': r.user_message,
            'intent': r.intent,
            'tools_used': r.tools_used_json,
            'confidence': r.confidence,
            'used_web_search': r.used_web_search,
            'feedback': f.rating if f else None,
            'needs_human_review': r.needs_human_review,
            'rag_index_version': r.rag_index_version,
            'documents_index_version': r.documents_index_version,
        })
    session.close()
    return result


def get_admin_stats() -> dict:
    session = SessionLocal()
    last_ing = session.execute(select(IngestionRun).order_by(desc(IngestionRun.created_at))).scalars().first()
    last_doc = session.execute(select(DocumentIndexRun).order_by(desc(DocumentIndexRun.indexed_at))).scalars().first()
    since = datetime.utcnow() - timedelta(hours=24)
    requests_24h = session.execute(select(func.count()).select_from(ChatRequestModel).where(ChatRequestModel.created_at >= since)).scalar_one()
    negative_24h = session.execute(select(func.count()).select_from(FeedbackModel).where(FeedbackModel.created_at >= since, FeedbackModel.rating == 'down')).scalar_one()
    human_review_count = session.execute(select(func.count()).select_from(ChatRequestModel).where(ChatRequestModel.needs_human_review == True)).scalar_one()
    session.close()
    return {
        'rag_documents_count': last_ing.documents_count if last_ing else 0,
        'chunks_count': last_ing.chunks_count if last_ing else 0,
        'sku_count': last_ing.sku_count if last_ing else 0,
        'documents_count': last_doc.documents_count if last_doc else 0,
        'last_rag_indexed_at': last_ing.created_at.isoformat() if last_ing else None,
        'last_documents_indexed_at': last_doc.indexed_at.isoformat() if last_doc else None,
        'rag_index_version': last_ing.index_version if last_ing else None,
        'documents_index_version': last_doc.index_version if last_doc else None,
        'requests_24h': requests_24h,
        'negative_feedback_24h': negative_24h,
        'needs_human_review_count': human_review_count,
    }


def get_current_index_versions() -> dict:
    session = SessionLocal()
    last_ing = session.execute(select(IngestionRun).order_by(desc(IngestionRun.created_at))).scalars().first()
    last_doc = session.execute(select(DocumentIndexRun).order_by(desc(DocumentIndexRun.indexed_at))).scalars().first()
    session.close()
    return {
        'rag_index_version': last_ing.index_version if last_ing else None,
        'documents_index_version': last_doc.index_version if last_doc else None,
    }
