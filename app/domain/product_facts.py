from __future__ import annotations

from pydantic import BaseModel, Field


class ProductEvidence(BaseModel):
    original_query: str
    resolved_query: str
    intent: str | None = None

    mentioned_articles: list[str] = Field(default_factory=list)
    sku_facts: list[dict] = Field(default_factory=list)
    kit_facts: list[dict] = Field(default_factory=list)
    component_facts: list[dict] = Field(default_factory=list)
    rag_facts: list[str] = Field(default_factory=list)
    document_facts: list[dict] = Field(default_factory=list)

    user_requested_product_type: str | None = None
    user_requested_size: str | None = None
    user_requested_pipe_size: str | None = None
    user_requested_dimension: str | None = None

    decision: str | None = None
    decision_reason: str | None = None
    recommended_articles: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    answer_hints: list[str] = Field(default_factory=list)
    final_answer_strategy: str = 'llm_composer'
    deterministic_reason: str | None = None
