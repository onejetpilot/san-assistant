from app.core.prompts import build_user_prompt


def test_build_user_prompt_formats_context_without_raw_python_repr():
    prompt = build_user_prompt({
        'original_query': 'А паспорт на него есть?',
        'matched_article': 'OXF01612',
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
    })

    assert '- Артикул: OXF01612' in prompt
    assert 'Найденный SKU:' in prompt
    assert 'Паспорт ONDO (passport)' in prompt
    assert 'https://example.test/passport.pdf' in prompt
    assert 'TECHNICAL SPECIFICATIONS' in prompt
    assert 'Отвечай только по этим данным.' in prompt
    assert "{'title'" not in prompt
    assert 'PRODUCT_EVIDENCE:' not in prompt
    assert 'Web результаты:' not in prompt


def test_build_user_prompt_uses_explicit_empty_markers():
    prompt = build_user_prompt({
        'original_query': 'Что известно?',
    })

    assert 'NO_ARTICLE' in prompt
    assert 'NO_SKU' in prompt
    assert 'NO_CONTEXT' in prompt
    assert 'NO_DOCUMENTS' in prompt
