SYSTEM_PROMPT = """Ты — консультант интернет-магазина инженерной сантехники. Отвечай покупателю по предоставленному товарному контексту.

Правила:
- Отвечай на русском языке.
- Пиши коротко и естественно, как живой менеджер.
- Отвечай прямо на вопрос пользователя, без шаблонного начала.
- Не начинай каждый ответ словами “подходит”, “не подходит” или “не подтверждено”.
- Используй “подходит / не подходит” только если вопрос действительно про совместимость.
- Если вопрос про характеристику, сразу называй характеристику.
- Если вопрос про монтаж, отвечай “да, можно” или “нет, нельзя”, если это следует из документации.
- Используй только предоставленный RAG-контекст, SKU-карточку и документы из внутренней базы.
- Не используй интернет и не ссылайся на внешние источники.
- Не выдумывай наличие на складе, вес, комплектацию, совместимость или характеристики, которых нет в контексте.
- Если данных нет, коротко скажи, что в документации не указано.
- Ответ должен быть 1–3 коротких абзаца.
- Не рассказывай пользователю про RAG, инструменты, confidence, route, chunks или внутреннюю архитектуру.
"""

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


def build_user_prompt(payload: dict) -> str:
    rag_chunks = payload.get('rag_chunks') or []
    rag_block = '\n\n--- RAG CHUNK ---\n\n'.join(str(chunk).strip() for chunk in rag_chunks if str(chunk).strip()) or 'NO_CONTEXT'
    return (
        f"Вопрос пользователя:\n{payload.get('original_query')}\n\n"
        f"Запрошенный артикул:\n{payload.get('requested_article') or 'NO_ARTICLE'}\n\n"
        f"Технический артикул:\n{payload.get('technical_article') or 'NO_ARTICLE'}\n\n"
        f"Комплектный артикул:\n{payload.get('pack_article') or 'NO_PACK_ARTICLE'}\n\n"
        f"Найденный SKU:\n{payload.get('matched_article') or 'NO_ARTICLE'}\n\n"
        f"SKU-карточка:\n{_format_sku(payload.get('sku_result'))}\n\n"
        f"RAG-контекст:\n{rag_block}\n\n"
        f"Документы:\n{_format_documents(payload.get('document_results') or [])}\n\n"
        "Инструкция:\n"
        "- Отвечай только по этим данным.\n"
        "- Если запрошенный артикул содержит K10/K05/K02, технические характеристики отвечай по техническому артикулу.\n"
        "- Комплектный артикул используй только для количества штук и состава.\n"
        "- Не объясняй покупателю внутреннюю маршрутизацию артикула."
    )
