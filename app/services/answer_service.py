from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.core.llm_client import OpenAICompatibleLLMClient
from app.core.logging import get_logger
from app.core.prompts import SYSTEM_PROMPT, build_user_prompt
from app.documents.document_search import DocumentSearch
from app.evaluation.answer_judge import evaluate_answer
from app.indexes.kit_index import KitIndex, KitRecord
from app.indexes.sku_index import SkuIndex, SkuRecord
from app.rag.retriever import RagRetriever, RetrievedChunk
from app.services.confidence import compute_confidence
from app.services.conversation_memory import ConversationMemoryService
from app.services.routing.rag_quality import filter_relevant_chunks, prioritize_chunks
from app.services.tool_payload import build_tool_payload, empty_results_payload
from app.storage.repository import get_current_index_versions, save_chat_request, save_knowledge_gap
from app.utils.article_normalizer import normalize_sku
from app.utils.ids import gen_request_id
from app.utils.text import extract_article_candidate
from app.utils.timing import now_ms


INJECTION_PATTERNS = ['ignore previous instructions', 'system prompt', 'developer message']
FOLLOW_UP_MARKERS = [
    'он',
    'она',
    'оно',
    'они',
    'его',
    'ее',
    'её',
    'нему',
    'него',
    'нему',
    'ним',
    'них',
    'этот',
    'эта',
    'это',
    'эти',
    'такой',
    'такая',
    'такие',
]
logger = get_logger('answer_service')


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
        self.memory = ConversationMemoryService()

    def _sanitize_context(self, text: str) -> str:
        out = text
        for pat in INJECTION_PATTERNS:
            out = re.sub(pat, '[REMOVED]', out, flags=re.IGNORECASE)
        return out

    @staticmethod
    def _smalltalk_answer(query: str) -> str:
        q = query.lower()
        if any(token in q for token in ['спасибо', 'благодар']):
            return 'Пожалуйста. Если нужен артикул, характеристика или документ, напишите запрос.'
        if any(token in q for token in ['пока', 'до свидания']):
            return 'Если понадобится информация по товарам или документам, возвращайтесь.'
        return 'Здравствуйте. Помогу с артикулами, характеристиками и документами по сантехническим товарам.'

    @staticmethod
    def _infer_intent(query: str, article: str | None) -> str:
        q = query.lower().strip()
        compact = re.sub(r'\s+', ' ', q)
        if not q or len(q) < 4 or q in {'что лучше?', 'что лучше', 'что это?', 'что это'}:
            return 'clarify'
        if compact in {'привет', 'здравствуйте', 'спасибо', 'пока', 'добрый день', 'добрый вечер'}:
            return 'smalltalk'
        if any(token in q for token in ['стих', 'анекдот', 'погода', 'рецепт', 'фильм']):
            return 'out_of_scope'
        if any(token in q for token in ['паспорт', 'сертификат', 'инструкц', 'pdf', 'документ']):
            return 'document_request'
        if any(token in q for token in ['что входит', 'состав комплект', 'состав набора', 'сколько штук', 'комплектац']):
            return 'kit_composition_question'
        if article and any(token in q for token in ['что за артикул', 'характеристики артикула', 'как называется товар', 'что за ']):
            return 'article_lookup'
        return 'product_qa'

    @staticmethod
    def _extract_doc_type(query: str) -> str | None:
        q = query.lower()
        if 'паспорт' in q:
            return 'passport'
        if 'сертификат' in q:
            return 'certificate'
        if 'инструкц' in q:
            return 'manual'
        return None

    @staticmethod
    def _is_follow_up_query(query: str) -> bool:
        q = query.lower()
        return any(re.search(rf'\b{re.escape(marker)}\b', q) for marker in FOLLOW_UP_MARKERS)

    def _resolve_history_article(self, *, requested_article: str | None, query: str, state: dict) -> tuple[str | None, bool]:
        if requested_article:
            return None, False
        current_article = state.get('current_article')
        if not current_article:
            return None, False
        if self._is_follow_up_query(query):
            return str(current_article), True
        return None, False

    def _collect_relevant_context(
        self,
        *,
        query: str,
        requested_article: str | None,
        matched_sku: SkuRecord | None,
    ) -> list[RetrievedChunk]:
        search_query = query
        anchor_article = requested_article or (matched_sku.article if matched_sku else None)
        if anchor_article and anchor_article not in search_query:
            search_query = f'{query} {anchor_article}'
        raw_chunks = self.rag.search(search_query) or []

        preferred_groups = {
            'description',
            'variants',
            'connections',
            'technical',
            'installation',
            'limitations',
            'faq',
            'key_facts',
        }
        preferred_sections = {
            'DESCRIPTION',
            'VARIANTS (АРТИКУЛЫ)',
            'CONNECTIONS',
            'TECHNICAL SPECIFICATIONS',
            'INSTALLATION',
            'FAQ',
            'KEY FACTS',
            'LIMITATIONS',
            'MATERIALS',
        }
        filtered: list[RetrievedChunk] = []
        seen: set[tuple[str, str]] = set()
        matched_doc_id = matched_sku.doc_id if matched_sku else ''
        for chunk in raw_chunks:
            metadata = getattr(chunk, 'metadata', {}) or {}
            doc_id = str(metadata.get('doc_id', ''))
            group = str(metadata.get('section_group', '')).lower()
            section = str(metadata.get('section', ''))
            if matched_doc_id and doc_id and doc_id != matched_doc_id:
                continue
            if group and group not in preferred_groups and section not in preferred_sections:
                continue
            key = (doc_id, section or chunk.text[:80])
            if key in seen:
                continue
            seen.add(key)
            filtered.append(chunk)

        return prioritize_chunks(filtered or raw_chunks, list(preferred_groups))[:8]

    @staticmethod
    def _log_prompt_preview(request_id: str, system_prompt: str, user_prompt: str) -> None:
        logger.info(
            'llm_prompt_preview',
            extra={
                'extra_data': {
                    'request_id': request_id,
                    'system_prompt_preview': system_prompt[:settings.LLM_PROMPT_PREVIEW_CHARS],
                    'user_prompt_preview': user_prompt[:settings.LLM_PROMPT_PREVIEW_CHARS],
                },
            },
        )

    @staticmethod
    def _format_sku_answer(sku: SkuRecord) -> str:
        lines = [
            f'Артикул {sku.article}: {sku.product}.',
            f'Бренд: {sku.brand}.',
            f'Категория: {sku.category}.',
        ]
        if sku.article_type:
            lines.append(f'Тип: {sku.article_type}.')
        if sku.short_description:
            lines.append(f'Характеристики: {sku.short_description}.')
        return '\n'.join(lines)

    def _format_kit_answer(self, kit: KitRecord, sku: SkuRecord | None = None) -> str:
        base_article = sku.article if sku else kit.kit_article
        lines = [f'Состав комплекта {base_article}: ' + '; '.join(kit.components) + '.']
        described_components: list[str] = []
        for component_article in kit.component_articles:
            row = self.sku.lookup(component_article)
            if not row:
                continue
            component_desc = (row.short_description or row.product).strip()
            described_components.append(f'{row.article} — {component_desc}')
        if described_components:
            lines.append('Компоненты:')
            lines.extend([f'- {item}' for item in described_components])
        return '\n'.join(lines)

    def _finalize_answer(self, answer: str, answer_style: str) -> str:
        if answer_style == 'short' and answer:
            parts = re.split(r'(?<=[.!?])\s+', answer.strip())
            return ' '.join(parts[:6])
        return answer

    def _build_documents_answer(self, documents: list[dict]) -> str:
        if not documents:
            return 'В базе знаний и документации нет данных по этому запросу.'
        return 'Нашёл документы: ' + '; '.join([f"{doc['title']} ({doc['public_url']})" for doc in documents[:5]])

    def _base_response(
        self,
        *,
        session_id: str,
        conversation_id: str,
        request_id: str,
        answer: str,
        original_query: str,
        resolved_query: str,
        answer_mode: str,
        confidence: str,
        tools_used: list[str],
        route: dict,
        depends_on_history: bool = False,
        sources: list[dict] | None = None,
        documents: list[dict] | None = None,
        retrieval_trace: list[dict] | None = None,
    ) -> dict:
        return {
            'session_id': session_id,
            'conversation_id': conversation_id,
            'request_id': request_id,
            'answer': answer,
            'original_query': original_query,
            'resolved_query': resolved_query,
            'depends_on_history': depends_on_history,
            'answer_mode': answer_mode,
            'sources': sources or [],
            'documents': documents or [],
            'used_web_search': False,
            'web_results': [],
            'confidence': confidence,
            'tools_used': tools_used,
            'retrieval_trace': retrieval_trace or [],
            'route': route,
        }

    async def answer(
        self,
        query: str,
        session_id: str | None = None,
        answer_style: str = 'detailed',
        conversation_id: str | None = None,
    ) -> dict:
        started = now_ms()
        request_id = gen_request_id()
        resolved_query = query.strip()
        article = extract_article_candidate(resolved_query)
        normalized_sku = normalize_sku(article)
        requested_article = normalized_sku.normalized or None
        intent = self._infer_intent(resolved_query, requested_article)

        sid = self.memory.ensure_session(session_id)
        cid = self.memory.ensure_conversation(sid, conversation_id)
        state = self.memory.get_state(cid, session_id=sid)
        self.memory.append_message(sid, cid, role='user', content=query, request_id=request_id, metadata_json={'resolved_query': resolved_query})

        history_article, depends_on_history = self._resolve_history_article(
            requested_article=requested_article,
            query=resolved_query,
            state=state,
        )
        lookup_article = requested_article or history_article
        route = {
            'intent': intent,
            'selected_route': 'simple_rag_llm',
            'expected_answer_type': 'consultant_answer',
            'confidence': 0.9 if lookup_article else 0.7,
            'reason': 'single_path_internal_rag',
            'tools': ['sku_lookup', 'rag_search', 'llm'],
        }

        if intent == 'clarify':
            answer = 'Не совсем понял запрос. Уточните, пожалуйста, товар, артикул или параметр.'
            payload = self._base_response(
                session_id=sid,
                conversation_id=cid,
                request_id=request_id,
                answer=answer,
                original_query=query,
                resolved_query=resolved_query,
                answer_mode='clarify',
                confidence='low',
                tools_used=['clarify'],
                route=route,
            )
            self.memory.append_message(sid, cid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': 'clarify', 'answer_mode': 'clarify'})
            return payload

        if intent == 'smalltalk':
            answer = self._smalltalk_answer(query)
            payload = self._base_response(
                session_id=sid,
                conversation_id=cid,
                request_id=request_id,
                answer=answer,
                original_query=query,
                resolved_query=resolved_query,
                answer_mode='short_answer',
                confidence='high',
                tools_used=['smalltalk'],
                route=route,
            )
            self.memory.append_message(sid, cid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent, 'answer_mode': 'short_answer'})
            return payload

        if intent == 'out_of_scope':
            answer = 'Я консультирую только по сантехническим товарам и связанной документации.'
            payload = self._base_response(
                session_id=sid,
                conversation_id=cid,
                request_id=request_id,
                answer=answer,
                original_query=query,
                resolved_query=resolved_query,
                answer_mode='not_enough_data',
                confidence='high',
                tools_used=['refuse'],
                route=route,
            )
            self.memory.append_message(sid, cid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent, 'answer_mode': 'not_enough_data'})
            return payload

        tools_called: list[str] = []
        empty_results: list[str] = []

        sku_result = None
        base_sku_result = None
        if lookup_article:
            tools_called.append('sku_lookup')
            sku_result = self.sku.lookup(lookup_article)
            if requested_article and normalized_sku.base_article and normalized_sku.base_article != requested_article:
                base_sku_result = self.sku.lookup(normalized_sku.base_article)
            if not (sku_result or base_sku_result):
                empty_results.append('sku_lookup')
        matched_sku = sku_result or base_sku_result

        kit_result = None
        if intent == 'kit_composition_question' and lookup_article:
            tools_called.append('kit_lookup')
            base_article = normalized_sku.base_article if requested_article else lookup_article
            kit_result = self.kits.lookup(lookup_article) or self.kits.lookup(base_article)
            if not kit_result:
                empty_results.append('kit_lookup')

        tools_called.append('rag_search')
        rag_query = resolved_query
        if history_article and history_article not in rag_query:
            rag_query = f'{rag_query} {history_article}'
        rag_results = self._collect_relevant_context(
            query=rag_query,
            requested_article=lookup_article,
            matched_sku=matched_sku,
        )
        if not rag_results:
            empty_results.append('rag_search')
        display_rag = filter_relevant_chunks(rag_results) or rag_results

        documents_raw = []
        if intent == 'document_request':
            tools_called.append('document_search')
            documents_raw = self.docs.search(
                rag_query,
                article=lookup_article or normalized_sku.base_article,
                doc_type=self._extract_doc_type(resolved_query),
            )
            if not documents_raw:
                empty_results.append('document_search')
        documents = [
            {
                'title': doc['title'],
                'type': doc['type'],
                'product': doc['product'],
                'brand': doc['brand'],
                'public_url': doc['public_url'],
            }
            for doc in documents_raw
        ]
        sources = [
            {
                'doc_id': chunk.metadata.get('doc_id', ''),
                'product': chunk.metadata.get('product', ''),
                'brand': chunk.metadata.get('brand', ''),
                'category': chunk.metadata.get('category', ''),
                'section': chunk.metadata.get('section', ''),
                'source_file': chunk.metadata.get('source_file', ''),
                'score': chunk.score,
            }
            for chunk in display_rag[:5]
        ]

        confidence = compute_confidence(
            bool(matched_sku or kit_result),
            [item.score for item in display_rag],
            bool(documents),
        )
        answer_mode = 'document_answer' if intent == 'document_request' else 'product_qa'
        final_answer_source = 'no_context'

        if intent == 'kit_composition_question' and kit_result:
            answer = self._format_kit_answer(kit_result, matched_sku)
            final_answer_source = 'kit_lookup'
        elif intent == 'document_request' and documents:
            answer = self._build_documents_answer(documents)
            final_answer_source = 'document_lookup'
        elif not (matched_sku or display_rag or documents):
            answer = 'В базе знаний и документации нет данных по этому запросу.'
            final_answer_source = 'no_context'
        else:
            tools_called.append('llm')
            prompt = build_user_prompt({
                'original_query': query,
                'matched_article': lookup_article or (matched_sku.article if matched_sku else None),
                'sku_result': matched_sku.model_dump() if matched_sku else None,
                'rag_chunks': [self._sanitize_context(chunk.text) for chunk in display_rag[:8]],
                'document_results': documents,
            })
            self._log_prompt_preview(request_id, SYSTEM_PROMPT, prompt)
            try:
                answer = await self.llm.chat(SYSTEM_PROMPT, prompt)
                final_answer_source = 'llm'
            except Exception:
                if matched_sku and intent == 'article_lookup':
                    answer = self._format_sku_answer(matched_sku)
                    final_answer_source = 'sku_fallback'
                elif documents:
                    answer = self._build_documents_answer(documents)
                    final_answer_source = 'document_fallback'
                elif kit_result:
                    answer = self._format_kit_answer(kit_result, matched_sku)
                    final_answer_source = 'kit_fallback'
                else:
                    answer = 'В базе знаний и документации нет данных по этому запросу.'
                    final_answer_source = 'no_context'

        answer = self._finalize_answer(answer, answer_style)

        if confidence['label'] == 'low' or not (sources or documents or matched_sku or kit_result):
            save_knowledge_gap(
                request_id=request_id,
                original_query=query,
                resolved_query=resolved_query,
                intent=intent,
                tools_used=tools_called,
                reason=confidence.get('reason', 'low_confidence_or_no_results'),
            )

        versions = get_current_index_versions()
        latency = now_ms() - started
        retrieval_trace = self._build_retrieval_trace(
            query=resolved_query,
            article=lookup_article,
            sku_result=matched_sku,
            kit_result=kit_result,
            rag_results=display_rag,
            documents=documents,
            tools_called=tools_called,
            empty_results=empty_results,
            intent=intent,
            final_answer_source=final_answer_source,
        )
        response = self._base_response(
            session_id=sid,
            conversation_id=cid,
            request_id=request_id,
            answer=answer,
            original_query=query,
            resolved_query=resolved_query,
            depends_on_history=depends_on_history,
            answer_mode=answer_mode,
            sources=sources,
            documents=documents,
            confidence=confidence['label'],
            tools_used=tools_called,
            retrieval_trace=retrieval_trace,
            route=route,
        )

        save_chat_request(
            request_id=request_id,
            session_id=sid,
            conversation_id=cid,
            user_message=query,
            answer=answer,
            intent=intent,
            answer_mode=answer_mode,
            router_mode=settings.ROUTER_MODE,
            tools_used_json=tools_called,
            sources_json=sources,
            documents_json=documents,
            used_web_search=False,
            confidence=confidence['label'],
            model_name=settings.LLM_MODEL,
            latency_ms=latency,
            rag_index_version=versions.get('rag_index_version'),
            documents_index_version=versions.get('documents_index_version'),
            needs_human_review=(confidence['label'] == 'low'),
        )

        current_product = matched_sku.product if matched_sku else (sources[0]['product'] if sources else None)
        current_brand = matched_sku.brand if matched_sku else (sources[0]['brand'] if sources else None)
        current_category = matched_sku.category if matched_sku else (sources[0]['category'] if sources else None)
        current_article = matched_sku.article if matched_sku else lookup_article
        current_doc_id = sources[0]['doc_id'] if sources else None

        self.memory.update_state(
            cid,
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
        self.memory.append_message(sid, cid, role='assistant', content=answer, request_id=request_id, metadata_json={'intent': intent, 'answer_mode': answer_mode})

        if settings.ENABLE_ANSWER_EVALUATION:
            await evaluate_answer({'query': resolved_query, 'answer': answer, 'sources': sources})

        return response

    @staticmethod
    def _build_retrieval_trace(
        *,
        query: str,
        article: str | None,
        sku_result: SkuRecord | None,
        kit_result: KitRecord | None,
        rag_results: list[RetrievedChunk],
        documents: list[dict],
        tools_called: list[str],
        empty_results: list[str],
        intent: str,
        final_answer_source: str,
    ) -> list[dict]:
        trace: list[dict] = []

        if 'sku_lookup' in tools_called:
            if sku_result:
                trace.append(build_tool_payload(
                    query=article or query,
                    results=[sku_result.model_dump()],
                    meta={'tool': 'sku_lookup'},
                    mode='exact_article',
                ))
            else:
                trace.append(empty_results_payload(
                    query=article or query,
                    note='Article was not found in SKU index.',
                    meta={'tool': 'sku_lookup'},
                    mode='exact_article',
                ))

        if 'kit_lookup' in tools_called:
            if kit_result:
                trace.append(build_tool_payload(
                    query=article or query,
                    results=[kit_result.model_dump()],
                    meta={'tool': 'kit_lookup'},
                    mode='exact_kit_article',
                ))
            else:
                trace.append(empty_results_payload(
                    query=article or query,
                    note='Kit article was not found in kit index.',
                    meta={'tool': 'kit_lookup'},
                    mode='exact_kit_article',
                ))

        if 'rag_search' in tools_called:
            rag_payloads = []
            for chunk in rag_results[:5]:
                metadata = getattr(chunk, 'metadata', {}) or {}
                rag_payloads.append({
                    'doc_id': metadata.get('doc_id', ''),
                    'product': metadata.get('product', ''),
                    'section_group': metadata.get('section_group', ''),
                    'section': metadata.get('section', ''),
                    'source_file': metadata.get('source_file', ''),
                    'score': getattr(chunk, 'score', 0),
                })
            if rag_payloads:
                trace.append(build_tool_payload(
                    query=query,
                    results=rag_payloads,
                    meta={'tool': 'rag_search'},
                    mode='document_aware_chunks',
                ))
            else:
                trace.append(empty_results_payload(
                    query=query,
                    note='No local RAG chunks found.',
                    meta={'tool': 'rag_search'},
                    mode='document_aware_chunks',
                ))

        if 'document_search' in tools_called:
            if documents:
                trace.append(build_tool_payload(
                    query=query,
                    results=documents,
                    meta={'tool': 'document_search'},
                    mode='document_index',
                ))
            else:
                trace.append(empty_results_payload(
                    query=query,
                    note='No matching documents found.',
                    meta={'tool': 'document_search'},
                    mode='document_index',
                ))

        if 'llm' in tools_called:
            trace.append(build_tool_payload(
                query=query,
                results=[{
                    'used_rag_chunks': len(rag_results[:5]),
                    'used_documents': len(documents[:5]),
                    'intent': intent,
                }],
                meta={'tool': 'llm', 'final_answer_source': final_answer_source},
                mode='composer',
            ))

        if not any(tool in tools_called for tool in ['llm', 'document_search', 'kit_lookup']) and not rag_results and not sku_result:
            trace.append(empty_results_payload(
                query=query,
                note='No reliable local context was found.',
                meta={'tool': 'fallback', 'empty_tools': empty_results},
                mode='no_context',
            ))

        return trace
