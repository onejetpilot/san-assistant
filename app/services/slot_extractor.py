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
    item_types: list[str] = []
    dimension_name: str = ''
    dimension_value: str = ''
    requested_size: str = ''
    requested_pipe_size: str = ''
    brand: str = ''
    asks_documents: bool = False
    requested_doc_type: str = ''
    asks_composition: bool = False
    asks_related_product: bool = False
    asks_articles_list: bool = False
    asks_assortment: bool = False
    asks_installation: bool = False
    asks_limitations: bool = False
    asks_warranty: bool = False
    asks_compatibility: bool = False
    asks_technical_spec: bool = False


def extract_slots(query: str) -> QuerySlots:
    ql = query.lower()
    slots = QuerySlots()

    for k, v in TYPE_MARKERS.items():
        if k in ql and v not in slots.item_types:
            slots.item_types.append(v)
    if slots.item_types:
        slots.item_type = slots.item_types[0]

    if 'длина' in ql or 'длинн' in ql or 'длиной' in ql:
        slots.dimension_name = 'length'
    elif 'диаметр' in ql or 'размер' in ql:
        slots.dimension_name = 'dimension'
    if slots.dimension_name:
        m = re.search(r'\b(\d{1,3})\b', ql)
        if m:
            slots.dimension_value = m.group(1)
    pipe_match = re.search(r'\b(\d{1,2})\s*[xх]\s*(\d(?:[,.]\d)?)\b', ql)
    if pipe_match:
        slots.requested_pipe_size = f"{pipe_match.group(1)}x{pipe_match.group(2).replace(',', '.')}"
        if not slots.dimension_value:
            slots.dimension_value = pipe_match.group(1)
    mm_match = re.search(r'\b(14|16|20)\s*мм\b', ql)
    if mm_match:
        slots.requested_size = mm_match.group(1)
    elif slots.dimension_value in {'14', '16', '20'}:
        slots.requested_size = slots.dimension_value

    for b in BRANDS:
        if b in ql:
            slots.brand = b.upper()
            break

    if any(x in ql for x in ['из чего состоит', 'состав', 'что входит', 'в наборе', 'комплект', 'комплектац', 'набор']):
        slots.asks_composition = True
        slots.intent_hint = 'composition'
    if any(x in ql for x in ['какая гильза', 'что нужно к', 'какие комплектующие', 'чем обжать']):
        slots.asks_related_product = True
        slots.intent_hint = 'related_product'

    if (
        'какие артикул' in ql
        or 'перечень артикул' in ql
        or 'список артикул' in ql
        or ('артикул' in ql and 'какие' in ql)
        or ('артикул' in ql and (slots.item_type or slots.brand))
    ):
        slots.asks_articles_list = True
        if slots.intent_hint == 'generic':
            slots.intent_hint = 'articles_list'

    if slots.dimension_name:
        slots.intent_hint = 'dimension'

    if any(x in ql for x in ['есть ли 14', 'бывают ли 14', 'есть размер 14', 'есть ли 16', 'есть размер 16', 'есть ли 20', 'есть размер 20', 'бывают ли 16', 'бывают ли 20']):
        slots.asks_assortment = True
        if slots.intent_hint == 'generic':
            slots.intent_hint = 'assortment'
    if not slots.asks_assortment and slots.requested_size and slots.item_types and any(x in ql for x in ['есть ли', 'бывают ли', 'есть размер']):
        slots.asks_assortment = True
        if slots.intent_hint == 'generic':
            slots.intent_hint = 'assortment'

    if any(x in ql for x in [
        'встанет', 'влезет', 'подойд', 'подходит', 'совместим', 'имеет ли значение', 'имеет значение', 'отличи',
        'плотно', 'сидеть', 'сядет', 'под трубу', 'под трубку', 'трубка',
        'для какой трубы', 'стенк', 'толщина стенки', 'под какую толщину', 'подойдут гильзы',
    ]):
        slots.asks_compatibility = True
        if slots.intent_hint == 'generic':
            slots.intent_hint = 'compatibility'

    if any(x in ql for x in ['монтаж', 'установк', 'подключ', 'стяжк', 'в стену', 'замонолит', 'скрытый монтаж', 'заливать', 'бетон']):
        slots.asks_installation = True
    if any(x in ql for x in ['ограничен', 'нельзя', 'запрещ']):
        slots.asks_limitations = True
    if 'гарант' in ql:
        slots.asks_warranty = True
    if any(x in ql for x in ['какой вес', 'какая длина', 'какое давление', 'какая резьба', 'производител', 'шаг резьб', 'марка латуни']):
        slots.asks_technical_spec = True
        if slots.intent_hint == 'generic':
            slots.intent_hint = 'technical_spec'

    for marker, dtype in DOC_MARKERS.items():
        if marker in ql:
            slots.asks_documents = True
            slots.requested_doc_type = dtype
            break

    return slots
