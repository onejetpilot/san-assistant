from app.services.slot_extractor import extract_slots


def test_extract_dimension_and_type_and_brand():
    s = extract_slots('какая длина аксиальной гильзы 16 ondo?')
    assert s.intent_hint == 'dimension'
    assert s.item_type == 'гильза'
    assert s.dimension_value == '16'
    assert s.brand == 'ONDO'


def test_extract_articles_list():
    s = extract_slots('какие артикулы у гильз аксиальных ondo?')
    assert s.asks_articles_list is True
    assert s.item_type == 'гильза'
    assert s.brand == 'ONDO'


def test_extract_articles_list_without_question_word():
    s = extract_slots('артикулы гильз ONDO')
    assert s.asks_articles_list is True
    assert s.item_type == 'гильза'
    assert s.brand == 'ONDO'


def test_extract_document_request():
    s = extract_slots('дай паспорт на артикул OXF02012')
    assert s.asks_documents is True
    assert s.requested_doc_type == 'passport'


def test_extract_pipe_fit_phrasing_as_compatibility():
    s = extract_slots('трубка с внутренним диаметром 15,7 мм будет плотно сидеть?')
    assert s.asks_compatibility is True


def test_extract_pipe_size_choice_as_compatibility():
    s = extract_slots('тройник под трубу 16x2.2 или 16x2.6?')
    assert s.asks_compatibility is True
