from app.rag.retriever import RetrievedChunk
from app.services.routing.rag_quality import chunks_for_llm, preferred_section_groups, prioritize_chunks
from app.services.slot_extractor import extract_slots


def _chunk(group: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        text=f'{group} text',
        metadata={'section_group': group, 'section': group},
        score=score,
    )


def test_warranty_intent_prefers_warranty_storage_chunks():
    chunks = [_chunk('overview', 0.52), _chunk('warranty_storage', 0.48)]

    ordered = chunks_for_llm(chunks, 'warranty_question', extract_slots('какая гарантия?'))

    assert ordered[0].metadata['section_group'] == 'warranty_storage'


def test_installation_intent_prefers_installation_chunks():
    chunks = [_chunk('technical', 0.52), _chunk('installation', 0.48)]

    ordered = chunks_for_llm(chunks, 'installation_or_usage_question', extract_slots('как выполнить монтаж?'))

    assert ordered[0].metadata['section_group'] == 'installation'


def test_dimension_question_prefers_article_rows_before_overview():
    chunks = [_chunk('overview', 0.52), _chunk('article_row', 0.48)]
    slots = extract_slots('какая длина OXS00016?')

    ordered = chunks_for_llm(chunks, 'knowledge_base_question', slots)

    assert ordered[0].metadata['section_group'] == 'article_row'


def test_unknown_intent_keeps_score_order_without_section_preferences():
    chunks = [_chunk('overview', 0.4), _chunk('technical', 0.5)]

    ordered = prioritize_chunks(chunks, preferred_section_groups('unknown_intent'))

    assert ordered[0].metadata['section_group'] == 'technical'
