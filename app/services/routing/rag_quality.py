from __future__ import annotations

from app.core.config import settings
from app.rag.retriever import RetrievedChunk

# Strong relevance threshold for LLM synthesis; below this we prefer fallback.
RAG_STRONG_SCORE = max(settings.RAG_MIN_SCORE, 0.35)


def filter_relevant_chunks(chunks: list[RetrievedChunk], min_score: float | None = None) -> list[RetrievedChunk]:
    threshold = RAG_STRONG_SCORE if min_score is None else min_score
    return [c for c in chunks if c.score >= threshold]


def has_strong_rag_context(chunks: list[RetrievedChunk]) -> bool:
    return bool(filter_relevant_chunks(chunks))


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
