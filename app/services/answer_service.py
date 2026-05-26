from __future__ import annotations

import re

from app.core.config import settings
from app.core.llm_client import OpenAICompatibleLLMClient
from app.core.prompts import SYSTEM_PROMPT, build_user_prompt
from app.documents.document_search import DocumentSearch
from app.indexes.sku_index import SkuIndex
from app.indexes.kit_index import KitIndex
from app.rag.retriever import RagRetriever
from app.services.confidence import compute_confidence
from app.services.conversation_memory import ConversationMemoryService
from app.services.query_expander import QueryExpander
from app.services.query_resolver import resolve_query
from app.services.router import route_query
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
        self.sku = SkuIndex.load('/data/indexes/sku_index.json')
        if not self.sku.data:
            self.sku = SkuIndex.load('./data/indexes/sku_index.json')
        self.kits = KitIndex.load('/data/indexes/kit_index.json')
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

    async def answer(self, query: str, session_id: str | None = None, answer_style: str = 'detailed') -> dict:
        started = now_ms()
        request_id = gen_request_id()
        sid = self.memory.ensure_session(session_id)
        state = self.memory.get_state(sid)
        recent = self.memory.get_recent_messages(sid, limit=10)
        resolved = resolve_query(query, state, recent)
        resolved_query = resolved['resolved_query']
        expanded_query = self.expander.expand(resolved_query)

        self.memory.append_message(sid, role='user', content=query, request_id=request_id, metadata_json={'resolved_query': resolved_query})

        router = await route_query(resolved_query)
        intent = router.get('intent', 'product_question')
        tools = router.get('tools', ['rag_search'])

        if intent == 'offtopic':
            answer = 'Я консультирую только по сантехническим товарам и связанной документации.'
            payload = {
                'session_id': sid, 'request_id': request_id, 'answer': answer,
                'original_query': query, 'resolved_query': resolved_query, 'depends_on_history': resolved['depends_on_history'],
                'answer_mode': 'not_enough_data', 'sources': [], 'documents': [], 'used_web_search': False,
                'web_results': [], 'confidence': 'high', 'tools_used': ['refuse'],
            }
            self.memory.append_message(sid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent})
            return payload

        article = extract_article_candidate(resolved_query)
        sku_result = self.sku.lookup(article) if article else None

        rag_results = self.rag.search(expanded_query)
        chroma_unavailable = not self.rag.available

        doc_type = None
        ql = resolved_query.lower()
        if 'паспорт' in ql:
            doc_type = 'passport'
        elif 'сертификат' in ql:
            doc_type = 'certificate'
        elif 'инструкц' in ql:
            doc_type = 'manual'

        doc_results = []
        if 'document_search' in tools or intent in {'warranty_question', 'document_request'}:
            doc_results = self.docs.search(expanded_query, article=article, doc_type=doc_type)

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
        if settings.ENABLE_WEB_SEARCH and ('san_team_search' in tools or (not rag_results and not doc_results and not sku_result)):
            web_results = await self.web.search(resolved_query)
            used_web_search = bool(web_results)

        conf = compute_confidence(bool(sku_result), [r.score for r in rag_results], bool(doc_results), used_web_only=used_web_search and not rag_results)

        answer_mode = 'short_answer'
        if intent in {'installation_question', 'warranty_question', 'compatibility_question'}:
            answer_mode = 'technical_answer'
        if intent == 'document_request':
            answer_mode = 'document_answer'
        if intent == 'comparison_question' or 'сравн' in ql:
            answer_mode = 'comparison_answer'
        if 'подоб' in ql or 'выбрать' in ql:
            answer_mode = 'selection_answer'

        sources = [{
            'doc_id': r.metadata.get('doc_id', ''),
            'product': r.metadata.get('product', ''),
            'brand': r.metadata.get('brand', ''),
            'category': r.metadata.get('category', ''),
            'section': r.metadata.get('section', ''),
            'source_file': r.metadata.get('source_file', ''),
            'score': r.score,
        } for r in rag_results[:5]]
        documents = [{'title': d['title'], 'type': d['type'], 'product': d['product'], 'brand': d['brand'], 'public_url': d['public_url']} for d in doc_results]

        # LLM fallback-safe answer
        answer = ''
        composition_keywords = (
            'из чего состоит',
            'состав',
            'что входит',
            'комплект',
            'в наборе',
        )
        asks_composition = any(k in ql for k in composition_keywords)
        if article:
            kit_from_global = self.kits.lookup(article)
        else:
            kit_from_global = None
        kit_components = sku_result.kit_components if sku_result and sku_result.kit_components else []
        if not kit_components and kit_from_global:
            kit_components = kit_from_global.components

        if (sku_result or kit_from_global) and kit_components and (asks_composition or intent == 'article_lookup'):
            base_article = sku_result.article if sku_result else kit_from_global.kit_article
            lines = []
            described_components: list[str] = []
            component_articles = kit_from_global.component_articles if kit_from_global else []
            if not component_articles and sku_result:
                component_articles = [
                    re.search(r'([A-Za-zА-Яа-я0-9._\-/]{4,})$', c).group(1)
                    for c in kit_components
                    if re.search(r'([A-Za-zА-Яа-я0-9._\-/]{4,})$', c)
                ]
            for component_article in component_articles:
                row = self.sku.lookup(component_article)
                if row:
                    described_components.append(f"{row.article} — {row.product}")
            lines.append(f"Состав комплекта {base_article}: " + '; '.join(kit_components) + '.')
            if described_components:
                lines.append("Компоненты:")
                lines.extend([f"- {x}" for x in described_components])
            answer = '\n'.join(lines)

        if comparison_block:
            answer = (
                'Сравнение:\n'
                f"- Что общего: {comparison_block['common']}\n"
                f"- Чем отличаются: {'; '.join(comparison_block['differences'])}\n"
                f"- Для каких случаев: {'; '.join(comparison_block['use_cases'])}"
            )
        try:
            if not answer:
                prompt = build_user_prompt({
                    'original_query': query,
                    'resolved_query': resolved_query,
                    'conversation_state': state,
                    'recent_messages': recent[-10:],
                    'router_decision': router,
                    'sku_result': sku_result.model_dump() if sku_result else None,
                    'product_cards': [],
                    'rag_chunks': [self._sanitize_context(r.text) for r in rag_results[:5]],
                    'document_results': documents,
                    'web_results': web_results,
                    'confidence': conf,
                    'answer_mode': answer_mode,
                    'answer_style': answer_style,
                })
                answer = await self.llm.chat(SYSTEM_PROMPT, prompt)
        except Exception:
            if sku_result:
                answer = f"Артикул {sku_result.article}: {sku_result.product}, бренд {sku_result.brand}, категория {sku_result.category}."
            elif documents:
                answer = 'LLM временно недоступна. Найдены документы: ' + '; '.join([d['title'] for d in documents])
            else:
                answer = 'LLM временно недоступна. Попробуйте повторить запрос позже.'

        if answer_style == 'short' and answer:
            parts = re.split(r'(?<=[.!?])\s+', answer.strip())
            answer = ' '.join(parts[:6])

        if chroma_unavailable:
            answer += '\n\nСемантический поиск временно недоступен, использованы точные индексы.'
        if used_web_search and 'san.team' not in answer:
            answer += '\n\nЧасть информации найдена через поиск по сайту san.team.'

        if conf['label'] == 'low' or (not sources and not documents and not sku_result):
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
            'tools_used': tools,
        }

        save_chat_request(
            request_id=request_id,
            session_id=sid,
            user_message=query,
            answer=answer,
            intent=intent,
            answer_mode=answer_mode,
            router_mode=settings.ROUTER_MODE,
            tools_used_json=tools,
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
