from __future__ import annotations

import json
import re

from app.core.config import settings
from app.core.llm_client import OpenAICompatibleLLMClient
from app.utils.article_normalizer import normalize_article

ARTICLE_RE = re.compile(r'\b[A-Za-zА-Яа-я0-9]{5,}[A-Za-zА-Яа-я0-9._\-/]*\b')


def is_offtopic(query: str) -> bool:
    keywords = ['погода', 'курс доллара', 'футбол', 'политика', 'рецепт', 'кино']
    q = query.lower()
    return any(k in q for k in keywords)


def rule_based_router(query: str) -> dict:
    q = query.lower()
    m = ARTICLE_RE.search(query)
    if m and len(normalize_article(m.group(0))) >= 5:
        return {'intent': 'article_lookup', 'tools': ['sku_lookup', 'rag_search'], 'confidence': 0.9, 'reason': 'article regex'}
    if 'сравни' in q or 'сравнение' in q or 'чем отличается' in q:
        return {'intent': 'comparison_question', 'tools': ['sku_lookup', 'rag_search'], 'confidence': 0.9, 'reason': 'comparison'}
    if any(x in q for x in ['паспорт', 'инструкц', 'сертификат', 'pdf', 'документ', 'ссылк', 'скачать']):
        return {'intent': 'document_request', 'tools': ['document_search', 'rag_search'], 'confidence': 0.9, 'reason': 'document request'}
    if 'san.team' in q or 'на сайте san.team' in q:
        return {'intent': 'san_team_search', 'tools': ['san_team_search'], 'confidence': 0.95, 'reason': 'explicit web search'}
    if is_offtopic(query):
        return {'intent': 'offtopic', 'tools': ['refuse'], 'confidence': 0.95, 'reason': 'offtopic'}
    if 'монтаж' in q or 'установк' in q:
        return {'intent': 'installation_question', 'tools': ['rag_search'], 'confidence': 0.8, 'reason': 'installation'}
    if 'гарант' in q:
        return {'intent': 'warranty_question', 'tools': ['rag_search', 'document_search'], 'confidence': 0.8, 'reason': 'warranty'}
    return {'intent': 'product_question', 'tools': ['rag_search'], 'confidence': 0.6, 'reason': 'default'}


async def llm_router(query: str) -> dict:
    client = OpenAICompatibleLLMClient()
    prompt = (
        'Return JSON only with schema: '
        '{"intent":"...","tools":["rag_search"],"query_rewrite":"...","confidence":0.0,"reason":"..."}. '
        'Allowed tools: sku_lookup, product_card_search, rag_search, document_search, san_team_search, clarify, refuse. '
        f'User query: {query}'
    )
    try:
        raw = await client.chat('You are strict router.', prompt, temperature=0.0)
    except Exception:
        return {'intent': 'product_question', 'tools': ['rag_search'], 'query_rewrite': query, 'confidence': 0.5, 'reason': 'llm_unavailable'}
    try:
        data = json.loads(raw)
    except Exception:
        return {'intent': 'product_question', 'tools': ['rag_search'], 'query_rewrite': query, 'confidence': 0.5, 'reason': 'invalid llm json'}
    if not isinstance(data.get('tools'), list):
        data['tools'] = ['rag_search']
    if data.get('confidence', 0) < 0.55:
        data['tools'] = ['rag_search']
    if data.get('intent') == 'offtopic':
        data['tools'] = ['refuse']
    return data


async def route_query(query: str) -> dict:
    mode = settings.ROUTER_MODE
    rules = rule_based_router(query)
    if mode == 'rules':
        return rules
    if mode == 'llm':
        return await llm_router(query)
    if rules.get('confidence', 0) >= 0.85:
        return rules
    llm = await llm_router(query)
    if llm.get('intent') == 'offtopic':
        return {'intent': 'offtopic', 'tools': ['refuse'], 'confidence': 0.95, 'reason': 'guardrail'}
    return llm
