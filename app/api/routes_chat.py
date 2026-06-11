import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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


def _format_sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post('/chat/stream')
async def chat_stream(payload: ChatRequest):
    async def event_stream():
        try:
            async for item in service.answer_stream(
                payload.message,
                session_id=payload.session_id,
                answer_style=payload.answer_style,
                conversation_id=payload.conversation_id,
            ):
                yield _format_sse_event(item['event'], item['data'])
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                'chat_stream_endpoint_error',
                extra={
                    'extra_data': {
                        'session_id': payload.session_id,
                        'conversation_id': payload.conversation_id,
                        'message_preview': payload.message[:200],
                        'error_type': type(exc).__name__,
                    },
                },
            )
            yield _format_sse_event('error', {'message': 'Не удалось обработать сообщение. Попробуйте повторить запрос.'})

    return StreamingResponse(event_stream(), media_type='text/event-stream')
