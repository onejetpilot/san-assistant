from app.indexes.kit_index import KitRecord
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.services.answer_service import AnswerService
from app.services.slot_extractor import extract_slots
from app.utils.article_normalizer import normalize_article


def _sku(article: str, short_description: str = '') -> SkuRecord:
    return SkuRecord(
        article=article,
        product='Фитинги аксиальные ONDO',
        brand='ONDO',
        category='Фитинги и соединения',
        model='Аксиальные',
        doc_id='ondo_axial',
        source_file='ondo_axial_fittings_rag_ready.txt',
        short_description=short_description,
        article_type='соединения аксиальные с внутренней резьбой',
    )


def test_format_exact_sku_answer():
    answer = AnswerService._format_sku_answer(
        _sku('OXF01612', 'диаметр(мм х дюйм) 16х1/2, длина(мм) 37,5')
    )

    assert 'Артикул OXF01612' in answer
    assert 'Фитинги аксиальные ONDO' in answer
    assert 'ONDO' in answer
    assert '16х1/2' in answer
    assert '37,5' in answer


def test_format_exact_kit_answer_with_component_descriptions():
    service = AnswerService.__new__(AnswerService)
    component = _sku('OXF01612', 'диаметр(мм х дюйм) 16х1/2, длина(мм) 37,5')
    sleeve = _sku('OXS00016', 'внутренний диаметр(мм) 16, длина(мм) 24')
    service.sku = SkuIndex(
        {
            normalize_article(component.article): component.model_dump(),
            normalize_article(sleeve.article): sleeve.model_dump(),
        }
    )
    kit = KitRecord(
        kit_article='OXF01612K10G',
        doc_id='kits',
        source_file='kits_rag_ready.txt',
        components=['10 шт OXF01612', '10 шт OXS00016'],
        component_articles=['OXF01612', 'OXS00016'],
    )

    answer = service._format_kit_answer(kit)

    assert 'Состав комплекта OXF01612K10G' in answer
    assert '10 шт OXF01612' in answer
    assert '10 шт OXS00016' in answer
    assert 'OXF01612 — диаметр(мм х дюйм) 16х1/2' in answer
    assert 'OXS00016 — внутренний диаметр(мм) 16' in answer


def test_russian_composition_markers():
    assert extract_slots('Что входит в набор OXF01612K10G?').asks_composition
    assert extract_slots('Какая комплектация OXF01612K10G?').asks_composition


def test_matches_item_type_with_russian_plural_form():
    assert AnswerService._matches_item_type('гильза', 'гильзы аксиальные')
    assert AnswerService._matches_item_type('муфта', 'муфты аксиальные')
    assert not AnswerService._matches_item_type('гильза', 'муфты аксиальные')
