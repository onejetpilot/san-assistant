from fastapi import APIRouter, HTTPException

from app.core.schemas import ChatRequest, ChatResponse
from app.core.logging import get_logger
from app.services.answer_service import AnswerService

router = APIRouter(prefix='/api', tags=['chat'])
service = AnswerService()
logger = get_logger('chat_api')


@router.post('/chat', response_model=ChatResponse)
async def chat(payload: ChatRequest):
    try:
        return await service.answer(
            payload.message,
            session_id=payload.session_id,
            answer_style=payload.answer_style,
            conversation_id=payload.conversation_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            'chat_endpoint_error',
            extra={
                'extra_data': {
                    'session_id': payload.session_id,
                    'conversation_id': payload.conversation_id,
                    'message_preview': payload.message[:200],
                    'error_type': type(exc).__name__,
                },
            },
        )
        raise HTTPException(status_code=500, detail='Не удалось обработать сообщение. Попробуйте повторить запрос.') from exc
