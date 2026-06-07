from __future__ import annotations

import re

from app.services.query_resolver import resolve_query
from app.services.slot_extractor import QuerySlots, extract_slots
from app.services.routing.models import RoutingContext
from app.utils.text import extract_article_candidate


def normalize_query(text: str) -> str:
    cleaned = re.sub(r'\s+', ' ', text.strip())
    return cleaned.lower()


def build_routing_context(
    original_query: str,
    conversation_state: dict,
    recent_messages: list[dict],
) -> RoutingContext:
    resolved = resolve_query(original_query, conversation_state, recent_messages)
    resolved_query = resolved['resolved_query']
    slots = extract_slots(resolved_query)
    article = extract_article_candidate(resolved_query)
    has_context = bool(
        conversation_state.get('current_article')
        or conversation_state.get('current_product')
        or conversation_state.get('current_brand')
    )
    return RoutingContext(
        original_query=original_query,
        resolved_query=resolved_query,
        normalized_query=normalize_query(resolved_query),
        depends_on_history=resolved['depends_on_history'],
        has_conversation_context=has_context,
        article=article,
        slots=slots,
    )
