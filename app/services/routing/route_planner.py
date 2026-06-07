from __future__ import annotations

from app.services.routing.models import RouteDecision, RoutingContext

INTENT_ROUTE_MAP: dict[str, dict] = {
    'out_of_scope': {
        'selected_route': 'refuse',
        'tools': ['refuse'],
        'expected_answer_type': 'refusal',
        'fallback_allowed': False,
    },
    'smalltalk': {
        'selected_route': 'refuse',
        'tools': ['refuse'],
        'expected_answer_type': 'refusal',
        'fallback_allowed': False,
    },
    'ambiguous_question': {
        'selected_route': 'clarify',
        'tools': ['clarify'],
        'needs_clarification': True,
        'expected_answer_type': 'clarification',
        'fallback_allowed': False,
    },
    'web_search_needed': {
        'selected_route': 'web_search',
        'tools': ['san_team_search', 'rag_search'],
        'expected_answer_type': 'web_augmented',
    },
    'document_request': {
        'selected_route': 'document_lookup',
        'tools': ['document_search', 'rag_search'],
        'expected_answer_type': 'document_links',
    },
    'article_lookup': {
        'selected_route': 'product_lookup',
        'tools': ['sku_lookup', 'rag_search'],
        'expected_answer_type': 'exact_product',
        'fallback_allowed': True,
    },
    'comparison_question': {
        'selected_route': 'hybrid',
        'tools': ['sku_lookup', 'rag_search'],
        'expected_answer_type': 'comparison',
    },
    'price_or_availability_question': {
        'selected_route': 'hybrid',
        'tools': ['sku_lookup', 'rag_search'],
        'expected_answer_type': 'availability',
    },
    'installation_or_usage_question': {
        'selected_route': 'rag_answer',
        'tools': ['rag_search'],
        'expected_answer_type': 'technical',
    },
    'warranty_question': {
        'selected_route': 'hybrid',
        'tools': ['rag_search', 'document_search'],
        'expected_answer_type': 'warranty',
    },
    'product_question': {
        'selected_route': 'hybrid',
        'tools': ['sku_lookup', 'rag_search'],
        'expected_answer_type': 'product_info',
    },
    'knowledge_base_question': {
        'selected_route': 'rag_answer',
        'tools': ['rag_search'],
        'expected_answer_type': 'knowledge',
    },
    'follow_up': {
        'selected_route': 'hybrid',
        'tools': ['sku_lookup', 'rag_search', 'document_search'],
        'expected_answer_type': 'contextual',
        'use_history': True,
    },
}


def plan_route(ctx: RoutingContext, intent: str, confidence: float, reason: str) -> RouteDecision:
    spec = INTENT_ROUTE_MAP.get(intent, INTENT_ROUTE_MAP['product_question']).copy()
    tools = list(spec['tools'])

    # Product lookup only when we have a lookup signal.
    if intent in {'product_question', 'follow_up'}:
        if not ctx.article and not ctx.slots.item_type and not ctx.slots.brand and not ctx.slots.asks_articles_list:
            tools = [t for t in tools if t != 'sku_lookup']
            if intent == 'product_question' and 'rag_search' not in tools:
                tools.append('rag_search')

    if intent == 'follow_up' and ctx.slots.asks_documents:
        if 'document_search' not in tools:
            tools.append('document_search')

    if intent == 'comparison_question' and not ctx.article:
        tools = [t for t in tools if t != 'sku_lookup']

    if intent == 'knowledge_base_question' and ctx.article and ctx.slots.dimension_name:
        if 'sku_lookup' not in tools:
            tools.insert(0, 'sku_lookup')

    return RouteDecision(
        intent=intent,
        selected_route=spec['selected_route'],
        tools_to_call=tools,
        confidence=confidence,
        reason=reason,
        needs_clarification=spec.get('needs_clarification', False),
        fallback_allowed=spec.get('fallback_allowed', True),
        use_history=spec.get('use_history', ctx.depends_on_history),
        expected_answer_type=spec.get('expected_answer_type', 'text'),
        query_rewrite=ctx.resolved_query,
        classifier='rules',
    )
