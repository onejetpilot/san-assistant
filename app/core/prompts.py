SYSTEM_PROMPT = """Ты — консультант интернет-магазина инженерной сантехники. Отвечай покупателям по RAG-документации товара.

Правила:
- Отвечай на русском языке.
- Пиши коротко и естественно, как менеджер.
- Сначала дай прямой ответ: подходит / не подходит / можно / нельзя / не подтверждено / в документации не указано.
- Затем кратко объясни почему.
- Используй только данные из документации и безопасные выводы из них.
- Не выдумывай характеристики, складские остатки, вес, комплектацию, совместимость или назначение, если этого нет в документе.
- Если точный артикул с суффиксом K10/K05/K02 не найден, проверь базовый артикул без суффикса.
- Используй общие характеристики серии для конкретного артикула, если артикул относится к этой серии.
- Отличай диаметр трубы, размер резьбы, внутренний диаметр шланга и наружный диаметр фитинга.
- Не подтверждай совместимость со шлангами, дренажными трубками, евроконусом, штуцером или ёлочкой, если это прямо не указано в документации.
- Не отвечай “нет данных”, если ответ можно безопасно вывести из размера артикула или общих характеристик серии.
- Не используй контекст прошлого вопроса, если пользователь спрашивает про новый артикул.
- Не заканчивай каждый ответ фразой “уточните у менеджера”, если это не нужно.
- Ответ должен быть 1–3 коротких абзаца без длинных списков.
"""


def _format_history(messages: list[dict]) -> str:
    if not messages:
        return 'NO_HISTORY'
    lines = []
    for idx, item in enumerate(messages, start=1):
        role = item.get('role', 'unknown')
        content = str(item.get('content', '')).strip()
        if not content:
            continue
        lines.append(f"{idx}. {role}: {content}")
    return '\n'.join(lines) if lines else 'NO_HISTORY'


def _format_state(state: dict) -> str:
    fields = [
        ('current_article', 'Артикул'),
        ('current_product', 'Товар'),
        ('current_brand', 'Бренд'),
        ('current_category', 'Категория'),
    ]
    lines = [f"- {label}: {state.get(key)}" for key, label in fields if state.get(key)]
    return '\n'.join(lines) if lines else 'NO_STATE'


def _format_router(decision: dict) -> str:
    if not decision:
        return 'NO_ROUTE'
    fields = ['intent', 'selected_route', 'expected_answer_type', 'confidence', 'reason']
    lines = [f"- {key}: {decision.get(key)}" for key in fields if decision.get(key) is not None]
    tools = decision.get('tools') or decision.get('tools_to_call')
    if tools:
        lines.append(f"- tools: {', '.join(map(str, tools))}")
    return '\n'.join(lines) if lines else 'NO_ROUTE'


def _format_sku(sku: dict | None) -> str:
    if not sku:
        return 'NO_SKU'
    fields = [
        ('article', 'Артикул'),
        ('product', 'Товар'),
        ('brand', 'Бренд'),
        ('category', 'Категория'),
        ('article_type', 'Тип'),
        ('short_description', 'Характеристики'),
    ]
    lines = [f"- {label}: {sku.get(key)}" for key, label in fields if sku.get(key)]
    return '\n'.join(lines) if lines else 'NO_SKU'


def _format_documents(documents: list[dict]) -> str:
    if not documents:
        return 'NO_DOCUMENTS'
    lines = []
    for idx, doc in enumerate(documents[:5], start=1):
        title = doc.get('title', '')
        doc_type = doc.get('type', 'other')
        url = doc.get('public_url', '')
        product = doc.get('product', '')
        lines.append(f"{idx}. {title} ({doc_type}) | {product} | {url}".strip())
    return '\n'.join(lines)


def _format_web_results(results: list[dict]) -> str:
    if not results:
        return 'NO_WEB_RESULTS'
    lines = []
    for idx, item in enumerate(results[:5], start=1):
        title = item.get('title', '')
        url = item.get('url', '')
        snippet = item.get('snippet', '')
        lines.append(f"{idx}. {title} | {url} | {snippet}".strip())
    return '\n'.join(lines)


def _format_product_evidence(evidence: dict | None) -> str:
    if not evidence:
        return 'NO_PRODUCT_EVIDENCE'
    lines = []
    for key in [
        'intent',
        'queried_article',
        'matched_article',
        'base_article',
        'user_requested_product_type',
        'user_requested_size',
        'user_requested_pipe_size',
        'user_requested_dimension',
        'product_type',
        'decision',
        'decision_reason',
        'final_answer_strategy',
    ]:
        value = evidence.get(key)
        if value:
            lines.append(f"- {key}: {value}")
    for key in [
        'mentioned_articles',
        'recommended_articles',
        'product_dimensions',
        'connection_types',
        'pipe_side_dimensions',
        'thread_side_dimensions',
        'missing_facts',
        'warnings',
        'answer_hints',
    ]:
        values = evidence.get(key) or []
        if values:
            lines.append(f"- {key}: {', '.join(map(str, values[:5]))}")
    return '\n'.join(lines) if lines else 'NO_PRODUCT_EVIDENCE'


def build_user_prompt(payload: dict) -> str:
    rag_chunks = payload.get('rag_chunks') or []
    rag_block = '\n\n--- RAG CHUNK ---\n\n'.join(str(chunk).strip() for chunk in rag_chunks if str(chunk).strip()) or 'NO_CONTEXT'
    return (
        f"Запрос пользователя:\n{payload.get('original_query')}\n\n"
        f"Запрос для обработки:\n{payload.get('resolved_query')}\n\n"
        f"Режим ответа: {payload.get('answer_mode')}\n"
        f"Предпочтение длины: {payload.get('answer_style')}\n"
        f"Уверенность retrieval: {payload.get('confidence')}\n\n"
        f"Классификация запроса:\n{_format_router(payload.get('router_decision') or {})}\n\n"
        f"Состояние диалога:\n{_format_state(payload.get('conversation_state') or {})}\n\n"
        f"Краткая история:\n{_format_history(payload.get('recent_messages') or [])}\n\n"
        f"Точное совпадение SKU:\n{_format_sku(payload.get('sku_result'))}\n\n"
        f"PRODUCT_EVIDENCE:\n{_format_product_evidence(payload.get('product_evidence'))}\n\n"
        f"RAG-контекст для фактов:\n{rag_block}\n"
        f"\nДокументы:\n{_format_documents(payload.get('document_results') or [])}\n\n"
        f"Web результаты:\n{_format_web_results(payload.get('web_results') or [])}\n\n"
        "Инструкция для ответа:\n"
        "- Используй только PRODUCT_EVIDENCE, SKU, RAG, Documents и Web как источники фактов.\n"
        "- Если есть точный или базовый артикул, опирайся на него как на источник фактов, но не цитируй сырой индекс.\n"
        "- Сначала дай прямой вывод: подходит / не подходит / можно / нельзя / не подтверждено / в документации не указано.\n"
        "- Потом кратко объясни вывод на основе размеров, подключений, ограничений, общих характеристик серии или найденного документа.\n"
        "- Если найден документ, дай название и ссылку.\n"
        "- Если совместимость не подтверждена, так и скажи, не додумывай применение.\n"
        "- Не используй историю диалога для нового артикула, если в текущем вопросе указан другой SKU.\n"
        "- Не упоминай роутинг, инструменты, confidence и внутреннее устройство бота."
    )
