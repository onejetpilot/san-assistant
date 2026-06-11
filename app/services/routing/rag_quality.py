from __future__ import annotations

from app.core.config import settings
from app.rag.retriever import RetrievedChunk
from app.services.slot_extractor import QuerySlots

# Strong relevance threshold for LLM synthesis; below this we prefer fallback.
RAG_STRONG_SCORE = max(settings.RAG_MIN_SCORE, 0.35)
# Weak but usable context for KB technical questions (e.g. sleeve dimensions in variants section).
RAG_WEAK_SCORE = max(settings.RAG_MIN_SCORE, 0.15)

KB_SYNTHESIS_INTENTS = frozenset({
    'knowledge_base_question',
    'compatibility_question',
    'related_product_question',
    'assortment_question',
    'technical_spec_question',
    'installation_or_usage_question',
    'warranty_question',
    'comparison_question',
    'follow_up',
})

SECTION_PRIORITY_SCORE = 0.08

SECTION_HINTS_BY_INTENT = {
    'installation_or_usage_question': ['installation', 'faq', 'overview'],
    'warranty_question': ['warranty_storage', 'faq', 'overview'],
    'document_request': ['overview', 'articles'],
    'article_lookup': ['article_row', 'articles', 'technical'],
    'kit_composition_question': ['article_row', 'articles', 'technical'],
    'compatibility_question': ['technical', 'article_row', 'articles', 'faq'],
    'related_product_question': ['article_row', 'articles', 'technical'],
    'assortment_question': ['article_row', 'articles', 'technical'],
    'technical_spec_question': ['technical', 'article_row', 'faq'],
    'product_question': ['article_row', 'articles', 'overview', 'technical'],
    'comparison_question': ['article_row', 'articles', 'technical', 'overview'],
    'price_or_availability_question': ['article_row', 'articles'],
}


def filter_relevant_chunks(chunks: list[RetrievedChunk], min_score: float | None = None) -> list[RetrievedChunk]:
    threshold = RAG_STRONG_SCORE if min_score is None else min_score
    return [c for c in chunks if c.score >= threshold]


def has_strong_rag_context(chunks: list[RetrievedChunk]) -> bool:
    return bool(filter_relevant_chunks(chunks))


def has_weak_rag_context(chunks: list[RetrievedChunk]) -> bool:
    return bool([c for c in chunks if c.score >= RAG_WEAK_SCORE])


def preferred_section_groups(intent: str, slots: QuerySlots | None = None) -> list[str]:
    groups = list(SECTION_HINTS_BY_INTENT.get(intent, []))
    if intent in KB_SYNTHESIS_INTENTS or intent == 'knowledge_base_question':
        if slots and slots.asks_warranty:
            groups.extend(['warranty_storage', 'faq'])
        if slots and slots.asks_installation:
            groups.extend(['installation', 'faq'])
        if slots and slots.asks_limitations:
            groups.extend(['installation', 'overview', 'faq'])
        if slots and slots.asks_composition:
            groups.extend(['article_row', 'articles'])
        if slots and (slots.dimension_name or slots.asks_compatibility or slots.asks_articles_list):
            groups.extend(['article_row', 'articles', 'technical'])
        if not groups:
            groups.extend(['technical', 'overview', 'faq'])
    return list(dict.fromkeys(groups))


def prioritize_chunks(chunks: list[RetrievedChunk], section_groups: list[str] | None = None) -> list[RetrievedChunk]:
    if not section_groups:
        return sorted(chunks, key=lambda c: c.score, reverse=True)
    priority = {group: idx for idx, group in enumerate(section_groups)}

    def sort_key(chunk: RetrievedChunk) -> tuple[float, int]:
        group = str(chunk.metadata.get('section_group', ''))
        boost = 0.0
        if group in priority:
            boost = SECTION_PRIORITY_SCORE * (len(priority) - priority[group])
        boosted_score = chunk.score + boost
        group_rank = priority.get(group, len(priority))
        return boosted_score, -group_rank

    return sorted(chunks, key=sort_key, reverse=True)


def chunks_for_llm(
    chunks: list[RetrievedChunk],
    intent: str,
    slots: QuerySlots | None = None,
) -> list[RetrievedChunk]:
    section_groups = preferred_section_groups(intent, slots)
    strong = prioritize_chunks(filter_relevant_chunks(chunks), section_groups)
    if strong:
        return strong[:5]
    if intent in KB_SYNTHESIS_INTENTS and has_weak_rag_context(chunks):
        return prioritize_chunks(
            [c for c in chunks if c.score >= RAG_WEAK_SCORE],
            section_groups,
        )[:5]
    return []


def top_rag_score(chunks: list[RetrievedChunk]) -> float:
    if not chunks:
        return 0.0
    return max(c.score for c in chunks)


def build_no_context_fallback(intent: str) -> str:
    if intent == 'document_request':
        return 'В базе документов не нашёл подходящий файл. Уточните артикул, бренд или тип документа (паспорт, инструкция, сертификат).'
    if intent in {'article_lookup', 'kit_composition_question', 'product_question', 'price_or_availability_question'}:
        return 'В каталоге не нашёл точного совпадения. Уточните артикул, бренд или параметры товара.'
    return 'В базе знаний не нашёл точной информации по этому вопросу. Попробуйте уточнить запрос или указать артикул/бренд.'
