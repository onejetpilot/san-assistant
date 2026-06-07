from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.slot_extractor import QuerySlots


class RoutingContext(BaseModel):
    original_query: str
    resolved_query: str
    normalized_query: str
    depends_on_history: bool = False
    has_conversation_context: bool = False
    article: str | None = None
    slots: QuerySlots = Field(default_factory=QuerySlots)


class RouteDecision(BaseModel):
    intent: str
    selected_route: str
    tools_to_call: list[str]
    confidence: float
    reason: str
    needs_clarification: bool = False
    fallback_allowed: bool = True
    use_history: bool = False
    expected_answer_type: str = 'text'
    query_rewrite: str | None = None
    classifier: str = 'rules'

    def to_legacy_dict(self) -> dict:
        return {
            'intent': self.intent,
            'tools': self.tools_to_call,
            'confidence': self.confidence,
            'reason': self.reason,
            'selected_route': self.selected_route,
            'needs_clarification': self.needs_clarification,
            'fallback_allowed': self.fallback_allowed,
            'use_history': self.use_history,
            'expected_answer_type': self.expected_answer_type,
            'query_rewrite': self.query_rewrite or '',
            'classifier': self.classifier,
        }

    def uses_tool(self, tool: str) -> bool:
        return tool in self.tools_to_call
