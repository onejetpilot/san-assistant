from __future__ import annotations

from app.utils.text import extract_article_candidate
from app.utils.article_normalizer import normalize_article

HISTORY_PRONOUNS = ['он', 'она', 'оно', 'они', 'этот', 'эта', 'это', 'эти', 'него', 'них', 'нему', 'нему', 'такой', 'такая', 'такие']
SHORT_FOLLOWUPS = ['а паспорт', 'а гарантия', 'а монтаж', 'а документы', 'а температура', 'а размеры', 'дай инструкцию', 'сертификат есть']


def resolve_query(original_query: str, conversation_state: dict, recent_messages: list[dict]) -> dict:
    q = original_query.strip()
    ql = q.lower()
    article = normalize_article(extract_article_candidate(q) or '') or None

    has_history_dependency = False
    if any(p in ql for p in HISTORY_PRONOUNS):
        has_history_dependency = True
    if any(ql.startswith(x) or x in ql for x in SHORT_FOLLOWUPS):
        has_history_dependency = True
    if len(q.split()) <= 3:
        has_history_dependency = has_history_dependency or any(k in ql for k in ['паспорт', 'гарант', 'монтаж', 'документ', 'инструкц', 'сертификат', 'температур'])

    # New explicit entity in query has priority
    explicit_brand = None
    for token in q.split():
        if token.isupper() and len(token) >= 3:
            explicit_brand = token
            break

    if article:
        has_history_dependency = False

    if not has_history_dependency:
        return {
            'original_query': original_query,
            'resolved_query': original_query,
            'depends_on_history': False,
            'used_context': {'reason': 'independent_query', 'recent_messages_count': len(recent_messages), 'explicit_brand': explicit_brand},
        }

    product = conversation_state.get('current_product')
    brand = conversation_state.get('current_brand')
    current_article = conversation_state.get('current_article')
    category = conversation_state.get('current_category')

    ctx_parts = []
    if current_article:
        ctx_parts.append(f'артикул {current_article}')
    if product:
        ctx_parts.append(f'продукт {product}')
    if brand:
        ctx_parts.append(f'бренд {brand}')
    if category:
        ctx_parts.append(f'категория {category}')

    if ctx_parts:
        resolved = f"{original_query}. Контекст текущего диалога: {', '.join(ctx_parts)}."
    else:
        resolved = original_query

    return {
        'original_query': original_query,
        'resolved_query': resolved,
        'depends_on_history': bool(ctx_parts),
        'used_context': {
            'current_product': product,
            'current_brand': brand,
            'current_article': current_article,
            'current_category': category,
        },
    }
