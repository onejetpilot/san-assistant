from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.services.routing.models import RouteDecision, RoutingContext

logger = get_logger('routing')


def log_routing_decision(
    ctx: RoutingContext,
    decision: RouteDecision,
    *,
    request_id: str | None = None,
    tools_called: list[str] | None = None,
    empty_results: list[str] | None = None,
    fallback_used: bool = False,
    latency_ms: int | None = None,
) -> None:
    logger.info(
        'routing_decision',
        extra={
            'extra_data': {
                'request_id': request_id,
                'user_query': ctx.original_query[:settings.LLM_PROMPT_PREVIEW_CHARS],
                'resolved_query': ctx.resolved_query[:settings.LLM_PROMPT_PREVIEW_CHARS],
                'detected_intent': decision.intent,
                'selected_route': decision.selected_route,
                'confidence': decision.confidence,
                'reason': decision.reason,
                'tools_planned': decision.tools_to_call,
                'tools_called': tools_called or [],
                'empty_results': empty_results or [],
                'fallback_used': fallback_used,
                'needs_clarification': decision.needs_clarification,
                'use_history': decision.use_history,
                'latency_ms': latency_ms,
                'classifier': decision.classifier,
            },
        },
    )
