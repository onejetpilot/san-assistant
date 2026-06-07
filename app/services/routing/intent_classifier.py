from __future__ import annotations

import re

from app.services.routing.models import RoutingContext
from app.utils.article_normalizer import normalize_article

# Article tokens must contain at least one digit to avoid matching plain words.
ARTICLE_TOKEN_RE = re.compile(r'\b[A-Za-z0-9]{5,}[A-Za-z0-9._\-/]*\b')

OUT_OF_SCOPE_KEYWORDS = [
    'стих', 'взломать', 'взлом', 'борщ', 'президент', 'политик',
    'рецепт', 'кино', 'футбол', 'анекдот', 'песн', 'играть в',
]
OFFTOPIC_KEYWORDS = ['погода', 'курс доллара', 'курс евро', 'биткоин']
SMALLTALK_KEYWORDS = ['привет', 'здравствуй', 'как дела', 'спасибо', 'пока']

WEB_SEARCH_MARKERS = [
    'san.team', 'на сайте san.team', 'на сайте производителя',
    'в интернете', 'в интернет', 'актуальн', 'проверь на сайте',
]
DOCUMENT_MARKERS = [
    'паспорт', 'инструкц', 'сертификат', 'pdf', 'документ',
    'скачать', 'технический паспорт', 'паспорт на',
]
INSTALLATION_MARKERS = ['монтаж', 'установк', 'подключ', 'эксплуатац', 'как правильно установ']
WARRANTY_MARKERS = ['гарант']
COMPARISON_MARKERS = ['сравни', 'сравнение', 'чем отличается', 'отличается от', 'разница между']
SELECTION_MARKERS = [
    'подбери', 'выбери', 'выбрать', 'есть ли у вас',
    'есть ли', 'найди товар', 'найди кран', 'найди насос', 'найди фильтр',
    'какой лучше',
]
PRICE_MARKERS = ['сколько стоит', 'цена', 'стоимость', 'прайс', 'наличи', 'в продаже']
KNOWLEDGE_MARKERS = [
    'как подобрать', 'почему падает', 'почему не', 'что делать если',
    'как работает', 'для чего', 'можно ли', 'допускается ли',
    'какая температура', 'какой диаметр', 'какой размер', 'какая длина',
    'имеет ли значение', 'в чем отличие', 'встанет', 'влезет', 'подойд',
    'производитель', 'кто производит', 'марка латуни', 'шаг резьбы',
    'рабочее давление', 'проходной диаметр', 'посадочного места',
]
AMBIGUOUS_PATTERNS = [
    'подбери это', 'подойдет ли', 'подойдёт ли', 'можно такой',
    'а такой', 'что лучше', 'что лучше?', 'можно так',
]
FOLLOW_UP_MARKERS = [
    'а паспорт', 'а гарантия', 'а монтаж', 'а документ', 'а цена',
    'а чем', 'а он', 'а она', 'а этот', 'а температура', 'а размер',
    'дай инструкцию', 'сертификат есть', 'на него', 'на неё',
]


def _looks_like_article(value: str) -> bool:
    normalized = normalize_article(value)
    return len(normalized) >= 5 and any(ch.isdigit() for ch in normalized)


def _find_article_token(query: str) -> str | None:
    for match in ARTICLE_TOKEN_RE.finditer(query):
        token = match.group(0)
        if _looks_like_article(token):
            return normalize_article(token)
    return None


def _is_technical_spec_question(ctx: RoutingContext) -> bool:
    q = ctx.normalized_query
    if ctx.slots.asks_compatibility or ctx.slots.intent_hint == 'compatibility':
        return True
    if ctx.slots.dimension_name and any(w in q for w in ['какая', 'какой', 'какие', 'сколько', '?']):
        return True
    if ctx.slots.item_type and any(m in q for m in ['какая длина', 'какой диаметр', 'какой размер', 'длина']):
        return True
    return False


def _is_ambiguous(ctx: RoutingContext) -> bool:
    q = ctx.normalized_query
    tokens = [t for t in q.split() if t]

    if any(pat in q for pat in AMBIGUOUS_PATTERNS):
        if not ctx.article and not ctx.slots.item_type and not ctx.slots.brand:
            return not ctx.has_conversation_context

    if len(tokens) <= 2 and not ctx.article and not ctx.slots.item_type and not ctx.slots.brand:
        if not ctx.slots.asks_documents and not re.search(r'\d', q):
            if not ctx.has_conversation_context and not ctx.depends_on_history:
                return True

    vague_short = {'это', 'такой', 'такая', 'такие', 'лучше', 'подойдет', 'подойдёт'}
    if len(tokens) <= 3 and any(t in vague_short for t in tokens):
        if not ctx.article and not ctx.has_conversation_context:
            return True

    return False


def classify_intent(ctx: RoutingContext) -> tuple[str, float, str]:
    q = ctx.normalized_query
    original = ctx.original_query.lower()

    if not q.strip():
        return 'ambiguous_question', 0.99, 'empty_query'

    if any(k in q for k in OUT_OF_SCOPE_KEYWORDS):
        return 'out_of_scope', 0.97, 'out_of_scope_keyword'

    if any(k in q for k in OFFTOPIC_KEYWORDS):
        return 'out_of_scope', 0.95, 'offtopic_keyword'

    if any(k in q for k in SMALLTALK_KEYWORDS) and len(q.split()) <= 4:
        return 'smalltalk', 0.85, 'smalltalk_greeting'

    if any(m in q for m in WEB_SEARCH_MARKERS):
        return 'web_search_needed', 0.95, 'explicit_web_search'

    if any(m in q for m in ['производитель', 'кто производит']):
        return 'knowledge_base_question', 0.88, 'manufacturer_marker'

    if _is_ambiguous(ctx):
        return 'ambiguous_question', 0.9, 'ambiguous_without_context'

    if any(m in q for m in COMPARISON_MARKERS):
        return 'comparison_question', 0.9, 'comparison_marker'

    if (
        ctx.has_conversation_context
        and ctx.slots.asks_compatibility
        and re.search(r'\b(он|она|оно|этот|эта|эти|него|неё)\b', q)
    ):
        return 'follow_up', 0.82, 'follow_up_compatibility'

    if any(m in q for m in PRICE_MARKERS):
        return 'price_or_availability_question', 0.88, 'price_marker'

    if any(m in q for m in WARRANTY_MARKERS) or ctx.slots.asks_warranty:
        return 'warranty_question', 0.86, 'warranty_marker'

    asks_doc_file = (
        any(m in q for m in DOCUMENT_MARKERS)
        or (ctx.slots.asks_documents and ctx.slots.requested_doc_type in {'passport', 'certificate', 'manual', 'other'})
    )
    if asks_doc_file:
        return 'document_request', 0.92, 'document_marker'

    if _is_technical_spec_question(ctx):
        return 'knowledge_base_question', 0.87, 'technical_spec_question'

    if any(m in q for m in KNOWLEDGE_MARKERS) or ctx.slots.asks_limitations:
        return 'knowledge_base_question', 0.78, 'knowledge_base_marker'

    if any(m in q for m in INSTALLATION_MARKERS) or ctx.slots.asks_installation:
        return 'installation_or_usage_question', 0.86, 'installation_marker'

    article = ctx.article or _find_article_token(ctx.resolved_query)
    if article:
        if ctx.slots.asks_composition:
            return 'article_lookup', 0.9, 'composition_with_article'
        if any(m in q for m in ['артикул', 'что за', 'что такое']):
            return 'article_lookup', 0.93, 'explicit_article_lookup'
        if 'найди' in q and ('артикул' in q or _find_article_token(ctx.original_query.lower())):
            return 'article_lookup', 0.91, 'find_by_article'
        return 'article_lookup', 0.88, 'article_token_detected'

    if any(m in q for m in SELECTION_MARKERS) or ctx.slots.asks_articles_list:
        return 'product_question', 0.84, 'product_selection_marker'

    if ctx.slots.item_type and ctx.slots.asks_articles_list:
        return 'product_question', 0.84, 'product_item_type_list'

    if ctx.slots.item_type and not _is_technical_spec_question(ctx):
        if any(m in q for m in SELECTION_MARKERS):
            return 'product_question', 0.84, 'product_item_type_selection'

    if ctx.depends_on_history or any(m in q for m in FOLLOW_UP_MARKERS):
        if ctx.has_conversation_context or ctx.depends_on_history:
            if any(m in q for m in DOCUMENT_MARKERS):
                return 'document_request', 0.87, 'follow_up_document'
            if any(m in q for m in PRICE_MARKERS):
                return 'price_or_availability_question', 0.84, 'follow_up_price'
            if any(m in q for m in COMPARISON_MARKERS):
                return 'comparison_question', 0.84, 'follow_up_comparison'
            return 'follow_up', 0.8, 'follow_up_with_history'

    if '?' in original or any(w in q for w in ['как', 'чем', 'почему', 'зачем', 'какой', 'какая', 'какие']):
        return 'knowledge_base_question', 0.7, 'question_form_default_kb'

    return 'product_question', 0.6, 'default_product_question'
