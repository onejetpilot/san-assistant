from fastapi import APIRouter

from app.core.schemas import ChatRequest, ChatResponse
from app.services.answer_service import AnswerService

router = APIRouter(prefix='/api', tags=['chat'])
service = AnswerService()


@router.post('/chat', response_model=ChatResponse)
async def chat(payload: ChatRequest):
    return await service.answer(
        payload.message,
        session_id=payload.session_id,
        answer_style=payload.answer_style,
        conversation_id=payload.conversation_id,
    )
