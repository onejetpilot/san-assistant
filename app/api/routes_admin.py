from fastapi import APIRouter

from app.core.config import settings
from app.core.chroma import get_chroma_client
from app.storage.repository import get_admin_stats, get_recent_requests, get_recent_knowledge_gaps

router = APIRouter(prefix='/api/admin', tags=['admin'])


@router.get('/status')
async def status():
    stats = get_admin_stats()
    chroma_status = 'ok'
    try:
        client = get_chroma_client()
        _ = client.heartbeat()
    except Exception:
        chroma_status = 'error'
    return {
        'status': 'ok',
        'model': settings.LLM_MODEL,
        'router_mode': settings.ROUTER_MODE,
        **stats,
        'chroma_status': chroma_status,
        'database_status': 'ok',
    }


@router.get('/recent-requests')
async def recent_requests():
    return get_recent_requests()


@router.get('/knowledge-gaps')
async def knowledge_gaps():
    return get_recent_knowledge_gaps()
