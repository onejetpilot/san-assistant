"""Backward-compatible router facade. Prefer app.services.routing."""

from __future__ import annotations

from app.services.routing.intent_classifier import classify_intent
from app.services.routing.router import QueryRouter, route_query, route_query_sync
from app.services.routing.preprocessor import build_routing_context

_router = QueryRouter()


def is_offtopic(query: str) -> bool:
    ctx = build_routing_context(query, {}, [])
    intent, _, _ = classify_intent(ctx)
    return intent == 'out_of_scope'


def rule_based_router(query: str, conversation_state: dict | None = None) -> dict:
    decision = route_query_sync(
        query,
        conversation_state=conversation_state or {},
        recent_messages=[],
    )
    return decision.to_legacy_dict()


async def llm_router(query: str) -> dict:
    ctx = build_routing_context(query, {}, [])
    decision = await _router.classify_with_llm(ctx)
    return decision.to_legacy_dict()


async def route_query_legacy(query: str, **kwargs) -> dict:
    decision = await route_query(query, **kwargs)
    return decision.to_legacy_dict()
