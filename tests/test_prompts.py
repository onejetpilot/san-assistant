from app.core.prompts import build_user_prompt


def test_build_user_prompt_formats_context_without_raw_python_repr():
    prompt = build_user_prompt({
        'original_query': 'А паспорт на него есть?',
        'resolved_query': 'А паспорт на него есть? Контекст: артикул OXF01612.',
        'answer_mode': 'document_answer',
        'answer_style': 'short',
        'confidence': {'label': 'high', 'reason': 'document_found'},
        'router_decision': {
            'intent': 'document_request',
            'selected_route': 'document_lookup',
            'tools': ['document_search', 'rag_search'],
            'confidence': 0.92,
            'reason': 'document_marker',
        },
        'conversation_state': {
            'current_article': 'OXF01612',
            'current_product': 'Фитинги аксиальные ONDO',
            'current_brand': 'ONDO',
        },
        'recent_messages': [
            {'role': 'user', 'content': 'Что за OXF01612?'},
            {'role': 'assistant', 'content': 'Артикул OXF01612: фитинг ONDO.'},
        ],
        'sku_result': {
            'article': 'OXF01612',
            'product': 'Фитинги аксиальные ONDO',
            'brand': 'ONDO',
            'category': 'Фитинги',
            'short_description': 'диаметр 16х1/2',
        },
        'rag_chunks': ['TECHNICAL SPECIFICATIONS\n- Номинальное давление: 1.6 МПа'],
        'document_results': [{
            'title': 'Паспорт ONDO',
            'type': 'passport',
            'product': 'Фитинги аксиальные ONDO',
            'public_url': 'https://example.test/passport.pdf',
        }],
        'web_results': [],
    })

    assert 'Классификация запроса:' in prompt
    assert '- intent: document_request' in prompt
    assert '- Артикул: OXF01612' in prompt
    assert '1. user: Что за OXF01612?' in prompt
    assert 'Паспорт ONDO (passport)' in prompt
    assert 'https://example.test/passport.pdf' in prompt
    assert 'TECHNICAL SPECIFICATIONS' in prompt
    assert "{'intent'" not in prompt
    assert "{'title'" not in prompt


def test_build_user_prompt_uses_explicit_empty_markers():
    prompt = build_user_prompt({
        'original_query': 'Что известно?',
        'resolved_query': 'Что известно?',
        'answer_mode': 'technical_answer',
        'answer_style': 'short',
    })

    assert 'NO_HISTORY' in prompt
    assert 'NO_STATE' in prompt
    assert 'NO_SKU' in prompt
    assert 'NO_CONTEXT' in prompt
    assert 'NO_DOCUMENTS' in prompt
