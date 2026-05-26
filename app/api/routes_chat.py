from fastapi import APIRouter

from app.core.schemas import ChatRequest, ChatResponse
from app.services.answer_service import AnswerService

router = APIRouter(prefix='/api', tags=['chat'])
service = AnswerService()


@router.post('/chat', response_model=ChatResponse)
async def chat(payload: ChatRequest):
    return await service.answer(payload.message, payload.session_id, payload.answer_style)
