from app.indexes.kit_index import KitRecord
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.rag.retriever import RetrievedChunk
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


def test_format_dimension_answer_from_sku():
    answer = AnswerService._format_dimension_answer(
        _sku('OXS00016', 'внутренний диаметр(мм) 16, длина(мм) 24, наружный диаметр(мм) 21,5'),
        'length',
    )

    assert 'OXS00016' in answer
    assert 'длина: 24 мм' in answer
    assert 'наружный диаметр' in answer


def test_format_pipe_compatibility_answer_rejects_unlisted_wall_thickness():
    chunk = RetrievedChunk(
        text='Фитинги аксиальные совместимы с полимерными трубами: Наружный диаметр трубы 16 мм с толщиной стенки 2,2мм и 20 мм с толщиной стенки 2,8 мм',
        metadata={'source_file': 'ondo_axial_fittings_rag_ready.txt'},
        score=0.5,
    )

    answer = AnswerService._format_pipe_compatibility_answer('гильза встанет в трубу 16x2,0?', [chunk])

    assert '16 мм' in answer
    assert '2,2 мм' in answer
    assert '16x2,0' in answer
    assert 'подтверждения в базе нет' in answer


def test_format_pipe_compatibility_answer_rejects_inner_diameter_question():
    chunk = RetrievedChunk(
        text='Фитинги аксиальные совместимы с полимерными трубами: Наружный диаметр трубы 16 мм с толщиной стенки 2,2мм и 20 мм с толщиной стенки 2,8 мм',
        metadata={'source_file': 'ondo_axial_fittings_rag_ready.txt'},
        score=0.5,
    )

    answer = AnswerService._format_pipe_compatibility_answer(
        'тройник аксиальный 16x16x16, трубка кондиционера с внутренним диаметром 15,7мм будет плотно сидеть?',
        [chunk],
    )

    assert 'наружным диаметром 16 мм' in answer
    assert '2,2 мм' in answer
    assert '15,7 мм' in answer
    assert 'совместимость подтвердить нельзя' in answer


def test_format_pipe_compatibility_answer_prefers_16x22_over_16x26():
    chunk = RetrievedChunk(
        text='Фитинги аксиальные совместимы с полимерными трубами: Наружный диаметр трубы 16 мм с толщиной стенки 2,2мм и 20 мм с толщиной стенки 2,8 мм',
        metadata={'source_file': 'ondo_axial_fittings_rag_ready.txt'},
        score=0.5,
    )

    answer = AnswerService._format_pipe_compatibility_answer(
        'тройник под трубу 16x2.2 или 16x2.6?',
        [chunk],
    )

    assert 'подтверждена труба 16x2,2 мм' in answer
    assert '16x2,6 мм' in answer
    assert 'подтверждения в базе нет' in answer


def test_format_pipe_compatibility_answer_prefers_16x22_over_16x20():
    chunk = RetrievedChunk(
        text='Фитинги аксиальные совместимы с полимерными трубами: Наружный диаметр трубы 16 мм с толщиной стенки 2,2мм и 20 мм с толщиной стенки 2,8 мм',
        metadata={'source_file': 'ondo_axial_fittings_rag_ready.txt'},
        score=0.5,
    )

    answer = AnswerService._format_pipe_compatibility_answer(
        'Для какой трубы 16 со стенкой 2,0 или 2,2?',
        [chunk],
    )

    assert 'подтверждена труба 16x2,2 мм' in answer
    assert '16x2,0 мм' in answer
    assert 'подтверждения в базе нет' in answer


def test_format_pipe_compatibility_answer_explains_inner_diameter_is_not_spec():
    chunk = RetrievedChunk(
        text='Фитинги аксиальные совместимы с полимерными трубами: Наружный диаметр трубы 16 мм с толщиной стенки 2,2мм и 20 мм с толщиной стенки 2,8 мм',
        metadata={'source_file': 'ondo_axial_fittings_rag_ready.txt'},
        score=0.5,
    )

    answer = AnswerService._format_pipe_compatibility_answer(
        'к нему труба с каким внутренним диаметром подойдет?',
        [chunk],
    )

    assert 'не по внутреннему диаметру' in answer
    assert '16x2,2 мм' in answer


def test_format_known_or_missing_spec_answers_from_real_questions():
    chunk = RetrievedChunk(
        text=(
            'TECHNICAL SPECIFICATIONS\n'
            '- Номинальное давление: 1.6 МПа\n'
            'MATERIALS\n'
            '- Корпус фитингов: горячештампованная латунь\n'
            'CONNECTIONS\n'
            '- Тип резьбы: трубная\n'
            'DESCRIPTION\n'
            '- Конструкция соединения не заужает внутренний диаметр трубопровода.\n'
            'FAQ\n'
            'Работы по монтажу аксиальных фитингов должны выполняться с помощью комплекта специального инструмента: ручного; электрического.'
        ),
        metadata={'manufacturer': 'Sabie S.r.l.', 'country': 'Italy'},
        score=0.6,
    )

    assert 'Sabie S.r.l.' in AnswerService._format_known_or_missing_spec_answer('Кто производитель?', [chunk])
    assert 'вес одной штуки не указан' in AnswerService._format_known_or_missing_spec_answer('А какой вес у одной шт?', [chunk])
    assert 'шаг резьбы' in AnswerService._format_known_or_missing_spec_answer('Какой шаг резьбы: 1,25 или 1,5?', [chunk])
    assert 'горячештампованная латунь' in AnswerService._format_known_or_missing_spec_answer('Марка используемой латуни?', [chunk])
    assert 'проходного диаметра' in AnswerService._format_known_or_missing_spec_answer('Какой внутренний проходной диаметр?', [chunk])
    assert 'примерно 16 бар' in AnswerService._format_known_or_missing_spec_answer('Рабочее давление всего 1,6 Мпа?', [chunk])
    assert 'специальным инструментом' in AnswerService._format_known_or_missing_spec_answer('Муфты монтировать каким инструментом или можно руками?', [chunk])


def test_russian_composition_markers():
    assert extract_slots('Что входит в набор OXF01612K10G?').asks_composition
    assert extract_slots('Какая комплектация OXF01612K10G?').asks_composition


def test_matches_item_type_with_russian_plural_form():
    assert AnswerService._matches_item_type('гильза', 'гильзы аксиальные')
    assert AnswerService._matches_item_type('муфта', 'муфты аксиальные')
    assert not AnswerService._matches_item_type('гильза', 'муфты аксиальные')
