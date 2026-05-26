from fastapi import APIRouter

from app.core.schemas import FeedbackRequest
from app.storage.repository import save_feedback

router = APIRouter(prefix='/api', tags=['feedback'])


@router.post('/feedback')
async def feedback(payload: FeedbackRequest):
    save_feedback(payload.request_id, payload.rating, payload.comment)
    return {'status': 'ok'}
