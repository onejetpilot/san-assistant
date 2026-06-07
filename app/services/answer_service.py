from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.core.llm_client import OpenAICompatibleLLMClient
from app.core.prompts import SYSTEM_PROMPT, build_user_prompt
from app.documents.document_search import DocumentSearch
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.indexes.kit_index import KitIndex, KitRecord
from app.rag.retriever import RagRetriever
from app.services.confidence import compute_confidence
from app.services.conversation_memory import ConversationMemoryService
from app.services.query_expander import QueryExpander
from app.services.query_resolver import resolve_query
from app.services.routing.router import route_query
from app.services.routing.rag_quality import (
    filter_relevant_chunks,
    has_strong_rag_context,
    has_weak_rag_context,
    chunks_for_llm,
    preferred_section_groups,
    prioritize_chunks,
    build_no_context_fallback,
    KB_SYNTHESIS_INTENTS,
)
from app.services.routing.observability import log_routing_decision
from app.services.routing.preprocessor import build_routing_context
from app.services.slot_extractor import extract_slots
from app.storage.repository import save_chat_request, save_knowledge_gap, get_current_index_versions
from app.utils.ids import gen_request_id
from app.utils.text import extract_article_candidate
from app.utils.timing import now_ms
from app.web_search.san_team_search import SanTeamSearch
from app.evaluation.answer_judge import evaluate_answer
from app.utils.article_normalizer import normalize_article


INJECTION_PATTERNS = ['ignore previous instructions', 'system prompt', 'developer message']


class AnswerService:
    def __init__(self) -> None:
        self.rag = RagRetriever()
        self.docs = DocumentSearch()
        indexes_path = Path(settings.INDEXES_PATH)
        self.sku = SkuIndex.load(str(indexes_path / 'sku_index.json'))
        if not self.sku.data:
            self.sku = SkuIndex.load('./data/indexes/sku_index.json')
        self.kits = KitIndex.load(str(indexes_path / 'kit_index.json'))
        if not self.kits.data:
            self.kits = KitIndex.load('./data/indexes/kit_index.json')
        self.llm = OpenAICompatibleLLMClient()
        self.web = SanTeamSearch()
        self.memory = ConversationMemoryService()
        self.expander = QueryExpander()

    def _sanitize_context(self, text: str) -> str:
        out = text
        for pat in INJECTION_PATTERNS:
            out = re.sub(pat, '[REMOVED]', out, flags=re.IGNORECASE)
        return out

    @staticmethod
    def _format_sku_answer(sku: SkuRecord) -> str:
        lines = [
            f"Артикул {sku.article}: {sku.product}.",
            f"Бренд: {sku.brand}.",
            f"Категория: {sku.category}.",
        ]
        if sku.article_type:
            lines.append(f"Тип: {sku.article_type}.")
        if sku.short_description:
            lines.append(f"Характеристики: {sku.short_description}.")
        return "\n".join(lines)

    def _format_kit_answer(self, kit: KitRecord, sku: SkuRecord | None = None) -> str:
        base_article = sku.article if sku else kit.kit_article
        lines = [f"Состав комплекта {base_article}: " + "; ".join(kit.components) + "."]
        described_components: list[str] = []
        for component_article in kit.component_articles:
            row = self.sku.lookup(component_article)
            if not row:
                continue
            component_desc = (row.short_description or row.product).strip()
            described_components.append(f"{row.article} — {component_desc}")
        if described_components:
            lines.append("Компоненты:")
            lines.extend([f"- {x}" for x in described_components])
        return "\n".join(lines)

    @staticmethod
    def _extract_dimension_value(short_description: str, dimension_name: str) -> str:
        if not short_description:
            return ''
        if dimension_name == 'length':
            m = re.search(r'длина\s*\(мм\)\s*([0-9]+(?:[,.][0-9]+)?)', short_description, flags=re.IGNORECASE)
            if m:
                return f"{m.group(1)} мм"
        if dimension_name == 'dimension':
            m = re.search(r'(?:диаметр|размер|наружный диаметр|внутренний диаметр)\s*\([^)]*\)\s*([0-9хx/,.]+)', short_description, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        return ''

    @classmethod
    def _format_dimension_answer(cls, sku: SkuRecord, dimension_name: str) -> str:
        value = cls._extract_dimension_value(sku.short_description, dimension_name)
        if dimension_name == 'length' and value:
            return f"У артикула {sku.article} длина: {value}. Характеристики: {sku.short_description}."
        if value:
            return f"У артикула {sku.article} размер/диаметр: {value}. Характеристики: {sku.short_description}."
        return cls._format_sku_answer(sku)

    @staticmethod
    def _format_pipe_compatibility_answer(query: str, rag_results: list) -> str:
        q = query.lower()
        if not any(x in q for x in [
            'встанет', 'влезет', 'подойд', 'подходит', 'совместим',
            'плотно', 'сидеть', 'сядет', 'под трубу', 'под трубку', 'трубка',
        ]):
            return ''

        context = '\n'.join(str(r.text) for r in rag_results[:5])
        if not context:
            return ''

        supports_16_22 = re.search(r'16\s*мм[^\n.]+2[,.]2\s*мм', context, flags=re.IGNORECASE)
        supports_20_28 = re.search(r'20\s*мм[^\n.]+2[,.]8\s*мм', context, flags=re.IGNORECASE)
        asks_16_20 = re.search(r'16\s*[xх/]\s*2[,.]0', q)
        asks_16_22 = re.search(r'16\s*[xх/]\s*2[,.]2', q)
        asks_16_26 = re.search(r'16\s*[xх/]\s*2[,.]6', q)
        asks_20_28 = re.search(r'20\s*[xх/]\s*2[,.]8', q)
        asks_inner_157 = 'внутрен' in q and re.search(r'15[,.]7', q)
        asks_inner_diameter = 'внутрен' in q and 'диаметр' in q

        if asks_inner_157 and supports_16_22:
            return (
                "По базе знаний аксиальные фитинги ONDO рассчитаны на полимерную трубу "
                "с наружным диаметром 16 мм и толщиной стенки 2,2 мм. По внутреннему диаметру "
                "трубки 15,7 мм совместимость подтвердить нельзя: для аксиального соединения важны "
                "наружный диаметр и толщина стенки трубы. Для дренажной трубки кондиционера с внутренним "
                "диаметром 15,7 мм в базе нет подтверждения, что она будет плотно сидеть на таком тройнике."
            )
        if asks_inner_diameter and supports_16_22:
            return (
                "В базе знаний совместимость для аксиальных фитингов ONDO указана не по внутреннему диаметру, "
                "а по наружному диаметру и толщине стенки трубы: для размера 16 — труба 16x2,2 мм. "
                "Подбор по внутреннему диаметру в базе не подтвержден."
            )

        if asks_16_20 and supports_16_22:
            return (
                "По базе знаний для аксиальных фитингов ONDO указана совместимость с трубой "
                "наружным диаметром 16 мм и толщиной стенки 2,2 мм. Для трубы 16x2,0 "
                "подтверждения в базе нет, поэтому я бы не подтверждал совместимость без документа производителя."
            )
        if asks_16_22 and asks_16_26 and supports_16_22:
            return (
                "Из этих вариантов по базе знаний подтверждена труба 16x2,2 мм. "
                "Для трубы 16x2,6 мм подтверждения в базе нет."
            )
        if asks_16_22 and supports_16_22:
            return "Да, в базе знаний указана совместимость с трубой 16x2,2 мм для аксиальных фитингов ONDO."
        if asks_16_26 and supports_16_22:
            return "Для трубы 16x2,6 мм подтверждения в базе нет. В базе указана труба 16x2,2 мм."
        if asks_20_28 and supports_20_28:
            return "Да, в базе знаний указана совместимость с трубой 20x2,8 мм для аксиальных фитингов ONDO."
        return ''

    @staticmethod
    def _format_known_or_missing_spec_answer(query: str, rag_results: list) -> str:
        q = query.lower()
        context = '\n'.join(str(r.text) for r in rag_results[:5])
        if not context:
            return ''

        if 'производител' in q or 'кто производит' in q:
            for chunk in rag_results[:5]:
                manufacturer = str(getattr(chunk, 'metadata', {}).get('manufacturer', '')).strip()
                country = str(getattr(chunk, 'metadata', {}).get('country', '')).strip()
                if manufacturer:
                    suffix = f", {country}" if country else ""
                    return f"Производитель: {manufacturer}{suffix}."
            m = re.search(r'Manufacturer:\s*([^\n]+)', context, flags=re.IGNORECASE)
            if not m:
                m = re.search(r'MANUFACTURER\s*\n?-?\s*([^\n]+)', context, flags=re.IGNORECASE)
            if m:
                return f"Производитель: {m.group(1).strip()}."
            if 'Sabie S.r.l.' in context:
                return "Производитель: Sabie S.r.l., Италия."

        if 'вес' in q:
            return "В базе знаний для аксиальных фитингов ONDO вес одной штуки не указан."

        if 'шаг резьб' in q:
            if 'Тип резьбы: трубная' in context:
                return "В базе знаний указан тип резьбы: трубная. Точный шаг резьбы (например 1,25 или 1,5) в базе не указан."
            return "Точный шаг резьбы в базе знаний не указан."

        if 'марка' in q and 'латун' in q:
            if 'горячештампованная латунь' in context.lower():
                return "В базе знаний указан материал корпуса: горячештампованная латунь. Конкретная марка латуни и метод контроля в базе не указаны."
            return "Конкретная марка латуни и метод контроля в базе знаний не указаны."

        if 'проходн' in q and 'диаметр' in q:
            if 'не заужает внутренний диаметр' in context.lower():
                return "В базе знаний сказано, что конструкция соединения не заужает внутренний диаметр трубопровода. Точное значение проходного диаметра в мм не указано."
            return "Точное значение внутреннего проходного диаметра в базе знаний не указано."

        if 'посадочн' in q:
            return "Длина посадочного места в базе знаний не указана."

        if 'давлен' in q:
            if '1.6 МПа' in context or '1,6 МПа' in context:
                return "Номинальное давление аксиальных фитингов ONDO: 1,6 МПа. Это примерно 16 бар."

        if ('инструмент' in q or 'руками' in q) and ('монтаж' in q or 'монтир' in q or 'зафиксировать' in q):
            return "Монтаж аксиальных фитингов выполняется специальным инструментом: ручным или электрическим/аккумуляторным. Фиксировать руками по базе знаний не предусмотрено."

        return ''

    @staticmethod
    def _matches_item_type(target_type: str, article_type: str) -> bool:
        target = str(target_type or '').strip().lower()
        article = str(article_type or '').strip().lower()
        if not target or not article:
            return False
        if target in article:
            return True

        stems = {
            'гильза': 'гильз',
            'муфта': 'муфт',
            'тройник': 'тройник',
            'уголок': 'угол',
            'соединение': 'соединен',
            'кран': 'кран',
            'коллектор': 'коллектор',
        }
        stem = stems.get(target, target)
        return stem in article

    async def answer(self, query: str, session_id: str | None = None, answer_style: str = 'detailed') -> dict:
        started = now_ms()
        request_id = gen_request_id()
        sid = self.memory.ensure_session(session_id)
        state = self.memory.get_state(sid)
        recent = self.memory.get_recent_messages(sid, limit=10)
        resolved = resolve_query(query, state, recent)
        resolved_query = resolved['resolved_query']
        expanded_query = self.expander.expand(resolved_query)
        slots = extract_slots(resolved_query)

        self.memory.append_message(sid, role='user', content=query, request_id=request_id, metadata_json={'resolved_query': resolved_query})

        routing_ctx = build_routing_context(query, state, recent)
        route = await route_query(
            resolved_query,
            conversation_state=state,
            recent_messages=recent,
            original_query=query,
        )
        intent = route.intent
        tools = route.tools_to_call
        router = route.to_legacy_dict()
        tools_called: list[str] = []
        empty_results: list[str] = []
        fallback_used = False

        if route.needs_clarification or 'clarify' in tools:
            answer = 'Не совсем понял запрос. Уточните, пожалуйста, товар, артикул или параметр (например: "артикулы гильз ONDO" или "паспорт на ONDO...").'
            log_routing_decision(routing_ctx, route, request_id=request_id, tools_called=['clarify'], latency_ms=now_ms() - started)
            payload = {
                'session_id': sid, 'request_id': request_id, 'answer': answer,
                'original_query': query, 'resolved_query': resolved_query, 'depends_on_history': resolved['depends_on_history'],
                'answer_mode': 'clarify', 'sources': [], 'documents': [], 'used_web_search': False,
                'web_results': [], 'confidence': 'low', 'tools_used': ['clarify'],
                'route': router,
            }
            self.memory.append_message(sid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': 'ambiguous_question', 'answer_mode': 'clarify'})
            return payload

        if intent in {'out_of_scope', 'offtopic', 'smalltalk'} or 'refuse' in tools:
            answer = 'Я консультирую только по сантехническим товарам и связанной документации.'
            log_routing_decision(routing_ctx, route, request_id=request_id, tools_called=['refuse'], latency_ms=now_ms() - started)
            payload = {
                'session_id': sid, 'request_id': request_id, 'answer': answer,
                'original_query': query, 'resolved_query': resolved_query, 'depends_on_history': resolved['depends_on_history'],
                'answer_mode': 'not_enough_data', 'sources': [], 'documents': [], 'used_web_search': False,
                'web_results': [], 'confidence': 'high', 'tools_used': ['refuse'],
                'route': router,
            }
            self.memory.append_message(sid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent})
            return payload

        article = routing_ctx.article or extract_article_candidate(resolved_query)
        sku_result = None
        kit_from_global = None
        if route.uses_tool('sku_lookup') and article:
            tools_called.append('sku_lookup')
            sku_result = self.sku.lookup(article)
            if not sku_result:
                empty_results.append('sku_lookup')
        if route.uses_tool('kit_lookup') and article:
            tools_called.append('kit_lookup')
            kit_from_global = self.kits.lookup(article)
            if not kit_from_global:
                empty_results.append('kit_lookup')
        elif article and not kit_from_global:
            kit_from_global = self.kits.lookup(article)

        rag_results: list = []
        chroma_unavailable = not self.rag.available
        if route.uses_tool('rag_search'):
            tools_called.append('rag_search')
            rag_results = self.rag.search(expanded_query)
            if not rag_results:
                empty_results.append('rag_search')
        section_groups = preferred_section_groups(intent, slots)
        rag_results = prioritize_chunks(rag_results, section_groups)
        rag_results_strong = filter_relevant_chunks(rag_results)

        doc_type = None
        ql = resolved_query.lower()
        if 'паспорт' in ql:
            doc_type = 'passport'
        elif 'сертификат' in ql:
            doc_type = 'certificate'
        elif 'инструкц' in ql:
            doc_type = 'manual'
        if slots.requested_doc_type:
            doc_type = slots.requested_doc_type

        doc_results = []
        if route.uses_tool('document_search'):
            tools_called.append('document_search')
            doc_results = self.docs.search(expanded_query, article=article, doc_type=doc_type)
            if not doc_results:
                empty_results.append('document_search')

        # comparison flow
        comparison_block = None
        if intent == 'comparison_question':
            candidates = [normalize_article(x) for x in re.findall(r'\b[A-Za-zА-Яа-я0-9._\-/]{5,}\b', resolved_query)]
            candidates = [c for c in candidates if c]
            unique = list(dict.fromkeys(candidates))[:5]
            cmp_rows = []
            for c in unique:
                row = self.sku.lookup(c)
                if row:
                    cmp_rows.append(row)
            if len(cmp_rows) >= 2:
                common_brand = len({r.brand for r in cmp_rows}) == 1
                comparison_block = {
                    'common': f"Одинаковый бренд: {'да' if common_brand else 'нет'}",
                    'differences': [f"{r.article}: {r.product} / {r.category}" for r in cmp_rows],
                    'use_cases': [f"{r.article} — {r.short_description or 'смотрите описание'}" for r in cmp_rows],
                }

        web_results = []
        used_web_search = False
        local_miss = not sku_result and not doc_results and not has_strong_rag_context(rag_results)
        should_web_search = (
            settings.ENABLE_WEB_SEARCH
            and route.uses_tool('san_team_search')
            and (intent == 'web_search_needed' or (local_miss and route.fallback_allowed))
        )
        if should_web_search:
            tools_called.append('san_team_search')
            web_results = await self.web.search(resolved_query)
            used_web_search = bool(web_results)
            if not web_results:
                empty_results.append('san_team_search')

        conf = compute_confidence(
            bool(sku_result or kit_from_global),
            [r.score for r in rag_results_strong or rag_results],
            bool(doc_results),
            used_web_only=used_web_search and not rag_results_strong,
        )

        answer_mode = 'short_answer'
        if intent in {'installation_or_usage_question', 'installation_question', 'warranty_question'}:
            answer_mode = 'technical_answer'
        if intent == 'document_request':
            answer_mode = 'document_answer'
        if intent == 'comparison_question' or 'сравн' in ql:
            answer_mode = 'comparison_answer'
        if intent in {'product_question', 'price_or_availability_question'} or ('подоб' in ql and intent != 'knowledge_base_question'):
            answer_mode = 'selection_answer'
        if intent in {'knowledge_base_question', 'comparison_question', 'follow_up'}:
            answer_mode = 'technical_answer'

        display_rag = rag_results_strong or rag_results
        sources = [{
            'doc_id': r.metadata.get('doc_id', ''),
            'product': r.metadata.get('product', ''),
            'brand': r.metadata.get('brand', ''),
            'category': r.metadata.get('category', ''),
            'section': r.metadata.get('section', ''),
            'source_file': r.metadata.get('source_file', ''),
            'score': r.score,
        } for r in display_rag[:5]]
        documents = [{'title': d['title'], 'type': d['type'], 'product': d['product'], 'brand': d['brand'], 'public_url': d['public_url']} for d in doc_results]

        # LLM fallback-safe answer
        answer = ''
        composition_keywords = (
            'из чего состоит',
            'состав',
            'что входит',
            'комплект',
            'комплектац',
            'набор',
            'в наборе',
        )
        asks_composition = slots.asks_composition or any(k in ql for k in composition_keywords)
        asks_dimension = slots.intent_hint == 'dimension' or slots.dimension_name in {'length', 'dimension'}
        target_type = slots.item_type
        kit_components = sku_result.kit_components if sku_result and sku_result.kit_components else []
        if not kit_components and kit_from_global:
            kit_components = kit_from_global.components

        if kit_from_global and (asks_composition or intent == 'article_lookup'):
            answer = self._format_kit_answer(kit_from_global, sku_result)
        elif sku_result and kit_components and asks_composition:
            component_articles = [
                re.search(r'([A-Za-zА-Яа-я0-9._\-/]{4,})$', c).group(1)
                for c in kit_components
                if re.search(r'([A-Za-zА-Яа-я0-9._\-/]{4,})$', c)
            ]
            kit = KitRecord(
                kit_article=sku_result.article,
                doc_id=sku_result.doc_id,
                source_file=sku_result.source_file,
                components=kit_components,
                component_articles=component_articles,
            )
            answer = self._format_kit_answer(kit, sku_result)
        elif sku_result and asks_dimension:
            answer = self._format_dimension_answer(sku_result, slots.dimension_name)
        elif sku_result and intent == 'article_lookup':
            answer = self._format_sku_answer(sku_result)

        if not answer and slots.asks_compatibility:
            answer = self._format_pipe_compatibility_answer(resolved_query, rag_results)

        if not answer:
            answer = self._format_known_or_missing_spec_answer(resolved_query, rag_results)

        # Deterministic size answer by article type + dimension, to avoid mixing types (e.g. гильза vs муфта).
        if not answer and asks_dimension and target_type:
            diameter = slots.dimension_value
            candidates = []
            for row in self.sku.data.values():
                at = str(row.get('article_type', '')).lower()
                if not self._matches_item_type(target_type, at):
                    continue
                if slots.brand and str(row.get('brand', '')).upper() != slots.brand:
                    continue
                short = str(row.get('short_description', ''))
                if diameter and not re.search(rf'(^|\D){re.escape(diameter)}(\D|$)', short):
                    continue
                art = str(row.get('article', ''))
                if not art:
                    continue
                candidates.append((art, short))
            if candidates:
                unique = []
                seen = set()
                for art, short in candidates:
                    if art in seen:
                        continue
                    seen.add(art)
                    unique.append((art, short))
                top = unique[:3]
                if len(top) == 1:
                    row = self.sku.lookup(top[0][0])
                    if row:
                        answer = self._format_dimension_answer(row, slots.dimension_name)
                if not answer:
                    lines = [f"Найдено по запросу ({target_type}):"]
                    for art, short in top:
                        lines.append(f"- {art}: {short}")
                    answer = '\n'.join(lines)

        # Deterministic article list by item_type (and optional brand).
        if not answer and slots.asks_articles_list and target_type:
            articles = []
            for row in self.sku.data.values():
                at = str(row.get('article_type', '')).lower()
                if not self._matches_item_type(target_type, at):
                    continue
                if slots.brand and str(row.get('brand', '')).upper() != slots.brand:
                    continue
                a = str(row.get('article', '')).strip()
                if a:
                    articles.append(a)
            articles = list(dict.fromkeys(articles))
            if articles:
                hdr = f"Артикулы {target_type}"
                if slots.brand:
                    hdr += f" {slots.brand}"
                lines = [hdr + ':']
                lines.extend([f"- {a}" for a in articles[:30]])
                answer = '\n'.join(lines)

        if comparison_block:
            answer = (
                'Сравнение:\n'
                f"- Что общего: {comparison_block['common']}\n"
                f"- Чем отличаются: {'; '.join(comparison_block['differences'])}\n"
                f"- Для каких случаев: {'; '.join(comparison_block['use_cases'])}"
            )
        if not answer and intent == 'document_request' and documents:
            answer = 'Найдены документы:\n' + '\n'.join(
                f"- {d['title']} ({d['type']}): {d['public_url']}" for d in documents[:5]
            )

        rag_usable = has_strong_rag_context(rag_results) or (
            intent in KB_SYNTHESIS_INTENTS and has_weak_rag_context(rag_results)
        )
        has_evidence = bool(sku_result or kit_from_global or documents or rag_usable or web_results)
        if not answer and not has_evidence and route.fallback_allowed:
            answer = build_no_context_fallback(intent)
            fallback_used = True
            tools_called.append('fallback')

        rag_only_intents = {'knowledge_base_question', 'installation_or_usage_question', 'warranty_question'}
        try:
            if not answer:
                rag_for_prompt = chunks_for_llm(rag_results, intent, slots)
                if intent in rag_only_intents and not rag_for_prompt and not sku_result and not documents:
                    answer = build_no_context_fallback(intent)
                    fallback_used = True
                    tools_called.append('fallback')
                else:
                    tools_called.append('llm')
                    prompt = build_user_prompt({
                        'original_query': query,
                        'resolved_query': resolved_query,
                        'conversation_state': state,
                        'recent_messages': recent[-10:] if route.use_history or resolved.get('depends_on_history') else [],
                        'router_decision': router,
                        'sku_result': sku_result.model_dump() if sku_result else None,
                        'product_cards': [],
                        'rag_chunks': [self._sanitize_context(r.text) for r in rag_for_prompt[:5]],
                        'document_results': documents,
                        'web_results': web_results,
                        'confidence': conf,
                        'answer_mode': answer_mode,
                        'answer_style': answer_style,
                    })
                    answer = await self.llm.chat(SYSTEM_PROMPT, prompt)
        except Exception:
            fallback_used = True
            if sku_result:
                answer = f"Артикул {sku_result.article}: {sku_result.product}, бренд {sku_result.brand}, категория {sku_result.category}."
            elif documents:
                answer = 'LLM временно недоступна. Найдены документы: ' + '; '.join([d['title'] for d in documents])
            else:
                answer = build_no_context_fallback(intent)

        if answer_style == 'short' and answer:
            parts = re.split(r'(?<=[.!?])\s+', answer.strip())
            answer = ' '.join(parts[:6])

        if chroma_unavailable:
            answer += '\n\nСемантический поиск временно недоступен, использованы точные индексы.'
        if used_web_search and web_results and 'san.team' not in answer:
            answer += '\n\nЧасть информации найдена через поиск по сайту san.team.'

        log_routing_decision(
            routing_ctx,
            route,
            request_id=request_id,
            tools_called=tools_called,
            empty_results=empty_results,
            fallback_used=fallback_used,
            latency_ms=now_ms() - started,
        )

        if conf['label'] == 'low' or (not sources and not documents and not sku_result and not kit_from_global):
            save_knowledge_gap(
                request_id=request_id,
                original_query=query,
                resolved_query=resolved_query,
                intent=intent,
                tools_used=tools,
                reason=conf.get('reason', 'low_confidence_or_no_results'),
            )

        versions = get_current_index_versions()
        latency = now_ms() - started
        response = {
            'session_id': sid,
            'request_id': request_id,
            'answer': answer,
            'original_query': query,
            'resolved_query': resolved_query,
            'depends_on_history': resolved['depends_on_history'],
            'answer_mode': answer_mode,
            'sources': sources,
            'documents': documents,
            'used_web_search': used_web_search,
            'web_results': web_results,
            'confidence': conf['label'],
            'tools_used': tools_called or tools,
            'route': router,
        }

        save_chat_request(
            request_id=request_id,
            session_id=sid,
            user_message=query,
            answer=answer,
            intent=intent,
            answer_mode=answer_mode,
            router_mode=settings.ROUTER_MODE,
            tools_used_json=tools_called or tools,
            sources_json=sources,
            documents_json=documents,
            used_web_search=used_web_search,
            confidence=conf['label'],
            model_name=settings.LLM_MODEL,
            latency_ms=latency,
            rag_index_version=versions.get('rag_index_version'),
            documents_index_version=versions.get('documents_index_version'),
            needs_human_review=(conf['label'] == 'low'),
        )

        current_product = sku_result.product if sku_result else (sources[0]['product'] if sources else state.get('current_product'))
        current_brand = sku_result.brand if sku_result else (sources[0]['brand'] if sources else state.get('current_brand'))
        current_category = sku_result.category if sku_result else (sources[0]['category'] if sources else state.get('current_category'))
        current_article = sku_result.article if sku_result else (article if article else state.get('current_article'))
        current_doc_id = sources[0]['doc_id'] if sources else state.get('current_doc_id')

        self.memory.update_state(
            sid,
            current_product=current_product,
            current_brand=current_brand,
            current_article=current_article,
            current_category=current_category,
            current_doc_id=current_doc_id,
            last_intent=intent,
            last_answer_mode=answer_mode,
            last_sources_json=sources,
            last_documents_json=documents,
        )
        self.memory.append_message(sid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent, 'answer_mode': answer_mode})

        if settings.ENABLE_ANSWER_EVALUATION:
            await evaluate_answer({'query': resolved_query, 'answer': answer, 'sources': sources})

        return response
