from app.services.routing.preprocessor import build_routing_context
from app.services.routing.intent_classifier import classify_intent
from app.services.routing.route_planner import plan_route


def _route(query: str, state: dict | None = None, messages: list | None = None):
    ctx = build_routing_context(query, state or {}, messages or [])
    intent, conf, reason = classify_intent(ctx)
    return plan_route(ctx, intent, conf, reason)


def test_product_selection_intent():
    d = _route('Подбери шаровый кран 1/2')
    assert d.intent == 'product_question'
    assert 'sku_lookup' in d.tools_to_call or 'rag_search' in d.tools_to_call
    assert d.reason


def test_product_pump_question():
    d = _route('Есть ли у вас насос для теплого пола?')
    assert d.intent == 'product_question'
    assert d.selected_route in {'hybrid', 'product_lookup', 'rag_answer'}


def test_article_lookup_by_number():
    d = _route('Найди товар по артикулу ABC12345')
    assert d.intent == 'article_lookup'
    assert 'sku_lookup' in d.tools_to_call


def test_composition_question_with_article_uses_kit_lookup():
    d = _route('Из чего состоит комплект OXF01612K10G?')
    assert d.intent == 'kit_composition_question'
    assert 'sku_lookup' in d.tools_to_call
    assert 'kit_lookup' in d.tools_to_call


def test_dimension_question_with_article_uses_sku_lookup():
    d = _route('Какая длина OXS00016?')
    assert d.intent == 'technical_spec_question'
    assert 'sku_lookup' in d.tools_to_call
    assert 'rag_search' in d.tools_to_call


def test_compatibility_question_detected_before_article_lookup():
    d = _route('Подойдет ли уголок OXL01616 под трубу 20х2.8?')
    assert d.intent == 'compatibility_question'
    assert 'sku_lookup' in d.tools_to_call


def test_related_product_question_detected():
    d = _route('Какая гильза нужна к тройнику OXT02020?')
    assert d.intent == 'related_product_question'
    assert 'sku_lookup' in d.tools_to_call


def test_assortment_question_detected():
    d = _route('Есть ли уголки и тройники на 14 мм?')
    assert d.intent == 'assortment_question'


def test_installation_question_detected_for_hidden_install():
    d = _route('Можно ли замонолитить эти фитинги в стяжку?')
    assert d.intent == 'installation_or_usage_question'


def test_price_question():
    d = _route('Сколько стоит фильтр грубой очистки?')
    assert d.intent == 'price_or_availability_question'


def test_manufacturer_question_is_kb_not_ambiguous():
    d = _route('Кто производитель?')
    assert d.intent == 'knowledge_base_question'
    assert 'rag_search' in d.tools_to_call


def test_product_link_request_is_not_document_request():
    d = _route('Скиньте ссылку на аксиальный с накидной гайкой 16 на 1/2')
    assert d.intent in {'product_question', 'knowledge_base_question'}
    assert 'document_search' not in d.tools_to_call


def test_in_sale_question_routes_to_availability():
    d = _route('У вас есть в продаже уголки аксиальные 16 2.2?')
    assert d.intent == 'price_or_availability_question'


def test_document_passport():
    d = _route('Дай паспорт на этот насос')
    assert d.intent == 'document_request'
    assert 'document_search' in d.tools_to_call


def test_document_manual():
    d = _route('Нужна инструкция по монтажу')
    assert d.intent in {'document_request', 'installation_or_usage_question'}
    assert d.reason


def test_document_certificate():
    d = _route('Скинь сертификат на товар')
    assert d.intent == 'document_request'


def test_document_download():
    d = _route('Где скачать технический паспорт?')
    assert d.intent == 'document_request'


def test_kb_installation():
    d = _route('Как правильно установить расширительный бак?')
    assert d.intent in {'knowledge_base_question', 'installation_or_usage_question'}
    assert 'rag_search' in d.tools_to_call


def test_kb_comparison_phrase():
    d = _route('Чем отличается редуктор давления от фильтра?')
    assert d.intent == 'comparison_question'


def test_kb_pipe_diameter():
    d = _route('Как подобрать диаметр трубы?')
    assert d.intent in {'knowledge_base_question', 'product_question'}
    assert 'rag_search' in d.tools_to_call


def test_kb_pressure_drop():
    d = _route('Почему падает давление в системе?')
    assert d.intent == 'knowledge_base_question'


def test_web_search_san_team():
    d = _route('Найди информацию на сайте san.team')
    assert d.intent == 'web_search_needed'
    assert 'san_team_search' in d.tools_to_call


def test_web_search_manufacturer():
    d = _route('Что написано на сайте производителя?')
    assert d.intent == 'web_search_needed'


def test_web_search_internet():
    d = _route('Проверь актуальную информацию в интернете')
    assert d.intent == 'web_search_needed'


def test_ambiguous_pick_this():
    d = _route('Подбери это')
    assert d.intent == 'ambiguous_question'
    assert d.needs_clarification


def test_ambiguous_what_better():
    d = _route('Что лучше?')
    assert d.intent == 'ambiguous_question'


def test_ambiguous_can_use():
    d = _route('Можно такой?')
    assert d.intent == 'ambiguous_question'


def test_out_of_scope_poem():
    d = _route('Напиши мне стих')
    assert d.intent == 'out_of_scope'
    assert 'refuse' in d.tools_to_call


def test_out_of_scope_president():
    d = _route('Кто президент США?')
    assert d.intent == 'out_of_scope'


def test_out_of_scope_hack():
    d = _route('Помоги взломать сайт')
    assert d.intent == 'out_of_scope'


def test_out_of_scope_borscht():
    d = _route('Как приготовить борщ?')
    assert d.intent == 'out_of_scope'


def test_follow_up_passport_with_history():
    state = {'current_article': 'OXF01612', 'current_product': 'Фитинги ONDO', 'current_brand': 'ONDO'}
    d = _route('А паспорт на него есть?', state)
    assert d.intent in {'document_request', 'follow_up'}
    assert d.use_history or d.depends_on_history is False  # use_history set from ctx


def test_follow_up_comparison_with_history():
    state = {'current_article': 'OXF01612', 'current_product': 'Фитинг'}
    d = _route('А чем он отличается от второго?', state)
    assert d.intent == 'comparison_question'


def test_follow_up_apartment_with_history():
    state = {'current_product': 'Насос', 'current_brand': 'ONDO'}
    d = _route('Подойдет ли он для квартиры?', state)
    assert d.intent in {'follow_up', 'knowledge_base_question', 'product_question'}


def test_follow_up_price_with_history():
    state = {'current_article': 'OXF01612'}
    d = _route('А цена?', state)
    assert d.intent in {'price_or_availability_question', 'follow_up'}


def test_passport_not_misrouted_as_article():
    d = _route('нужен паспорт на изделие')
    assert d.intent == 'document_request'
    assert 'sku_lookup' not in d.tools_to_call or d.intent == 'document_request'


def test_route_has_confidence_and_reason():
    d = _route('Какая гарантия на ONDO?')
    assert 0.0 < d.confidence <= 1.0
    assert d.reason
