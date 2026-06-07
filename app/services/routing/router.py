from __future__ import annotations

import json

from app.core.config import settings
from app.core.llm_client import OpenAICompatibleLLMClient
from app.services.routing.intent_classifier import classify_intent
from app.services.routing.models import RouteDecision, RoutingContext
from app.services.routing.preprocessor import build_routing_context
from app.services.routing.route_planner import plan_route


class QueryRouter:
    def classify(self, ctx: RoutingContext) -> RouteDecision:
        intent, confidence, reason = classify_intent(ctx)
        return plan_route(ctx, intent, confidence, reason)

    async def classify_with_llm(self, ctx: RoutingContext) -> RouteDecision:
        client = OpenAICompatibleLLMClient()
        prompt = (
            'Return JSON only: '
            '{"intent":"...","tools":["rag_search"],"confidence":0.0,"reason":"..."}. '
            'Allowed intents: product_question, article_lookup, document_request, '
            'knowledge_base_question, installation_or_usage_question, warranty_question, '
            'comparison_question, price_or_availability_question, web_search_needed, '
            'ambiguous_question, out_of_scope, follow_up. '
            'Allowed tools: sku_lookup, kit_lookup, rag_search, document_search, san_team_search, clarify, refuse. '
            f'User query: {ctx.resolved_query}'
        )
        try:
            raw = await client.chat('You are a strict intent router for plumbing products.', prompt, temperature=0.0)
            data = json.loads(raw)
        except Exception:
            return self.classify(ctx)

        intent = data.get('intent', 'product_question')
        if intent == 'offtopic':
            intent = 'out_of_scope'
        confidence = float(data.get('confidence', 0.5))
        reason = str(data.get('reason', 'llm_router'))
        decision = plan_route(ctx, intent, confidence, reason)
        if isinstance(data.get('tools'), list) and data['tools']:
            decision.tools_to_call = data['tools']
        decision.classifier = 'llm'
        if confidence < 0.55:
            rules = self.classify(ctx)
            decision = rules
            decision.reason = f'llm_low_confidence_fallback:{reason}'
        if intent == 'out_of_scope':
            decision = plan_route(ctx, 'out_of_scope', 0.95, 'llm_guardrail')
            decision.classifier = 'llm'
        return decision

    async def route(self, ctx: RoutingContext) -> RouteDecision:
        mode = settings.ROUTER_MODE
        rules = self.classify(ctx)
        if mode == 'rules':
            return rules
        if mode == 'llm':
            return await self.classify_with_llm(ctx)
        if rules.confidence >= 0.85:
            return rules
        llm_decision = await self.classify_with_llm(ctx)
        if llm_decision.intent == 'out_of_scope':
            return plan_route(ctx, 'out_of_scope', 0.95, 'hybrid_guardrail')
        return llm_decision


_default_router = QueryRouter()


async def route_query(
    query: str,
    *,
    conversation_state: dict | None = None,
    recent_messages: list[dict] | None = None,
    original_query: str | None = None,
) -> RouteDecision:
    ctx = build_routing_context(
        original_query or query,
        conversation_state or {},
        recent_messages or [],
    )
    if original_query and query != original_query:
        ctx = RoutingContext(
            original_query=original_query,
            resolved_query=query,
            normalized_query=ctx.normalized_query,
            depends_on_history=ctx.depends_on_history,
            has_conversation_context=ctx.has_conversation_context,
            article=ctx.article,
            slots=ctx.slots,
        )
    return await _default_router.route(ctx)


def route_query_sync(
    query: str,
    *,
    conversation_state: dict | None = None,
    recent_messages: list[dict] | None = None,
    original_query: str | None = None,
) -> RouteDecision:
    ctx = build_routing_context(
        original_query or query,
        conversation_state or {},
        recent_messages or [],
    )
    return _default_router.classify(ctx)
