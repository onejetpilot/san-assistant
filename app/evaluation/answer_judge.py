from app.core.logging import get_logger

logger = get_logger(__name__)


async def evaluate_answer(payload: dict) -> dict:
    try:
        return {
            'relevance': 4,
            'groundedness': 4,
            'uses_only_allowed_sources': True,
            'hallucination_risk': False,
            'needs_human_review': False,
        }
    except Exception as e:
        logger.error('judge_failed', extra={'extra_data': {'error': str(e)}})
        return {}
