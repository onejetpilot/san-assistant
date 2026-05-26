from __future__ import annotations

import re
from pydantic import BaseModel


TYPE_MARKERS = {
    'гильз': 'гильза',
    'муфт': 'муфта',
    'тройник': 'тройник',
    'угол': 'уголок',
    'соединен': 'соединение',
    'кран': 'кран',
    'коллектор': 'коллектор',
}

DOC_MARKERS = {
    'паспорт': 'passport',
    'сертификат': 'certificate',
    'инструкц': 'manual',
    'гарант': 'warranty',
    'pdf': 'other',
}

BRANDS = ['ondo', 'stm', 'optima', 'roegen', 'valtec', 'rispa', 'atlasplast']


class QuerySlots(BaseModel):
    intent_hint: str = 'generic'
    item_type: str = ''
    dimension_name: str = ''
    dimension_value: str = ''
    brand: str = ''
    asks_documents: bool = False
    requested_doc_type: str = ''
    asks_composition: bool = False
    asks_articles_list: bool = False
    asks_installation: bool = False
    asks_limitations: bool = False
    asks_warranty: bool = False


def extract_slots(query: str) -> QuerySlots:
    ql = query.lower()
    slots = QuerySlots()

    for k, v in TYPE_MARKERS.items():
        if k in ql:
            slots.item_type = v
            break

    if 'длина' in ql:
        slots.dimension_name = 'length'
    elif 'диаметр' in ql or 'размер' in ql:
        slots.dimension_name = 'dimension'
    if slots.dimension_name:
        m = re.search(r'\b(\d{1,3})\b', ql)
        if m:
            slots.dimension_value = m.group(1)

    for b in BRANDS:
        if b in ql:
            slots.brand = b.upper()
            break

    if any(x in ql for x in ['из чего состоит', 'состав', 'что входит', 'в наборе', 'комплект']):
        slots.asks_composition = True
        slots.intent_hint = 'composition'

    if 'какие артикул' in ql or 'перечень артикул' in ql or ('артикул' in ql and 'какие' in ql):
        slots.asks_articles_list = True
        if slots.intent_hint == 'generic':
            slots.intent_hint = 'articles_list'

    if slots.dimension_name:
        slots.intent_hint = 'dimension'

    if any(x in ql for x in ['монтаж', 'установк', 'подключ']):
        slots.asks_installation = True
    if any(x in ql for x in ['ограничен', 'нельзя', 'запрещ']):
        slots.asks_limitations = True
    if 'гарант' in ql:
        slots.asks_warranty = True

    for marker, dtype in DOC_MARKERS.items():
        if marker in ql:
            slots.asks_documents = True
            slots.requested_doc_type = dtype
            break

    return slots

