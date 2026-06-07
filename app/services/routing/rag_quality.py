from __future__ import annotations

from app.core.config import settings
from app.rag.retriever import RetrievedChunk

# Strong relevance threshold for LLM synthesis; below this we prefer fallback.
RAG_STRONG_SCORE = max(settings.RAG_MIN_SCORE, 0.35)
# Weak but usable context for KB technical questions (e.g. sleeve dimensions in variants section).
RAG_WEAK_SCORE = max(settings.RAG_MIN_SCORE, 0.15)

KB_SYNTHESIS_INTENTS = frozenset({
    'knowledge_base_question',
    'installation_or_usage_question',
    'warranty_question',
    'comparison_question',
    'follow_up',
})


def filter_relevant_chunks(chunks: list[RetrievedChunk], min_score: float | None = None) -> list[RetrievedChunk]:
    threshold = RAG_STRONG_SCORE if min_score is None else min_score
    return [c for c in chunks if c.score >= threshold]


def has_strong_rag_context(chunks: list[RetrievedChunk]) -> bool:
    return bool(filter_relevant_chunks(chunks))


def has_weak_rag_context(chunks: list[RetrievedChunk]) -> bool:
    return bool([c for c in chunks if c.score >= RAG_WEAK_SCORE])


def chunks_for_llm(chunks: list[RetrievedChunk], intent: str) -> list[RetrievedChunk]:
    strong = filter_relevant_chunks(chunks)
    if strong:
        return strong[:5]
    if intent in KB_SYNTHESIS_INTENTS and has_weak_rag_context(chunks):
        return sorted(
            [c for c in chunks if c.score >= RAG_WEAK_SCORE],
            key=lambda c: c.score,
            reverse=True,
        )[:5]
    return []


def top_rag_score(chunks: list[RetrievedChunk]) -> float:
    if not chunks:
        return 0.0
    return max(c.score for c in chunks)


def build_no_context_fallback(intent: str) -> str:
    if intent == 'document_request':
        return 'В базе документов не нашёл подходящий файл. Уточните артикул, бренд или тип документа (паспорт, инструкция, сертификат).'
    if intent in {'article_lookup', 'product_question', 'price_or_availability_question'}:
        return 'В каталоге не нашёл точного совпадения. Уточните артикул, бренд или параметры товара.'
    return 'В базе знаний не нашёл точной информации по этому вопросу. Попробуйте уточнить запрос или указать артикул/бренд.'
